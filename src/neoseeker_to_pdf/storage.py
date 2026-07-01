import os


def read_text(path: str) -> str:
    with open(path, encoding="utf-8") as file:
        return file.read()


def write_text(path: str, content: str) -> None:
    directory = os.path.dirname(path)
    if directory:
        os.makedirs(directory, exist_ok=True)

    with open(path, "w", encoding="utf-8") as file:
        file.write(content)
