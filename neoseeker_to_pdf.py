import os
import json
import time
import hashlib
import requests

from bs4 import BeautifulSoup
from playwright.sync_api import sync_playwright
from urllib.parse import unquote

from clean_html import clean_html


with open("config.json", encoding="utf-8") as f:
    config = json.load(f)


URL = config["url"]
OUTPUT = config["output"]
RETRIES = config.get("retries", 3)

CACHE = "cache"

os.makedirs(CACHE, exist_ok=True)


session = requests.Session()

session.headers.update({
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 "
        "(KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": (
        "text/html,application/xhtml+xml,"
        "application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8"
    ),
    "Accept-Language": "en-US,en;q=0.9",
})


def cache_file(url):

    return os.path.join(
        CACHE,
        hashlib.md5(url.encode()).hexdigest() + ".html"
    )


def download(url):

    url = unquote(url)
    path = cache_file(url)


    if os.path.exists(path):

        with open(
            path,
            encoding="utf-8"
        ) as f:
            return f.read()


    for attempt in range(RETRIES):

        try:

            r = session.get(
                url,
                timeout=30
            )
            print(
                r.status_code,
                url
            )


            if r.status_code in [403,404]:

                print(
                    "Saltando:",
                    r.status_code,
                    url
                )

                return ""


            r.raise_for_status()


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



def get_cookies(context):

    cookies = context.cookies()

    for c in cookies:

        session.cookies.set(
            c["name"],
            c["value"],
            domain=c.get("domain"),
            path=c.get("path")
        )

    print(
        "Cookies copiadas:",
        len(cookies)
    )



def get_chapters(page):


    links = page.locator("a").evaluate_all(
        """
        elements => elements.map(a => ({
            text: a.innerText,
            href: a.href
        }))
        """
    )


    chapters = []
    seen = set()


    for l in links:

        href = l["href"].split("#")[0]
        text = (l["text"] or "").strip()


        if (

            href.startswith(
                "https://www.neoseeker.com/dragon-quest-xi/"
            )

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



    return chapters




def build_html(chapters):


    output = []


    output.append("""
<!DOCTYPE html>

<html>

<head>

<meta charset="utf-8">

<style>

body {
font-family: Arial;
}


.chapter {
page-break-before: always;
}


img {
max-width:100%;
}


table {
border-collapse: collapse;
}


</style>


</head>


<body>


<h1>Neoseeker Walkthrough</h1>

""")


    for i, chapter in enumerate(chapters):

        print(
            f"Procesando {i+1}/{len(chapters)}"
        )


        html = download(chapter)


        if not html:
            continue



        title, content, css = clean_html(html)


        output.append(f"""

            {css}

            <section class="chapter">

            {title}

            {content}

            </section>

            """)


        time.sleep(3)



    output.append(
        "</body></html>"
    )


    return "".join(output)





print("Abriendo navegador...")


with sync_playwright() as p:


    browser = p.chromium.launch_persistent_context(

        "chrome_profile",

        headless=False,

        viewport={
            "width":1280,
            "height":900
        },

        locale="en-US"

    )


    page = browser.new_page()


    page.goto(
        URL,
        wait_until="commit",
        timeout=120000
    )


    input(
        "Pasa Cloudflare y pulsa ENTER..."
    )


    get_cookies(browser)


    chapters = get_chapters(page)


    print(
        f"{len(chapters)} capítulos encontrados"
    )


    html = build_html(chapters)


    with open(
        "guide.html",
        "w",
        encoding="utf-8"
    ) as f:

        f.write(html)


    browser.close()



print(
    "HTML generado:",
    "guide.html"
)