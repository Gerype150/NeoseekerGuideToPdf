from bs4 import BeautifulSoup


def clean_html(html):

    soup = BeautifulSoup(
        html,
        "html.parser"
    )


    for e in soup.select("""
        #comments,
        .comments,
        .comment,
        .sidebar,
        .ads,
        .advertisement,
        .ad-container,
        [class*="ad-"],
        [id*="ad"]
    """):
        e.decompose()


    for e in soup.find_all(
        lambda tag:
            tag.name in ["div", "section"]
            and "Advertisement" in tag.get_text()
    ):
        e.decompose()

    styles = soup.select(
        'link[rel="stylesheet"], style'
    )


    title = soup.select_one(
        "#page-title"
    )

    content = soup.select_one(
        "#wiki-content"
    )


    if not content:
        return "", "", ""


    hrs = content.find_all("hr")

    if hrs:
        hrs[-1].decompose()


    clearfix = content.select(
        ".clearfix"
    )

    if clearfix:
        clearfix[-1].decompose()


    for a in content.find_all("a"):

        if a.find("img"):
            a.unwrap()


    css = "\n".join(
        str(x) for x in styles
    )


    return (
        str(title) if title else "",
        str(content),
        css
    )