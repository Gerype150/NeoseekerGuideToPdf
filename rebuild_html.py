import os
import hashlib
from bs4 import BeautifulSoup

from clean_html import clean_html


CACHE = "cache"
OUTPUT = "guide.html"


def cache_files():

    files = []

    for f in os.listdir(CACHE):
        if f.endswith(".html"):
            files.append(
                os.path.join(CACHE, f)
            )

    return sorted(files)


def rebuild():

    chapters = cache_files()

    print(f"{len(chapters)} páginas encontradas en caché")

    output = []


    output.append("""
<!DOCTYPE html>
<html>
<head>

<meta charset="utf-8">

<style>

@media print {

.chapter:not(:first-of-type) {
    page-break-before: always;
}

}

* {
    -webkit-print-color-adjust: exact !important;
    print-color-adjust: exact !important;
}


body {
    font-family: Arial, sans-serif;
}


img {
    max-width:100%;
    page-break-inside: avoid;
}
a {
    color: inherit;
    text-decoration: none;
}


table {
    border-collapse: collapse;
}


td, th {
    border: 1px solid #999;
}


div, section {
    box-sizing: border-box;
}


* {
    -webkit-print-color-adjust: exact !important;
    print-color-adjust: exact !important;
}

table,
figure,
pre {
    page-break-inside: avoid;
}


</style>

</head>

<body>

<h1>Neoseeker Walkthrough</h1>

""")


    for i, file in enumerate(chapters):

        print(f"Procesando {i+1}/{len(chapters)}")


        with open(
            file,
            encoding="utf-8"
        ) as f:
            html = f.read()


        title, content = clean_html(html)


        output.append(f"""

<section class="chapter">

<h1>{title}</h1>

{content}

</section>

""")


    output.append("""
</body>
</html>
""")


    with open(
        OUTPUT,
        "w",
        encoding="utf-8"
    ) as f:
        f.write(
            "".join(output)
        )


    print("Generado:", OUTPUT)



rebuild()