from bs4 import BeautifulSoup


def clean_html(html):

    soup = BeautifulSoup(
        html,
        "html.parser"
    )

    for e in soup.find_all("script"):
        if "primis" in str(e).lower():
            e.parent.decompose()

    for e in soup.select("""
        #comments,
        .comments,
        .comment,
        .sidebar,
        .ads,
        .advertisement,
        .ad-container,
        .section-vu,
        [class*="ad-"],
        [id*="ad"],
        [id*="inline"]
    """):
        e.decompose()

     # anuncios Primis
    for script in soup.find_all("script"):
        if "primis" in str(script).lower():
            if script.parent:
                script.parent.decompose()


    # contenedores que contienen texto Advertisement
    for div in soup.find_all("div"):
        if "Advertisement" in div.get_text(" ", strip=True):
            div.decompose()


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
    
    # limpieza final de anuncios por contenido/atributos
    for div in list(content.find_all("div")):

        attrs = div.attrs or {}

        classes = " ".join(
            attrs.get("class", [])
        )

        div_id = attrs.get(
            "id",
            ""
        )

        texto = div.get_text(
            " ",
            strip=True
        ).lower()


        if (
            "section-vu" in classes
            or "sticky" in classes
            or "inline" in div_id.lower()
            or "primis" in str(div).lower()
            or "advertisement" in texto
        ):
            div.decompose()

    return (
        str(title) if title else "",
        str(content),
        css
    )