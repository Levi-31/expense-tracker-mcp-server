from pathlib import Path

BASE_DIR = Path(__file__).parent.parent

CATEGORIES_PATH = BASE_DIR / "categories.json"


def get_categories():

    with open(
        CATEGORIES_PATH,
        "r",
        encoding="utf-8",
    ) as f:

        return f.read()