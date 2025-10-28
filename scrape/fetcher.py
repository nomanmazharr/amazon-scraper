import requests
import time
import random

def fetch_html(url, headers=None, backoff=1):
    if headers is None:
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/118.0.0.0 Safari/537.36',
            'Accept-Language': 'en-US,en;q=0.9',
            'Accept-Encoding': 'gzip, deflate, br',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
            'Referer': 'https://www.amazon.com/'
        }
    try:
        response = requests.get(url, headers=headers)
        if response.status_code == 429:
            sleep_time = backoff * random.uniform(1, 2)
            print(f"Rate limited (429). Backing off for {sleep_time:.2f} seconds.")
            time.sleep(sleep_time)
            return fetch_html(url, headers, backoff * 2)
        response.raise_for_status()
        return response.text
    except requests.exceptions.RequestException as e:
        print(f"Error fetching {url}: {e}")
        return None

def load_local_html(filename):
    try:
        with open(filename, 'r', encoding='utf-8') as f:
            return f.read()
    except FileNotFoundError:
        print(f"Local HTML file not found: {filename}")
        return None