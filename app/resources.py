import json
from pathlib import Path

BASE_DIR = Path(__file__).parent.parent
CATEGORIES_PATH = BASE_DIR / "category.json"

_categories_cache = None


def get_categories():

    with open(
        CATEGORIES_PATH,
        "r",
        encoding="utf-8",
    ) as f:

        return f.read()


def load_categories() -> dict:
    global _categories_cache
    if _categories_cache is None:
        with open(CATEGORIES_PATH, "r", encoding="utf-8") as f:
            _categories_cache = json.load(f)
    return _categories_cache


def normalize_and_validate(category: str, subcategory: str) -> tuple[str, str]:
    cats = load_categories()
    
    # Normalize category: strip and lowercase, convert spaces to underscores
    norm_cat = category.strip().lower().replace(" ", "_")
    if norm_cat not in cats:
        matched_cat = None
        for k in cats.keys():
            if k.lower().replace(" ", "_") == norm_cat:
                matched_cat = k
                break
        if matched_cat:
            norm_cat = matched_cat
        else:
            raise ValueError(
                f"Invalid category: '{category}'. Allowed categories: {list(cats.keys())}"
            )
            
    allowed_subcats = cats[norm_cat]
    
    # Normalize subcategory
    norm_sub = subcategory.strip().lower().replace(" ", "_")
    if norm_sub not in allowed_subcats:
        matched_sub = None
        for s in allowed_subcats:
            if s.lower().replace(" ", "_") == norm_sub:
                matched_sub = s
                break
        if matched_sub:
            norm_sub = matched_sub
        else:
            raise ValueError(
                f"Invalid subcategory: '{subcategory}' for category '{norm_cat}'. "
                f"Allowed subcategories: {allowed_subcats}"
            )
            
    return norm_cat, norm_sub