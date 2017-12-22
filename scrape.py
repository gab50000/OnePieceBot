import configparser
import time

import selenium
from selenium import webdriver
import daiquiri
import fire


logger = daiquiri.getLogger(__name__)


cp = configparser.ConfigParser()
cp.read("scrape.cfg")


URL = cp.get("scrape", "url")
PATH = cp.get("scrape", "path")


xpath_comic_link = '//*[@id="content"]/div/div[3]/div[2]/div[2]/div[2]/a'
xpath = '//*[@id="page"]/div/a/img'


class Scraper:
    def __init__(self):
        options = webdriver.ChromeOptions()
        options.set_headless()
        self.driver = webdriver.Chrome(executable_path=PATH, options=options)

    def get_links(self, url):
        self.driver.get(url)
        all_links = [link.get_attribute("href")
                     for link in self.driver.find_elements_by_xpath('//*/a')]
        links = [link for link in all_links if "/read/" in link]
        return links


    def open_comic(self, link):
        self.driver.get(link)
        pic_links = []
        while True:
            try:
                pic = self.driver.find_element_by_xpath(xpath)
            except selenium.common.exceptions.NoSuchElementException:
                logger.info("No more pictures found")
                break
            pic_link = pic.get_attribute("src")
            logger.info(f"Found pic {pic_link}")
            yield pic_link
            pic.click()
            time.sleep(0.2)

    def __del__(self):
        self.driver.quit()


def main(level="info"):
    daiquiri.setup(level=getattr(daiquiri.logging, level.upper()))
    scraper = Scraper()
    links = scraper.get_links(URL)
    print(links)
    pic_links = scraper.open_comic(links[0])
    print(pic_links)


if __name__ == "__main__":
    fire.Fire()
