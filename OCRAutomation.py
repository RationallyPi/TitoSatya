from pathlib import Path
import time
import shutil

import undetected_chromedriver as uc
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# ---------- CONFIG ----------
modelURL = "https://huggingface.co/PaddlePaddle/PaddleOCR-VL-1.5"

INPUT_FOLDER = Path("Papers")
OUTPUT_FOLDER = Path("Parsed_Markdown")
DOWNLOAD_DIR = Path("chrome_downloads").resolve()

OUTPUT_FOLDER.mkdir(exist_ok=True)
DOWNLOAD_DIR.mkdir(exist_ok=True)

CHROME_VERSION = 150

DOWNLOAD_LINK_SELECTOR = "#component-30 a.download-link"
CLEAR_BUTTON_SELECTOR = "button.icon-button[aria-label='Clear']"

# ---------- CHROME SETUP ----------
options = uc.ChromeOptions()
prefs = {
    "download.default_directory": str(DOWNLOAD_DIR),
    "download.prompt_for_download": False,
    "safebrowsing.enabled": True,
}
options.add_experimental_option("prefs", prefs)

driver = uc.Chrome(options=options, version_main=CHROME_VERSION)
wait = WebDriverWait(driver, 30)


def switch_into_gradio_iframe():
    driver.switch_to.default_content()
    iframe = wait.until(
        EC.presence_of_element_located((By.CSS_SELECTOR, "iframe"))
    )
    driver.switch_to.frame(iframe)


def upload_file(filepath: Path):
    file_input = wait.until(
        EC.presence_of_element_located((By.CSS_SELECTOR, "input[type='file']"))
    )
    driver.execute_script("""
        arguments[0].style.display = 'block';
        arguments[0].style.opacity = 1;
        arguments[0].style.visibility = 'visible';
    """, file_input)
    file_input.send_keys(str(filepath.resolve()))
    time.sleep(10)


def click_parse_button():
    parse_button = wait.until(
        EC.element_to_be_clickable((By.ID, "component-14"))
    )
    parse_button.click()


def wait_for_download_link(poll_interval=3, log_every=30):
    start = time.time()
    last_log = start
    was_spinning = True
    tab_opened = False

    while True:
        comp30 = driver.find_elements(By.ID, "component-30")
        if comp30:
            link_matches = driver.find_elements(By.CSS_SELECTOR, DOWNLOAD_LINK_SELECTOR)
            if link_matches:
                elapsed = time.time() - start
                print(f"Download link appeared after {elapsed:.1f}s")
                return link_matches[0]

        spinning = len(driver.find_elements(
            By.CSS_SELECTOR, ".generating, .pending, [data-testid='loading-status']"
        )) > 0

        if was_spinning and not spinning and not tab_opened:
            print(">>> Spinner just disappeared — opening Markdown Source tab")
            comp29 = driver.find_elements(By.ID, "component-29-button")
            if comp29:
                comp29[0].click()
                tab_opened = True
                time.sleep(1)

        was_spinning = spinning

        now = time.time()
        if now - last_log >= log_every:
            print(f"Still waiting... ({now - start:.0f}s elapsed, spinner_visible={spinning})")
            last_log = now

        time.sleep(poll_interval)


def get_newest_file_in(folder: Path, before_time: float, timeout=60) -> Path:
    deadline = time.time() + timeout
    while time.time() < deadline:
        candidates = [
            f for f in folder.iterdir()
            if f.stat().st_mtime > before_time and not f.name.endswith(".crdownload")
        ]
        if candidates:
            return max(candidates, key=lambda f: f.stat().st_mtime)
        time.sleep(0.5)
    raise TimeoutError("Download did not complete in time")


def download_and_save(download_link, original_filename: str):
    before_time = time.time()
    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", download_link)
    download_link.click()

    downloaded_file = get_newest_file_in(DOWNLOAD_DIR, before_time)

    target_name = Path(original_filename).stem + ".txt"
    target_path = OUTPUT_FOLDER / target_name
    shutil.move(str(downloaded_file), str(target_path))
    print(f"Saved: {target_path}")


def clear_upload():
    """
    Clicks the 'Clear' (X) button on the Upload Image component to
    remove the current file, resetting it for the next upload —
    no page reload needed.
    """
    clear_button = wait.until(
        EC.element_to_be_clickable((By.CSS_SELECTOR, CLEAR_BUTTON_SELECTOR))
    )
    clear_button.click()
    print("Cleared upload component for next file")
    time.sleep(5)  # small buffer for the UI to reset
def get_current_download_href():
    """Returns the current download link's href, or None if it doesn't exist."""
    link = driver.find_elements(By.CSS_SELECTOR, DOWNLOAD_LINK_SELECTOR)
    return link[0].get_attribute("href") if link else None


def wait_for_download_link(previous_href=None, poll_interval=3, log_every=30):
    """
    Waits indefinitely, tracking the spinner. When the spinner stops,
    opens the Markdown Source tab (if not already open) and checks
    for a NEW download link (different href from previous_href).
    """
    start = time.time()
    last_log = start
    was_spinning = True
    tab_opened = False

    while True:
        current_href = get_current_download_href()
        if current_href and current_href != previous_href:
            elapsed = time.time() - start
            print(f"New download link appeared after {elapsed:.1f}s")
            return driver.find_element(By.CSS_SELECTOR, DOWNLOAD_LINK_SELECTOR)

        spinning = len(driver.find_elements(
            By.CSS_SELECTOR, ".generating, .pending, [data-testid='loading-status']"
        )) > 0

        if was_spinning and not spinning and not tab_opened:
            print(">>> Spinner just disappeared — opening Markdown Source tab")
            comp29 = driver.find_elements(By.ID, "component-29-button")
            if comp29:
                comp29[0].click()
                tab_opened = True
                time.sleep(1)

        was_spinning = spinning

        now = time.time()
        if now - last_log >= log_every:
            print(f"Still waiting... ({now - start:.0f}s elapsed, spinner_visible={spinning})")
            last_log = now

        time.sleep(poll_interval)




# ---------- MAIN ----------
def main():
    driver.get(modelURL)
    time.sleep(30)

    files = sorted(INPUT_FOLDER.glob("*"))


    #Implement mechanism to iterate through every Date folder.  (Not tested yet)
    date_folders = [f for f in INPUT_FOLDER.iterdir() if f.is_dir()]
    if not date_folders:
        print(f"No date folders found in {INPUT_FOLDER.resolve()}")
        return

    switch_into_gradio_iframe()

    previous_href = None

    for date_folder in date_folders:
        files = sorted(date_folder.glob("*"))
        for i, filepath in enumerate(files):
            print(f"[{i+1}/{len(files)}] Processing {filepath.name}")

        upload_file(filepath)
        click_parse_button()

        download_link = wait_for_download_link(previous_href=previous_href)
        download_and_save(download_link, filepath.name)

        previous_href = download_link.get_attribute("href")

        if i < len(files) - 1:
            clear_upload()

    driver.switch_to.default_content()


if __name__ == "__main__":
    try:
        main()
    finally:
        driver.quit()