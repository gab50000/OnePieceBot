import time

import selenium
from selenium import webdriver


URL = "https://jaiminisbox.com/reader/series/one-piece-2"

xpath_comic_link = '//*[@id="content"]/div/div[3]/div[2]/div[2]/div[2]/a'
xpath = '//*[@id="page"]/div/a/img'


def get_links(driver):
    wrappers = driver.find_elements_by_xpath('//*[@class="element"]')
    links = [elem.find_elements_by_tag_name("a")[1].get_attribute("href")
             for elem in wrappers]
    return links


def open_comic(driver, link):
    driver.get(link)
    pic_links = []
    while True:
        pic = driver.find_element_by_xpath(xpath)
        pic_link = pic.get_attribute("src")
        print(f"Found pic {pic_link}")
        pic_links.append(pic_link)
        pic.click()
        time.sleep(0.5)
    return pic_links



def main():
    driver = webdriver.PhantomJS()
    driver.get(URL)
    print(driver.title)
    links = get_links(driver)
    print(links)
    pic_links = open_comic(driver, links[0])
    print(pic_links)
    driver.quit()


if __name__ == "__main__":
    main()