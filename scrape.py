import configparser
import time

import selenium
from selenium import webdriver
import daiquiri


logger = daiquiri.getLogger()


cp = configparser.ConfigParser()
cp.read("scrape.cfg")


URL = cp.get("scrape", "url")
PATH = cp.get("scrape", "path")


xpath_comic_link = '//*[@id="content"]/div/div[3]/div[2]/div[2]/div[2]/a'
xpath = '//*[@id="page"]/div/a/img'


def get_links(driver):
    all_links = driver.find_elements_by_xpath('//*/a/@href')
    links = [link for link in all_links if "/read/" in link]
    return links


def open_comic(driver, link):
    driver.get(link)
    pic_links = []
    while True:
        try:
            pic = driver.find_element_by_xpath(xpath)
        except selenium.common.exceptions.NoSuchElementException:
            logger.info("No more pictures found")
            break
        pic_link = pic.get_attribute("src")
        logger.info(f"Found pic {pic_link}")
        pic_links.append(pic_link)
        pic.click()
        time.sleep(0.2)
    return pic_links


def main():
    daiquiri.setup(level=daiquiri.logging.DEBUG)
    options = webdriver.ChromeOptions()
    options.set_headless()
    driver = webdriver.Chrome(executable_path=PATH, options=options)
    driver.get(URL)
    print(driver.title)
    links = get_links(driver)
    print(links)
    pic_links = open_comic(driver, links[0])
    print(pic_links)
    driver.quit()


if __name__ == "__main__":
    main()
