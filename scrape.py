from configparser import ConfigParser

from selenium import webdriver
from selenium.common.exceptions import NoSuchElementException, StaleElementReferenceException, WebDriverException
from selenium.webdriver import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.wait import WebDriverWait
from seleniumwire import webdriver
import re
import time
import json
import random
config_file = ConfigParser()
config_file.read("config.ini")
driver = webdriver.Chrome(config_file.get("BASIC", "DRIVER"))
wait = WebDriverWait(driver, int(config_file.get("BASIC", "WAIT")))


# webpage elements to match/click on
SEARCH_WAIT_XPATH = config_file.get("MATCHING", "SEARCH_WAIT_XPATH")
NO_RES_XPATH = config_file.get("MATCHING", "NO_RES_XPATH")
RES_COUNT_XPATH = config_file.get("MATCHING", "RES_COUNT_XPATH")
NEXT_PAGE_XPATH = config_file.get("MATCHING", "NEXT_PAGE_XPATH")
LINK_XPATH = config_file.get("MATCHING", "LINK_XPATH")
PAGE_NAV_XPATH = config_file.get("MATCHING", "PAGE_NAV_XPATH")
PAGE_NUM_XPATH_TEMPLATE = config_file.get("MATCHING", "PAGE_NUM_XPATH_TEMPLATE")


# regular expression for matching the page number
PAGE_RANGE_REGEX = config_file.get("MATCHING", "PAGE_RANGE_REGEX")
PAGE_RANGE_REGEX_GROUP = config_file.get("MATCHING", "PAGE_RANGE_REGEX_GROUP")


# control parameters
INCREMENT = int(config_file.get("MATCHING", "PRICE_INCREMENT"))
MAX_PAGE_COUNT = int(config_file.get("MATCHING", "MAX_PAGE_COUNT"))
NEXT_SLEEP = int(config_file.get("BASIC", "SLEEP"))

# targets for the scraper
URL = config_file.get("TARGET", "URL_TEMPLATE")
START_PRICE = int(config_file.get("TARGET", "START_PRICE"))
MAX_PRICE = int(config_file.get("TARGET", "MAX_PRICE"))


def get_next_sleep():
    return random.randint(1, NEXT_SLEEP + 1)


def find_scroll_and_wait(by, value):
    element = driver.find_element(by, value)
    return scroll_and_wait(element)


def scroll_and_wait(element):
    act = ActionChains(driver).move_to_element(element)
    act.perform()

    element = wait.until(EC.visibility_of(element))
    return element


def wait_scroll_and_wait(by, value):
    element = wait.until(EC.presence_of_element_located((by, value)))
    return scroll_and_wait(element)


def wait_for_search(xpath):
    wait.until(EC.presence_of_element_located((By.XPATH, xpath)))
    return


def find_num_results(no_res_path, res_count_path, page_regex, page_regex_group):
    try:
        driver.find_element_by_xpath(no_res_path)
        return 0
    except NoSuchElementException:
        try:
            page_elt = driver.find_element_by_xpath(res_count_path)
            page_match = re.match(page_regex, page_elt.text)
            return int(page_match.group(page_regex_group))
        except NoSuchElementException:
            return 1


def go_to_next_page(current, next_xpath):
    wait.until(EC.presence_of_element_located((By.XPATH, PAGE_NAV_XPATH)))
    while True:
        try:
            next_btn = driver.find_element_by_xpath((PAGE_NUM_XPATH_TEMPLATE % (current + 1)))
            break
        except NoSuchElementException:
            try:
                next_btn = wait_scroll_and_wait(By.XPATH, next_xpath)
                break
            except StaleElementReferenceException:
                pass
    driver.execute_script("arguments[0].click();", next_btn)


def scan_current_page(link_path):
    result = []
    while len(result) == 0:
        try:
            wait.until(EC.element_to_be_clickable((By.XPATH, link_path)))
            elements = driver.find_elements_by_xpath(link_path)
            for elt in elements:
                result.append(elt.get_attribute("href"))
        except StaleElementReferenceException:
            result.clear()
    return result


def set_price_range(current, increment):
    next_url = URL % (current, current + increment)
    while True:
        try:
            driver.get(next_url)
            time.sleep(get_next_sleep())
            if driver.current_url == next_url:
                break
        except WebDriverException:
            pass
    wait_for_search(SEARCH_WAIT_XPATH)
    page_count = find_num_results(NO_RES_XPATH, RES_COUNT_XPATH, PAGE_RANGE_REGEX, PAGE_RANGE_REGEX_GROUP)
    return page_count


def initialize_scraping(base_price):
    current = 0
    wait_for_search(SEARCH_WAIT_XPATH)
    page_count = find_num_results(NO_RES_XPATH, RES_COUNT_XPATH, PAGE_RANGE_REGEX, PAGE_RANGE_REGEX_GROUP)
    print(page_count)

    while page_count == 0:
        page_count = set_price_range(base_price, INCREMENT)
        print("Pages: " + str(page_count))
        time.sleep(get_next_sleep())
        current = base_price
        base_price = base_price + INCREMENT
    return current, page_count


def scan_until_success(initial_results, current_page):
    prev_results = initial_results
    current_result = prev_results
    next_retry = 0
    while prev_results == current_result:
        if next_retry > 3:
            go_to_next_page(current_page, NEXT_PAGE_XPATH)
        if next_retry > 10:
            raise TimeoutError()
        time.sleep(get_next_sleep())
        wait_for_search(SEARCH_WAIT_XPATH)
        current_result = scan_current_page(LINK_XPATH)
        next_retry = next_retry + 1
    return current_result


def scrape_apartments(start_price, init_pages, increment):
    results = []
    current = start_price
    page_count = init_pages

    while current <= MAX_PRICE:
        try:
            while page_count <= MAX_PAGE_COUNT:
                increment = max(1, increment / 2)
                page_count = set_price_range(current, increment)
            print("Pages:" + str(page_count))
            first_result = scan_current_page(LINK_XPATH)
            print("Added: %s" % first_result)
            results.extend(scan_current_page(LINK_XPATH))
            prev_results = first_result
            for i in range(1, page_count):
                go_to_next_page(i, NEXT_PAGE_XPATH)
                current_result = scan_until_success(prev_results, i)
                prev_results = current_result
                results.extend(current_result)
                print("Added: %s" % current_result)
        except TimeoutError:
            break

        if page_count < 20:
            increment = increment + 5
        current += increment
        page_count = set_price_range(current, INCREMENT)
        print("Scanned Apartments: " + str(len(set(results))))
    return results


if __name__ == "__main__":
    start = START_PRICE
    driver.get(URL % (START_PRICE, START_PRICE))
    driver.maximize_window()
    start_price, init_pages = initialize_scraping(start)

    results = scrape_apartments(start_price, init_pages, INCREMENT)

    results = list(set(results))
    with open("urls.json", "w") as file:
        file.write(json.dumps(results))
    print("Scraping Complete")
