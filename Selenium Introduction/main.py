import time
import os
import glob
import pandas as pd

from selenium import webdriver
from selenium.webdriver.chrome.webdriver import WebDriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
# The HTML report must be in the same folder as main.py
REPORT_PATH = glob.glob(os.path.join(BASE_DIR, "*.html"))[0]
OUTPUT_DIR = os.path.join(BASE_DIR, "output")


class SeleniumWebDriverContextManager:
    def __init__(self):
        self.driver = None

    def __enter__(self):
        options = webdriver.ChromeOptions()
        options.add_argument("--headless=new")
        options.add_argument("--window-size=1400,1000")
        self.driver = webdriver.Chrome(options=options)
        return self.driver

    def __exit__(self, exc_type, exc_value, traceback):
        if self.driver:
            self.driver.quit()


def extract_table(driver: WebDriver):
    try:
        wait = WebDriverWait(driver, 10)

        # using ID as locator
        plot = wait.until(EC.presence_of_element_located((By.CLASS_NAME, "plotly-graph-div")))
        plot_id = plot.get_attribute("id")
        plot = driver.find_element(By.ID, plot_id)

        # using CSS selector as locator
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "g.table")))

        # using xpath as locator
        header_cells = driver.find_elements(By.XPATH, "//*[name()='g' and @id='header']//*[name()='text']")
        headers = [cell.get_attribute("textContent") for cell in header_cells[:3]]

        columns = driver.execute_script("return arguments[0].data[0].cells.values;", plot)
        rows = list(zip(*columns))

        df = pd.DataFrame(rows, columns=headers)
        df.to_csv(os.path.join(OUTPUT_DIR, "table.csv"), index=False)
        print(f"table.csv saved ({len(df)} rows)")
    except (TimeoutException, NoSuchElementException) as e:
        print("Could not read the table:", e)


def read_doughnut(driver: WebDriver):
    rows = []
    for text in driver.find_elements(By.CSS_SELECTOR, "g.slicetext text"):
        lines = text.find_elements(By.CSS_SELECTOR, "tspan.line")
        rows.append((lines[0].get_attribute("textContent"), lines[1].get_attribute("textContent")))
    return pd.DataFrame(rows, columns=["Facility Type", "Min Average Time Spent"])


def save_state(driver: WebDriver, index: int):
    time.sleep(2)  # wait for the chart animation to finish
    driver.save_screenshot(os.path.join(OUTPUT_DIR, f"screenshot{index}.png"))
    read_doughnut(driver).to_csv(os.path.join(OUTPUT_DIR, f"doughnut{index}.csv"), index=False)
    print(f"State {index} saved")


def process_doughnut(driver: WebDriver):
    try:
        wait = WebDriverWait(driver, 10)
        wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "g.pielayer g.slice")))

        # State 0: no filters applied
        save_state(driver, 0)

        filter_count = len(driver.find_elements(By.CSS_SELECTOR, "g.legend g.traces"))
        for i in range(filter_count):
            try:
                filters = driver.find_elements(By.CSS_SELECTOR, "g.legend g.traces")
                filters[i].find_element(By.CLASS_NAME, "legendtoggle").click()
                save_state(driver, i + 1)
            except (NoSuchElementException, IndexError) as e:
                print(f"Filter {i + 1} could not be applied:", e)
    except TimeoutException as e:
        print("Doughnut chart did not load:", e)


if __name__ == "__main__":
    os.makedirs(OUTPUT_DIR, exist_ok=True)
    with SeleniumWebDriverContextManager() as driver:
        driver.get("file:///" + REPORT_PATH.replace("\\", "/").lstrip("/"))
        extract_table(driver)
        process_doughnut(driver)