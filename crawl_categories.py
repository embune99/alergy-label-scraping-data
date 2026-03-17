import json
from pathlib import Path
from typing import List
from urllib.parse import urlparse, urljoin

from bs4 import BeautifulSoup

from crawl_each_product import fetch_html, extract_product_data


BASE_URL = "https://www.etos.nl"
PAGE_SIZE = 100


def read_category_urls(path: Path) -> List[str]:
    lines = path.read_text(encoding="utf-8").splitlines()
    return [line.strip() for line in lines if line.strip()]


def category_slug_from_url(url: str) -> str:
    parsed = urlparse(url)
    # Take the last non-empty segment of the path as slug
    segments = [seg for seg in parsed.path.split("/") if seg]
    return segments[-1] if segments else "unknown"


def _normalize_product_href(category_url: str, href: str) -> str:
    """
    Turn a product <a href> (relative or absolute) into an absolute URL.
    """
    if href.startswith("http://") or href.startswith("https://"):
        return href
    if href.startswith("/"):
        return urljoin(BASE_URL, href)
    return urljoin(category_url, href)


def fetch_product_urls_page(category_url: str, start: int) -> List[str]:
    """
    Fetch ONE async page of product tiles for this category:
    ?async=true&start=<start>&sz=100&isLoadMore=true
    and return unique product URLs in page order.
    """
    page_url = (
        category_url.rstrip("/")
        + f"/?async=true&start={start}&sz={PAGE_SIZE}&isLoadMore=true"
    )
    print(f"  Loading page: {page_url}")
    html = fetch_html(page_url)
    soup = BeautifulSoup(html, "html.parser")

    urls: List[str] = []
    seen: set[str] = set()
    for a in soup.select(".c-product-tile a"):
        href = a.get("href")
        if not href:
            continue
        full = _normalize_product_href(category_url, href)
        if full in seen:
            continue
        seen.add(full)
        urls.append(full)

    return urls


def main() -> None:
    # Default inputs so we can just run: python crawl_categories.py
    category_file = Path("category.txt")
    products_root = Path("products")

    category_urls = read_category_urls(category_file)

    for category_url in category_urls:
        slug = category_slug_from_url(category_url)
        category_dir = products_root / slug
        category_dir.mkdir(parents=True, exist_ok=True)
        urls_file = category_dir / "_urls.txt"
        meta_path = category_dir / "_meta.json"

        # Load existing URLs (if any), preserving order
        existing_urls: List[str] = []
        if urls_file.exists():
            existing_urls = [
                line.strip()
                for line in urls_file.read_text(encoding="utf-8").splitlines()
                if line.strip()
            ]
        existing_count = len(existing_urls)

        # Load previous meta to know crawled_product_urls and processed_count
        previous_crawled: int | None = None
        previous_processed: int = 0
        if meta_path.exists():
            try:
                prev_meta = json.loads(meta_path.read_text(encoding="utf-8"))
                if isinstance(prev_meta, dict):
                    prev_crawled_val = prev_meta.get("crawled_product_urls")
                    if isinstance(prev_crawled_val, int):
                        previous_crawled = prev_crawled_val
                    prev_processed_val = prev_meta.get("processed_count")
                    if isinstance(prev_processed_val, int) and prev_processed_val >= 0:
                        previous_processed = prev_processed_val
            except Exception:
                previous_crawled = None
                previous_processed = 0

        print(f"Crawling category: {category_url} -> {slug}")
        product_urls: list[str] = []

        # If we already have enough URLs according to previous crawled count, skip URL discovery
        if previous_crawled is not None and existing_count >= previous_crawled:
            print(
                f"  Skipping URL discovery: existing URLs ({existing_count}) "
                f">= previous crawled ({previous_crawled})"
            )
            # Reuse URLs exactly as stored in _urls.txt (original order)
            product_urls = existing_urls
        else:
            # Discover URLs via async pages, appending new ones to _urls.txt
            product_urls_list: List[str] = list(existing_urls)
            product_urls_seen: set[str] = set(existing_urls)

            # Align start to PAGE_SIZE boundary if resuming partially
            if existing_count == 0:
                start = 0
            else:
                start = (existing_count // PAGE_SIZE) * PAGE_SIZE

            with urls_file.open("a", encoding="utf-8") as uf:
                while True:
                    page_urls = fetch_product_urls_page(category_url, start)
                    if not page_urls:
                        # No products returned, stop
                        break

                    print(
                        f"    Found {len(page_urls)} product URLs on page starting {start}"
                    )

                    for u in page_urls:
                        if u in product_urls_seen:
                            continue
                        uf.write(u + "\n")
                        product_urls_seen.add(u)
                        product_urls_list.append(u)

                    # If fewer than PAGE_SIZE URLs, this is the last page
                    if len(page_urls) < PAGE_SIZE:
                        break

                    start += PAGE_SIZE

            product_urls = product_urls_list

        # Initialize metadata for the category (using latest known crawl count)
        processed_count = min(previous_processed, len(product_urls))
        crawled_count = len(product_urls)
        meta = {
            "category_url": category_url,
            "slug": slug,
            "crawled_product_urls": crawled_count,
            "processed_count": processed_count,
        }
        with open(meta_path, "w", encoding="utf-8") as f:
            json.dump(meta, f, ensure_ascii=False, indent=2)

        # Resume from where we left off last time
        for index, product_url in enumerate(
            product_urls[processed_count:], start=processed_count
        ):
            try:
                product = extract_product_data(product_url)
            except Exception as exc:
                print(f"    Error fetching {product_url}: {exc}")
                continue

            sku = product.get("additional_information", {}).get("id")
            if not sku:
                print(f"    Skipping {product_url}: missing sku")
                continue

            output_path = category_dir / f"{sku}.json"
            with open(output_path, "w", encoding="utf-8") as f:
                json.dump(product, f, ensure_ascii=False, indent=2)

            print(f"    Saved {output_path}")

            # After each successful product, update processed_count in meta
            processed_count = index + 1
            meta["processed_count"] = processed_count
            with open(meta_path, "w", encoding="utf-8") as f:
                json.dump(meta, f, ensure_ascii=False, indent=2)


if __name__ == "__main__":
    main()

