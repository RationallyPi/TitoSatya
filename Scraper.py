from pathlib import Path
from datetime import datetime, timedelta
import time
import requests
import undetected_chromedriver as uc

from selenium.webdriver.common.by import By

# -----------------------------
# CONFIG
# -----------------------------
START_DATE = "2026-03-27"
END_DATE = "2026-07-05"


#START_DATE = "2024-07-15"
#END_DATE = "2024-09-23"

BASE_URL = "https://epaper.ekantipur.com/kathmandupost/"
BASE_DOMAIN = "https://epaper.ekantipur.com"

SAVE_ROOT = Path("Papers")

# -----------------------------
# CHROME
# -----------------------------
profile = Path("selenium_profile").resolve()

options = uc.ChromeOptions()
options.add_argument(f"--user-data-dir={profile}")

driver = uc.Chrome(options=options, version_main=150)

# -----------------------------
# COPY COOKIES TO REQUESTS
# -----------------------------
session = requests.Session()

def update_session_cookies():
    session.cookies.clear()

    for cookie in driver.get_cookies():
        session.cookies.set(
            cookie["name"],
            cookie["value"]
        )

# -----------------------------
# DATE LIST
# -----------------------------
start = datetime.strptime(START_DATE, "%Y-%m-%d")
end = datetime.strptime(END_DATE, "%Y-%m-%d")

current = start

while current <= end:

    date = current.strftime("%Y-%m-%d")

    print(f"\nScraping {date}")

    save_dir = SAVE_ROOT / date
    save_dir.mkdir(parents=True, exist_ok=True)

    driver.get(BASE_URL + date)

    # wait for page to initialize
    time.sleep(3)

    # -----------------------------
    # SCROLL UNTIL ALL PAGES LOAD
    # -----------------------------
    last_height = 0

    while True:

        driver.execute_script(
            "window.scrollBy(0, 1200);"
        )

        time.sleep(0.5)

        height = driver.execute_script(
            "return document.body.scrollHeight"
        )

        if height == last_height:
            break

        last_height = height

    # update cookies
    update_session_cookies()

    # -----------------------------
    # FIND PAGE IMAGES
    # -----------------------------
    imgs = driver.find_elements(By.CSS_SELECTOR, "img.imgSection")

    page_urls = {}

    for img in imgs:

     url = (
          img.get_attribute("data-original")
          or img.get_attribute("src")
     )

     page = img.get_attribute("data-page-num")

     if not url or not page:
          continue

     page = int(page)

     # Only keep the first 5 pages
     if page > 5:
          continue

     if (
          date in url
          and "/large/" in url
          and "page-" in url
     ):
          page_urls[page] = url

    # -----------------------------
    # DOWNLOAD
    # -----------------------------
    for page in sorted(page_urls):

        url = page_urls[page]

        if url.startswith("/"):
            url = BASE_DOMAIN + url

        print(f"Downloading page {page}")

        r = session.get(url)

        if r.status_code == 200:

            with open(
                save_dir / f"page_{page}.jpg",
                "wb"
            ) as f:
                f.write(r.content)

        else:
            print(
                f"Failed page {page} ({r.status_code})"
            )

    current += timedelta(days=1)

driver.quit()