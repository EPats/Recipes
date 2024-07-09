import random
import time
import requests
from bs4 import BeautifulSoup
from logger import get_logger


def get_page(url: str, retries: int = 3, backoff_factor: float = 0.3) -> BeautifulSoup | None:
    user_agents: list[str] = [
        'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.0 Safari/605.1.15',
        'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'
    ]

    for attempt in range(retries):
        try:
            headers: dict = {
                'User-Agent': random.choice(user_agents),
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
                'Referer': 'https://www.google.com/',
                'DNT': '1',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
            }

            response: requests.Response = requests.get(url, headers=headers, timeout=15)
            response.raise_for_status()

            return BeautifulSoup(response.text, 'html.parser')

        except requests.exceptions.RequestException as e:
            get_logger().warning(f'Attempt {attempt + 1} failed for {url}: {str(e)}')
            if attempt + 1 < retries:
                time.sleep(backoff_factor * (2 ** attempt) + random.uniform(0, 1))
            else:
                get_logger().error(f'Failed to fetch {url} after {retries} attempts')
                return None

    return None
