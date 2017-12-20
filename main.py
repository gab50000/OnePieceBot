import configparser
from io import BytesIO
import re
import zipfile

import telegram
from telegram.ext import Dispatcher, MessageHandler, Updater, CommandHandler
from lxml import html
import requests
import daiquiri
from tinydb import TinyDB, Query


daiquiri.setup(level=daiquiri.logging.DEBUG)
logger = daiquiri.getLogger(__name__)


config = configparser.ConfigParser()
config.read("auth.cfg")
TOKEN = config["Telegram"]["token"]
ADMIN_ID = int(config["Telegram"]["admin_id"])


DB = TinyDB("bot_db.json")
AUTH = DB.table("authorized")
LAST_UPDATE = DB.table("last_update")


def check_id(func):
    def new_func(self, bot, update, **kwargs):
        requesting_id = update.message.chat_id
        if AUTH.search(Query().id == requesting_id):
            logger.debug("Found ID in database")
            func(self, bot, update, **kwargs)
        else:
            chat = update.message.chat
            warning = f"User {chat.first_name} {chat.last_name} with id " \
                      f"{requesting_id} not in id list"
            logger.warning(warning)
            bot.send_message(chat_id=ADMIN_ID, text=warning)
    return new_func


class ComicBot:
    def __init__(self):
        self.updater = Updater(token=TOKEN)
        self.url = "https://jaiminisbox.com/reader/series/one-piece-2/"
        handlers = [CommandHandler("start", self.start),
                    CommandHandler("comic_list", self.get_comic_list),
                    CommandHandler("read", self.send_comic, pass_args=True),
                    CommandHandler("authorize", self.authorize, pass_args=True),
                    CommandHandler("watch_chapters", self.watch_chapters,
                                   pass_job_queue=True),
                    CommandHandler("unwatch", self.unwatch,
                                   pass_job_queue=True)]
        dispatcher = self.updater.dispatcher
        for h in handlers:
            dispatcher.add_handler(h)
        self.updater.start_polling()
        self.jobs = {}

    @property
    def comic_list(self):
        r1 = requests.get(self.url)
        tree = html.fromstring(r1.content)
        comic_links = [link for link in tree.xpath("//a/@href") if "/download/" in link]
        return comic_links

    @property
    def chapters(self):
        links = self.comic_list
        chapters = [re.search(r"(\d+)\/$", link).group(1) for link in links]
        return chapters

    @check_id
    def start(self, bot, update):
        user_id = update.message.from_user.id
        bot.send_message(chat_id=user_id, text="Hallo!")

    @check_id
    def get_comic_list(self, bot, update):
        user_id = update.message.from_user.id
        bot.send_message(chat_id=user_id,
                         text="Folgende Kapitel sind verfügbar:")
        liste = "\n".join(f"Kapitel {chap}" for chap in self.chapters)
        bot.send_message(chat_id=user_id, text=liste)

    def download_comic(self, number):
        comic_link = self.comic_list[number]
        r = requests.get(comic_link, stream=True)
        if r.status_code != 200:
            raise ConnectionError("Could not download comic")
        zipf = zipfile.ZipFile(BytesIO(r.content))
        zipfile_content = sorted(zipf.namelist())
        logger.debug(zipfile_content)
        pics = [BytesIO(zipf.read(name)) for name in zipfile_content]
        return pics

    @check_id
    def send_comic(self, bot, update, args):
        user_id = update.message.from_user.id
        logger.debug(args)
        if len(args) != 1:
            bot.send_message(chat_id=user_id, text="Bitte genau eine "
                             "Kapitelnummer angeben!")
            return
        try:
            index = self.chapters.index(args[0])
        except ValueError:
            bot.send_message(chat_id=user_id, text="Kapitel nicht gefunden")
            return
        bot.send_message(chat_id=user_id, text="Ich lade den neuesten Comic...")
        comic = self.download_comic(index)
        for pic in comic:
            bot.send_chat_action(chat_id=user_id, action=telegram.ChatAction.UPLOAD_PHOTO)
            self.updater.bot.send_photo(chat_id=user_id, photo=pic, timeout=120)

    def check_latest(self, bot, job):
        user_id = job.context
        chapters = self.chapters
        latest = max(chapters, key=int)
        if not LAST_UPDATE.all():
            LAST_UPDATE.insert({"chapter": latest})
        if latest != LAST_UPDATE.all()[0]["chapter"]:
            bot.send_message(chat_id=user_id,
                             text=f"Neues Kapitel {latest} erhältlich!")
        else:
            logger.debug("No new chapter found")

    @check_id
    def watch_chapters(self, bot, update, job_queue):
        user_id = update.message.from_user.id

        if user_id not in self.jobs:
            bot.send_message(chat_id=user_id,
                             text="Prüfe halbstündlich auf Updates")
            new_job = job_queue.run_repeating(self.check_latest, interval=1800, first=0,
                                              context=update.message.chat_id)
            self.jobs[user_id] = new_job
        else:
            bot.send_message(chat_id=user_id,
                             text="Prüfe schon auf Updates")

    @check_id
    def unwatch(self, bot, update, job_queue):
        user_id = update.message.from_user.id
        if user_id in self.jobs:
            bot.send_message(chat_id=user_id,
                            text="Beende halbstündigen Check")
            self.jobs[user_id].schedule_removal()
            del self.jobs[user_id]
        else:
            bot.send_message(chat_id=user_id,
                            text="Keinen laufenden Job gefunden")


    def authorize(self, bot, update, args):
        user_id = update.message.from_user.id
        if user_id != ADMIN_ID:
            logger.debug("Authorize request from non-Admin")
            return
        if not args:
            logger.debug("No ids specified")
            return
        try:
            new_ids = [int(arg) for arg in args]
        except ValueError:
            bot.send_message(chat_id=user_id, text="Ungültige id")
        logger.debug("New ids: %s", new_ids)
        for id_ in new_ids:
            AUTH.insert({"id": id_})
            bot.send_message(chat_id=user_id, text=f"Füge id {id_} hinzu.")


comic_bot = ComicBot()