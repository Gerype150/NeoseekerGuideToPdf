import os
from playwright.sync_api import sync_playwright


OUTPUT = "Dragon Quest XI Walkthrough.pdf"


def create_pdf():

    if not os.path.exists("guide.html"):
        print("No existe guide.html")
        return


    with sync_playwright() as p:

        browser = p.chromium.launch()

        page = browser.new_page()

        page.goto(
            "file://" + os.path.abspath("guide.html")
        )

        page.pdf(
            path=OUTPUT,
            format="A4",
            print_background=True,
            outline=True
        )

        browser.close()


print("Generando PDF...")

create_pdf()

print("Terminado:", OUTPUT)