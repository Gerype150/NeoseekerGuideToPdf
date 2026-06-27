import os
import json
import time
import hashlib
import requests

from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright
from clean_html import clean_html


with open("config.json", encoding="utf-8") as f:
    config = json.load(f)

URL = config["url"]
OUTPUT = config["output"]
RETRIES = config.get("retries", 3)

CACHE = "cache"

browser_context = None

os.makedirs(CACHE, exist_ok=True)


session = requests.Session()
session.headers.update({
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 "
        "(KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.9",
    "Accept-Encoding": "gzip, deflate",
    "Connection": "keep-alive"
})


def cache_file(url):
    return os.path.join(
        CACHE,
        hashlib.md5(url.encode()).hexdigest() + ".html"
    )


def download(url):

    path = cache_file(url)

    if os.path.exists(path):
        with open(path, encoding="utf-8") as f:
            return f.read()

    for attempt in range(RETRIES):

        try:
            r = session.get(
                url,
                timeout=30,
                allow_redirects=True
            )
            if r.status_code in [403, 404]:
                print("Saltando:", r.status_code, url)
                return ""

            r.raise_for_status()
            if "<html" not in r.text.lower():
                print("Respuesta no HTML:", url)
                return ""

            with open(
                path,
                "w",
                encoding="utf-8"
            ) as f:
                f.write(r.text)

            return r.text

        except Exception:
            if attempt == RETRIES - 1:
                raise

            time.sleep(3)

def clean_page(url):

    html = download(url)

    return clean_html(html)



def create_pdf(html):

    with open(
        "guide.html",
        "w",
        encoding="utf-8"
    ) as f:
        f.write(html)


    page = browser_context.new_page()

    page.goto(
        "file://" + os.path.abspath("guide.html")
    )


    page.pdf(
        path=OUTPUT,
        format="A4",
        print_background=True,
        outline=True
    )


    page.close()

def get_cookies_from_browser(context):
    cookies = context.cookies()

    session.cookies.clear()

    for c in cookies:
        session.cookies.set(
            c["name"],
            c["value"],
            domain=c["domain"]
        )



print("Buscando capítulos...")

with sync_playwright() as p:

    browser_context = p.chromium.launch_persistent_context(
        "chrome_profile",
        headless=False,
        viewport={"width":1280,"height":900},
        locale="en-US",
        slow_mo=100
    )

    page = browser_context.new_page()

    page.goto(
        URL,
        wait_until="commit",
        timeout=120000
    )
    page.wait_for_timeout(10000)

    print("Pasa Cloudflare si aparece...")
    
    input("Cuando estés dentro de la guía pulsa ENTER...")
    get_cookies_from_browser(browser_context)

    links = page.locator("a").evaluate_all(
        """
        elements => elements.map(a => ({
            text: a.innerText,
            href: a.href
        }))
        """
    )


    seen = set()
    chapters = []

    for l in links:

        href = l["href"].split("#")[0]
        text = (l["text"] or "").strip()

        if (
            href.startswith("https://www.neoseeker.com/dragon-quest-xi/")
            and text
            and "/File:" not in href
            and "/Image:" not in href
            and "Special:" not in href
            and "javascript:" not in href
            and href.rstrip("/") != URL.rstrip("/")
            and href not in seen
        ):
                seen.add(href)
                chapters.append(href)


    print(
            f"{len(chapters)} capítulos encontrados"
    )


    html = build_html(chapters)

    create_pdf(html)


    browser_context.close()


print(
    "Terminado:",
    OUTPUT
)