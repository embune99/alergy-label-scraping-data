import json
import re
import sys
import time
from pathlib import Path
import traceback
from typing import Any, Dict, List, Optional
from urllib.parse import urlparse, urlsplit, urlunsplit, parse_qsl, urlencode

import requests
from bs4 import BeautifulSoup


HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/122.0 Safari/537.36"
    )
}


def fetch_html(url: str, retries: int = 3, timeout: int = 30) -> str:
    last_exc: Exception | None = None

    for attempt in range(retries):
        try:
            resp = requests.get(url, timeout=timeout, headers=HEADERS)
            resp.raise_for_status()
            return resp.text
        except Exception as exc:
            last_exc = exc
            if attempt < retries - 1:
                time.sleep(2)
            else:
                raise last_exc


def extract_product_name(soup: BeautifulSoup) -> Optional[str]:
    h1 = soup.find("h1", id="product-title")
    if not h1:
        return None
    return h1.get_text(strip=True)


def extract_images(soup: BeautifulSoup) -> List[str]:
    images: List[str] = []

    # Only use product carousel thumbnails:
    # div.product-image-carousel__thumbnail-container ... img.image-item
    for img in soup.select(
        "div.product-image-carousel__thumbnail-container img.image-item"
    ):
        src = img.get("src")
        if not src:
            continue

        # Upgrade sw query param to 800 if present
        split = urlsplit(src)
        query_pairs = parse_qsl(split.query, keep_blank_values=True)
        new_query_pairs = []
        for key, value in query_pairs:
            if key == "sw":
                new_query_pairs.append((key, "800"))
            else:
                new_query_pairs.append((key, value))
        new_query = urlencode(new_query_pairs)
        upgraded_src = urlunsplit(
            (split.scheme, split.netloc, split.path, new_query, split.fragment)
        )

        if upgraded_src not in images:
            images.append(upgraded_src)

    return images


def extract_price(soup: BeautifulSoup) -> Optional[str]:
    """
    Extract price from JSON-LD Product schema: offers.price + offers.priceCurrency.
    """
    for script in soup.find_all("script", type="application/ld+json"):
        raw = script.string
        if not raw or not raw.strip():
            continue
        try:
            data = json.loads(raw)
            if not isinstance(data, dict) or data.get("@type") != "Product":
                continue
            offers = data.get("offers")
            if not isinstance(offers, dict):
                continue
            price = offers.get("price")
            price_currency = offers.get("priceCurrency")
            if price is None:
                continue
            price_str = str(price).strip()
            if not price_str:
                continue
            if price_currency:
                return f"{price_str} {str(price_currency).strip()}"
            return price_str
        except (json.JSONDecodeError, TypeError):
            continue
    return None


def extract_description(soup: BeautifulSoup) -> Optional[str]:
    # Only use description from:
    # <div class="s-rich-text" property="description"> ... </div>
    container = soup.select_one("div.s-rich-text[property='description']")
    if not container:
        return None

    text = container.get_text(separator="\n", strip=True)
    return text or None


def extract_raw_ingredients(soup: BeautifulSoup) -> Optional[str]:
    """
    Extract raw ingredients from:
    document.querySelectorAll(".accordion__item.js-accordion-item")[1]
      .querySelectorAll(".accordion__item-content .s-rich-text")[1]
    """
    accordion_items = soup.select(".accordion__item.js-accordion-item")
    if len(accordion_items) < 2:
        return None

    second_item = accordion_items[1]
    rich_text_blocks = second_item.select(".accordion__item-content .s-rich-text")
    if len(rich_text_blocks) < 2:
        return None

    block = rich_text_blocks[1]
    # Check if the block contains "Ingredients" (case-insensitive)
    if "ingredients" not in block.get_text().lower():
        return None

    # Mimic `.lastChild` behaviour: take last child node of this block
    if not block.contents:
        return None

    text = block.get_text()
    # Strip surrounding quotes if present
    match = re.search(r"ingredients\s*:?\s*(.*)", text, re.IGNORECASE)

    if match:
        ingredients_raw = match.group(1).strip()
        cleaned = ingredients_raw.strip().strip('"').strip()
        return cleaned or None
    return None


def extract_product_type(soup: BeautifulSoup) -> Optional[str]:
    """
    Extract product type from:
    document.querySelectorAll(".product-details__important-attributes")[0].children[1]
    """
    blocks = soup.select(".product-details__important-attributes")
    if not blocks:
        return None

    first_block = blocks[0]
    # Direct children only, similar to .children in DOM
    children = first_block.find_all(recursive=False)
    if len(children) < 2:
        return None

    text = children[1].get_text(strip=True)
    return text or None


def extract_product_category(soup: BeautifulSoup) -> Optional[str]:
    """
    Extract product category from:
    document.querySelectorAll(".breadcrumb__list .breadcrumb__list-item .breadcrumb__item span")[1]
    """
    spans = soup.select(".breadcrumb__list .breadcrumb__list-item .breadcrumb__item span")
    if len(spans) < 2:
        return None

    text = spans[1].get_text(strip=True)
    return text or None


def extract_legal_grade(soup: BeautifulSoup) -> Optional[str]:
    """
    Extract legal grade / warning text from:
    document.querySelectorAll("div.s-rich-text[property='description']")[1]
      .nextElementSibling.lastChild.lastChild
    """
    containers = soup.select("div.s-rich-text[property='description']")
    if len(containers) < 2:
        return None

    second = containers[1]
    next_elem = second.find_next_sibling()
    if not next_elem or not next_elem.contents:
        return None

    # First lastChild
    first_last_child = next_elem.contents[-1]
    # Then lastChild of that node (if it has children)
    if getattr(first_last_child, "contents", None):
        target = first_last_child.contents[-1]
    else:
        target = first_last_child

    text = getattr(target, "get_text", lambda **_: str(target))(strip=True)
    cleaned = text.strip().strip('"').strip()
    return cleaned or None


def extract_sku(soup: BeautifulSoup, url: str) -> Optional[str]:
    """
    Extract sku from:
    - <script type="application/ld+json"> Product schema (preferred)
    - Fallback: numeric id at end of product URL before .html
      e.g. ...-120874327.html -> 120874327
    """
    for script in soup.find_all("script", type="application/ld+json"):
        raw = script.string
        if not raw or not raw.strip():
            continue
        try:
            data = json.loads(raw)
            if isinstance(data, dict):
                sku = data.get("sku")
                if sku is not None:
                    return str(sku)
        except (json.JSONDecodeError, TypeError):
            continue

    parsed = urlparse(url)
    last_segment = parsed.path.rstrip("/").split("/")[-1]
    if last_segment.endswith(".html"):
        last_segment = last_segment[: -len(".html")]
    parts = last_segment.split("-")
    if parts:
        candidate = parts[-1]
        if candidate.isdigit():
            return candidate

    return None


def extract_product_data(url: str) -> Dict[str, Any]:
    html = fetch_html(url)
    soup = BeautifulSoup(html, "html.parser")

    product_name = extract_product_name(soup)
    images = extract_images(soup)
    price = extract_price(soup)
    description = extract_description(soup)
    raw_ingredients = extract_raw_ingredients(soup)
    product_type = extract_product_type(soup)
    product_category = extract_product_category(soup)
    legal_grade = extract_legal_grade(soup)
    sku = extract_sku(soup, url)

    parsed = urlparse(url)
    website = parsed.netloc

    return {
        "product_information": {
            "product_url": url,
            "images": images,
            "website": website,
            "product_name": product_name,
            "price": price,
            "description": description,
        },
        "inferred_information": {
            "raw_ingredients": raw_ingredients,
            "product_type": product_type,
            "product_category": product_category,
            "legal_grade": legal_grade,
        },
        "additional_information": {
            "id": sku,
        },
    }


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python etos_product_title.py <product_url> [output_dir]")
        sys.exit(1)

    url = sys.argv[1]
    output_dir = Path(sys.argv[2]) if len(sys.argv) >= 3 else Path("products")

    try:
        product = extract_product_data(url)
    except Exception as exc:
        print(f"Error while fetching or parsing page: {exc}")
        sys.exit(1)

    sku = product.get("additional_information", {}).get("id")
    if not sku:
        print("Could not determine product id (sku) to name output file.")
        sys.exit(1)

    output_dir.mkdir(parents=True, exist_ok=True)
    output_path = output_dir / f"{sku}.json"

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(product, f, ensure_ascii=False, indent=2)

    print(f"Saved product to {output_path}")


if __name__ == "__main__":
    main()

