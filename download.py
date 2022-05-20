import json
import os
import sys
import time

from selenium.common.exceptions import WebDriverException
from selenium.webdriver.chrome.options import Options
from seleniumwire import webdriver

import scrape


if __name__ == "__main__":
    config_file = scrape.config_file
    chrome_options = Options()
    chrome_param = config_file.get("BASIC", "DOWNLOAD_OPTIONS")
    for param in chrome_param.split(","):
        if len(param.strip()) != 0:
            chrome_options.add_argument(param.strip())

    driver = webdriver.Chrome(config_file.get("BASIC", "DRIVER"), options=chrome_options)

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
        while not fetched:
            try:
                driver.get(url)
                fetched = True
            except WebDriverException:
                pass
        time.sleep(scrape.get_next_sleep())
        output = {"url": url, "time:": time.time(), "html": driver.page_source}
        with open(output_path, "w") as file:
            file.write(json.dumps(output))
        print("Downloaded: %d/%d pages" % (current, len(urls)))
        current = current + 1
