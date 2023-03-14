import json
import os
import sys
import time

from selenium.common.exceptions import WebDriverException
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.wait import WebDriverWait
from seleniumwire import webdriver
from selenium.webdriver.chrome.service import Service

import scrape

PAGE_DOWNLOAD_READY = scrape.config_file.get("MATCHING", "PAGE_DOWNLOAD_READY_XPATH")
PAGE_DOWNLOAD_LOADED = scrape.config_file.get("MATCHING", "PAGE_DOWNLOAD_LOADED_XPATH")
RETRY_COUNT = int(scrape.config_file.get("BASIC", "FETCH_RETRY"))

if __name__ == "__main__":
    config_file = scrape.config_file
    chrome_options = Options()
    chrome_param = config_file.get("BASIC", "DOWNLOAD_OPTIONS")
    for param in chrome_param.split(","):
        if len(param.strip()) != 0:
            chrome_options.add_argument(param.strip())

    driver = webdriver.Chrome(Service(config_file.get("BASIC", "DRIVER")), options=chrome_options)
    wait = WebDriverWait(driver, int(config_file.get("BASIC", "WAIT")))

    url_path = sys.argv[1]
    output_folder = sys.argv[2]
    os.makedirs(output_folder, exist_ok=True)

    urls = []
    with open(url_path, "r") as url_file:
        urls.extend(json.load(url_file))
    current = 1
    for url in urls:
        output_path = os.path.join(output_folder, str(current) + ".json")
        if os.path.exists(output_path):
            current = current + 1
            continue
        fetched = False

        retry = 0
        while not fetched and retry < RETRY_COUNT:
            try:
                driver.get(url)
                wait.until(EC.presence_of_element_located((By.XPATH, PAGE_DOWNLOAD_READY)))
                element = driver.find_element(By.XPATH, PAGE_DOWNLOAD_READY)
                actions = ActionChains(driver)
                actions.move_to_element(element).perform()
                wait.until(EC.presence_of_element_located((By.XPATH, PAGE_DOWNLOAD_LOADED)))
                fetched = True
            except WebDriverException as e:
                print(e)
                pass
            retry = retry + 1
            if driver.current_url != url:
                break
        if fetched:
            time.sleep(scrape.get_next_sleep())
            final_page_source = driver.page_source
            time.sleep(0.5)
            while final_page_source != driver.page_source:
                final_page_source = driver.page_source
                time.sleep(0.1)
            output = {"url": url, "time:": time.time(), "html": final_page_source}
            with open(output_path, "w") as file:
                file.write(json.dumps(output))
            print("Downloaded: %d/%d pages" % (current, len(urls)))
        else:
            print("Skipped: " + url)
        current = current + 1
