import configparser
import datetime
from io import BytesIO
import re
import zipfile
from functools import wraps

import telegram
from telegram.ext import Dispatcher, MessageHandler, Updater, CommandHandler
from lxml import html
import requests
import daiquiri
import fire

from telegram_helper import check_id, command, TelegramBot


logger = daiquiri.getLogger(__name__)


def date_cache(func):
    cache = {}
    @wraps(func)
    def new_func(*args, **kwargs):
        key = (datetime.date.today(), args, frozenset(kwargs.items()))
        logger.debug("Got key %s", key)
        if key in cache:
            logger.debug("Found key in cache")
        return cache.setdefault(key, func(*args, **kwargs))
    return new_func


class ComicBot(TelegramBot):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.jobs = self.database.setdefault("jobs", [])
        self.last_chapter = self.database.setdefault("last_chapter", None)
        self.job_interval = 30

    def get_comic_links(self):
        r1 = requests.get(self.url)
        tree = html.fromstring(r1.content)
        comic_links = [link for link in tree.xpath("//a/@href") if "/download/" in link]
        return comic_links

    def get_chapters(self):
        links = self.get_comic_links()
        chapters = [re.search(r"(\d+)\/$", link).group(1) for link in links]
        return chapters

    @check_id
    @command
    def start(self, bot, update):
        message = update.message
        message.reply_text("Hallo!")

    @check_id
    @command
    def get_comic_list(self, bot, update):
        message = update.message
        message.reply_text("Folgende Kapitel sind verfügbar:")
        liste = "\n".join(f"Kapitel {chap}" for chap in self.get_chapters())
        message.reply_text(liste)

    @date_cache
    def download_comic(self, number):
        comic_link = self.get_comic_links()[number]
        r = requests.get(comic_link, stream=True)
        if r.status_code != 200:
            raise ConnectionError("Could not download comic")
        zipf = zipfile.ZipFile(BytesIO(r.content))
        zipfile_content = sorted(zipf.namelist())
        logger.debug(zipfile_content)
        pics = [BytesIO(zipf.read(name)) for name in zipfile_content]
        return pics

    @check_id
    @command(pass_args=True)
    def send_comic(self, bot, update, args):
        message = update.message
        chat = message.chat
        user_id = message.from_user.id
        logger.debug(args)
        if len(args) != 1:
            message.reply_text("Bitte genau eine Kapitelnummer angeben!")
            return
        try:
            index = self.get_chapters().index(args[0])
        except ValueError:
            message.reply_text("Kapitel nicht gefunden")
            return
        message.reply_text("Ich lade den neuesten Comic...")
        comic = self.download_comic(index)
        for pic in comic:
            chat.send_action(action=telegram.ChatAction.UPLOAD_PHOTO)
            message.reply_photo(photo=pic, timeout=120)

    def check_latest(self, bot, job):
        user_id = job.context
        chapters = self.get_chapters()
        latest = max(chapters, key=int)
        if not self.last_chapter:
            self.last_chapter = latest
        if latest != self.last_chapter:
            bot.send_message(chat_id=user_id,
                             text=f"Neues Kapitel {latest} erhältlich!")
        else:
            bot.send_message(chat_id=user_id,
                             text="Nix gefunden")
            logger.debug("No new chapter found")

    def restart_jobs(self):
        self.current_jobs = {}
        job_queue = self.updater.job_queue
        for user_id in self.jobs:
            logger.debug(f"Restart job for user {user_id}")
            new_job = job_queue.run_repeating(self.check_latest,
                                              interval=self.job_interval, first=0,
                                              context=user_id)
            self.current_jobs[user_id] = new_job

    @check_id
    @command(pass_job_queue=True)
    def watch_chapters(self, bot, update, job_queue):
        # store jobs of this session
        self.current_jobs = {}
        message = update.message
        user_id = message.from_user.id

        if user_id not in self.jobs:
            message.reply_text("Prüfe halbstündlich auf Updates")
            new_job = job_queue.run_repeating(self.check_latest,
                                              interval=self.job_interval,
                                              first=0, context=user_id)
            self.jobs.append(user_id)
            self.current_jobs[user_id] = new_job
        else:
            message.reply_text("Prüfe schon auf Updates")

    @check_id
    @command(pass_job_queue=True)
    def unwatch(self, bot, update, job_queue):
        message = update.message
        user_id = message.from_user.id
        if user_id in self.jobs:
            message.reply_text("Beende halbstündigen Check")
            self.current_jobs[user_id].schedule_removal()
            self.jobs.remove(user_id)
        else:
            message.reply_text("Keinen laufenden Job gefunden")


def run(level="info"):
    daiquiri.setup(level=getattr(daiquiri.logging, level.upper()))
    comic_bot = ComicBot.from_configfile("comicbot.cfg")
    comic_bot.restart_jobs()
    comic_bot.run()


def read_shelve(fname):
    import shelve
    with shelve.open(fname) as f:
        for k, v in f.items():
            print(f"{k}: {v}")


if __name__ == "__main__":
    fire.Fire()