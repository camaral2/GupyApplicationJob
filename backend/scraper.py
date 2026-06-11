import json
import re
from typing import Any
from urllib.parse import quote, urljoin

from bs4 import BeautifulSoup


def _normalize_text(value: Any) -> str:
    if value is None:
        return ""
    if isinstance(value, (list, tuple, set)):
        return " ".join(str(item) for item in value)
    return str(value).strip()


def _normalize_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, list):
        items = []
        for item in value:
            text = _normalize_text(item)
            if text:
                items.append(text)
        return items
    if isinstance(value, str):
        parts = [part.strip() for part in re.split(r"\n|;|\|", value) if part.strip()]
        return parts
    return [_normalize_text(value)]


def _find_value(obj: Any, keys: set[str]) -> Any:
    if isinstance(obj, dict):
        for key, value in obj.items():
            if key in keys:
                return value
            found = _find_value(value, keys)
            if found is not None:
                return found
    elif isinstance(obj, list):
        for item in obj:
            found = _find_value(item, keys)
            if found is not None:
                return found
    return None


def _extract_from_next_data(soup: BeautifulSoup) -> dict[str, Any]:
    script = soup.find("script", id="__NEXT_DATA__")
    if not script:
        return {}
    try:
        payload = json.loads(script.string or "")
    except (TypeError, json.JSONDecodeError):
        return {}
    title = _find_value(payload, {"name", "title", "jobTitle"})
    description = _find_value(payload, {"jobDescription", "description", "summary", "text"})
    responsibilities = _find_value(payload, {"responsibilities", "responsibility"})
    requirements = _find_value(payload, {"requirements", "requirement"})
    apply_url = _find_value(payload, {"applyUrl", "apply_url"})
    return {
        "title": _normalize_text(title),
        "description": _normalize_text(description),
        "responsibilities": _normalize_list(responsibilities),
        "requirements": _normalize_list(requirements),
        "apply_url": _normalize_text(apply_url),
    }


def _extract_text_items(block: Any) -> list[str]:
    if not block:
        return []
    items = [item.get_text(" ", strip=True) for item in block.find_all("li") if item.get_text(" ", strip=True)]
    if items:
        return items
    text = _normalize_text(block.get_text(" ", strip=True))
    if not text:
        return []
    return [part.strip() for part in re.split(r"\n|;", text) if part.strip()]


def _extract_apply_url(soup: BeautifulSoup, base_url: str | None = None) -> str:
    for selector in [
        'a[href*="/apply"]',
        'a[href*="apply?"]',
        'a[data-testid="job-cta-link"]',
        'a[href*="candidates/jobs"]',
    ]:
        for link in soup.select(selector):
            href = _normalize_text(link.get("href"))
            if not href:
                continue
            if href.startswith(("http://", "https://")):
                return href
            if base_url:
                return urljoin(base_url, href)
            return href
    return ""


def _extract_from_html(soup: BeautifulSoup, base_url: str | None = None) -> dict[str, Any]:
    title = _normalize_text(soup.title.get_text(strip=True)) if soup.title else ""
    if not title:
        title = _normalize_text(soup.find(["h1", "h2"]).get_text(strip=True)) if soup.find(["h1", "h2"]) else ""

    description = ""
    for selector in [".job-description", ".description", ".summary", "p"]:
        node = soup.select_one(selector)
        if node:
            description = _normalize_text(node.get_text(" ", strip=True))
            break

    responsibilities = []
    for selector in [".responsibilities", ".responsibility", "ul"]:
        block = soup.select_one(selector)
        if block:
            responsibilities = _extract_text_items(block)
            if responsibilities:
                break

    requirements = []
    for selector in [".requirements", ".requirement", "ul"]:
        block = soup.select_one(selector)
        if block:
            requirements = _extract_text_items(block)
            if requirements:
                break

    return {
        "title": title,
        "description": description,
        "responsibilities": responsibilities,
        "requirements": requirements,
        "apply_url": _extract_apply_url(soup, base_url),
    }


def _normalize_url(href: str, base_url: str | None = None) -> str:
    href = _normalize_text(href)
    if not href:
        return ""
    if href.startswith(("http://", "https://")):
        return href
    if base_url:
        return urljoin(base_url, href)
    return href


def _extract_job_title_and_company(aria_label: str) -> tuple[str, str]:
    aria_label = _normalize_text(aria_label)
    if not aria_label:
        return "", ""

    if aria_label.lower().startswith("ir para vaga"):
        rest = aria_label[len("Ir para vaga") :].strip()
        if rest.lower().startswith("vaga"):
            rest = rest[len("vaga") :].strip()

        match = re.search(r"^(.*?)\s+da empresa\s+(.+)$", rest, re.IGNORECASE)
        if match:
            title = match.group(1).strip()
            company = match.group(2).strip()
            company = re.split(r"\s+na cidade\s+|\s+publicada\s+|\s+publicada há|\s+Essa vaga|\s+Esta empresa", company, maxsplit=1, flags=re.IGNORECASE)[0].strip()
            return title, company

    return aria_label, ""


def build_gupy_search_url(term: str, page: int = 1, workplace_types: str | None = None) -> str:
    normalized_term = " ".join(str(term or "product owner").split()).strip() or "product owner"
    encoded_term = quote(normalized_term)
    page_number = max(1, int(page or 1))
    base_url = f"https://portal.gupy.io/job-search/term={encoded_term}&workplaceTypes[]=remote"
    if page_number > 1:
        return f"{base_url}?page={page_number}"
    return base_url


def parse_gupy_search_results(html: str, base_url: str | None = None) -> list[dict[str, Any]]:
    soup = BeautifulSoup(html, "html.parser")
    results: list[dict[str, Any]] = []
    seen_urls: set[str] = set()

    for link in soup.find_all("a", href=True):
        href = _normalize_url(link.get("href"), base_url)
        aria_label = _normalize_text(link.get("aria-label"))
        if not href or not aria_label.lower().startswith("ir para vaga"):
            continue
        if "/job/" not in href.lower():
            continue
        if href in seen_urls:
            continue

        title, company = _extract_job_title_and_company(aria_label)
        if not title:
            continue

        seen_urls.add(href)
        results.append(
            {
                "title": title,
                "company": company,
                "url": href,
                "source_url": base_url or "",
            }
        )

    return results


def parse_gupy_page(html: str, url: str | None = None) -> dict[str, Any]:
    soup = BeautifulSoup(html, "html.parser")

    data = _extract_from_next_data(soup)
    if data and (data.get("title") or data.get("description") or data.get("responsibilities") or data.get("requirements")):
        result = {
            "title": data.get("title", ""),
            "description": data.get("description", ""),
            "responsibilities": data.get("responsibilities", []),
            "requirements": data.get("requirements", []),
            "apply_url": data.get("apply_url", ""),
            "source_url": url or "",
        }
        if not result["apply_url"]:
            result["apply_url"] = _extract_apply_url(soup, url)
        return result

    fallback = _extract_from_html(soup, url)
    fallback["source_url"] = url or ""
    return fallback
