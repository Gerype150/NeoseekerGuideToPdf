import os
from playwright.sync_api import sync_playwright

OUTPUT = "Dragon Quest XI Walkthrough.pdf"


def create_pdf():

    print("Generando PDF...")


    with sync_playwright() as p:

        browser = p.chromium.launch()


        page = browser.new_page()


        page.goto(
            "file://" + os.path.abspath("guide.html"),
            wait_until="domcontentloaded",
            timeout=120000
        )


        # esperar imágenes
        page.wait_for_timeout(5000)


        page.pdf(
            path=OUTPUT,
            format="A4",
            print_background=True,
            prefer_css_page_size=True
        )


        browser.close()


    print("PDF creado")



create_pdf()