import time
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.by import By
from selenium.common.exceptions import TimeoutException, WebDriverException
from bs4 import BeautifulSoup
from logger import get_logger
import atexit
import re


driver: webdriver.Chrome | None = None


@atexit.register
def exit_handler() -> None:
    close_driver()


def close_driver() -> None:
    global driver
    if driver:
        get_logger().info('Closing Chrome driver')
        driver.close()
        driver.quit()
        driver = None


def get_base_url(url: str) -> str:
    base: str = re.sub(r'(https?://)?(www\.)?', '', url)
    base = base.split('/')[0]
    return base


def set_chrome_options() -> Options:
    chrome_options = Options()
    chrome_options.add_argument("--headless")
    chrome_options.add_argument("--no-sandbox")
    chrome_options.add_argument("--disable-dev-shm-usage")
    chrome_options.add_argument("--disable-blink-features=AutomationControlled")
    chrome_options.add_argument("--start-maximized")
    chrome_options.add_argument("--disable-extensions")
    chrome_options.add_experimental_option("excludeSwitches", ["enable-automation"])
    chrome_options.add_experimental_option('useAutomationExtension', False)
    chrome_prefs = {
        "profile.default_content_settings": {"images": 2},
        "profile.managed_default_content_settings": {"images": 2}
    }
    chrome_options.add_experimental_option("prefs", chrome_prefs)
    return chrome_options


def get_page(url: str, retries: int = 3) -> BeautifulSoup | None:
    global driver
    driver = webdriver.Chrome(options=set_chrome_options())
    driver.execute_cdp_cmd('Network.setUserAgentOverride', {
        "userAgent": 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/83.0.4103.53 Safari/537.36'})

    for attempt in range(retries):
        try:
            # Navigate to Google first
            driver.get("https://www.google.com")
            time.sleep(2)  # Wait for a bit

            # Now navigate to the actual URL
            driver.get(url)
            time.sleep(5)  # Wait for the page to load

            # Scroll down the page
            driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
            time.sleep(2)  # Wait after scrolling

            WebDriverWait(driver, 10).until(EC.presence_of_element_located((By.TAG_NAME, "body")))

            page_source = driver.page_source
            return BeautifulSoup(page_source, 'html.parser')

        except TimeoutException:
            get_logger().warning(f'Attempt {attempt + 1} timed out for {url}')
        except WebDriverException as e:
            get_logger().warning(f'WebDriver error on attempt {attempt + 1} for {url}: {str(e)}')
        except Exception as e:
            get_logger().warning(f'Unexpected error on attempt {attempt + 1} for {url}: {str(e)}')
        finally:
            if attempt + 1 == retries:
                get_logger().error(f'Failed to fetch {url} after {retries} attempts')
                close_driver()
                return None
            close_driver()

    close_driver()
    return None