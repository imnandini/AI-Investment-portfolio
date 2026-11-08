"""Bounded, public company-news RSS. Only company names leave the application."""
from collections import OrderedDict
import asyncio
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
import html
import re
from urllib.parse import parse_qs, urlsplit
from xml.etree import ElementTree as ET

import httpx

CACHE = OrderedDict()
MAX_BYTES = 1_000_000
WINDOW = timedelta(days=30)


def utcnow():
    return datetime.now(timezone.utc)


def text(value, limit=400):
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]*>", " ", value or ""))).strip()[:limit]


def public_link(value):
    try:
        url = urlsplit(value or "")
        if url.hostname in ("www.bing.com", "bing.com"):
            target = parse_qs(url.query).get("url", [None])[0]
            if target:
                return public_link(target) if urlsplit(target).hostname not in ("www.bing.com", "bing.com") else None
        if url.scheme not in ("http", "https") or not url.hostname or url.username or url.password:
            return None
        return value
    except ValueError:
        return None


def company_terms(name):
    name = re.sub(r"\([^)]*\)", " ", name)
    terms = re.findall(r"[a-z0-9]+", name.casefold())
    while terms and terms[-1] in {"limited", "ltd", "inc", "incorporated", "corporation", "corp", "plc", "pvt"}:
        terms.pop()
    return terms


def parse_feed(content, name, checked_at):
    if len(content) > MAX_BYTES or b"<!DOCTYPE" in content.upper() or b"<!ENTITY" in content.upper():
        raise ValueError("unsupported feed")
    root = ET.fromstring(content)
    if root.tag != "rss" or root.find("channel") is None:
        raise ValueError("unsupported feed")
    terms = company_terms(name)
    if not terms:
        return []
    phrase = " ".join(terms)
    articles, seen = [], set()
    for item in root.findall("./channel/item")[:150]:
        title = text(item.findtext("title"), 250)
        if re.search(r"\b(?:share|stock) price (?:live(?: updates?)?|highlights|history|today)\b", title, re.I):
            continue
        # Require the company phrase in the headline, not just search ranking.
        words = " ".join(re.findall(r"[a-z0-9]+", title.casefold()))
        if not re.search(r"(?<!\w)" + re.escape(phrase) + r"(?!\w)", words):
            continue
        link = public_link(item.findtext("link"))
        try:
            published = parsedate_to_datetime(item.findtext("pubDate") or "")
            if published.utcoffset() is None:
                continue
            published = published.astimezone(timezone.utc)
        except (ValueError, TypeError, OverflowError):
            continue
        if not link or published < checked_at - WINDOW or published > checked_at + timedelta(minutes=5):
            continue
        source = next((child for child in item if child.tag.rsplit("}", 1)[-1].lower() == "source"), None)
        publisher = text(source.text, 100) if source is not None else urlsplit(link).hostname
        # Google appends the publisher to its headline. Retain the attribution separately.
        if publisher and title.endswith(" - " + publisher):
            title = title[:-(len(publisher) + 3)]
        fingerprint = re.sub(r"\W+", "", title.casefold())
        if not fingerprint or fingerprint in seen:
            continue
        seen.add(fingerprint)
        articles.append({"id": "", "title": title, "url": link, "publisher": publisher or "Publisher unavailable",
                         "published_at": published.isoformat()})
    articles.sort(key=lambda item: item["published_at"], reverse=True)
    return [{**article, "id": f"news-{index}"} for index, article in enumerate(articles[:8], 1)]


async def fetch_feed(url, params):
    async with asyncio.timeout(5):
        async with httpx.AsyncClient(timeout=httpx.Timeout(4), follow_redirects=False, headers={"User-Agent": "InvestmentResearchCopilot/1.0"}) as client:
            async with client.stream("GET", url, params=params) as response:
                response.raise_for_status()
                content = bytearray()
                async for chunk in response.aiter_bytes():
                    content.extend(chunk)
                    if len(content) > MAX_BYTES:
                        raise ValueError("oversized feed")
    return bytes(content)


async def company_news(name, currency="INR"):
    checked_at = utcnow()
    key = (name.casefold().strip(), currency)
    cached = CACHE.get(key)
    if cached and cached[0] > checked_at:
        CACHE.move_to_end(key)
        return {**cached[1], "cached": True}
    query_name = " ".join(company_terms(name))
    if not query_name or re.fullmatch(r"inds\d+", query_name):
        return {"status": "unavailable", "articles": [], "checked_at": checked_at.isoformat(), "cached": False,
                "note": "A company name is needed for news matching. Reimport this holding to refresh its name."}
    region = "en-IN" if currency == "INR" else "en-US"
    topics = "(earnings OR profit OR revenue OR orders OR debt OR business OR outlook)"
    providers = [
        ("Bing News RSS", "https://www.bing.com/news/search", {"q": f'"{query_name}" {topics}', "format": "rss", "setlang": "en", "mkt": region}),
        ("Google News RSS", "https://news.google.com/rss/search", {"q": f'"{query_name}" {topics} when:30d', "hl": region, "gl": "IN" if currency == "INR" else "US", "ceid": "IN:en" if currency == "INR" else "US:en"}),
    ]
    succeeded, articles, provider = False, [], None
    for label, url, params in providers:
        try:
            articles = parse_feed(await fetch_feed(url, params), name, checked_at)
            succeeded = True
            provider = label
            if articles:
                break
        except (httpx.HTTPError, ValueError, ET.ParseError, TimeoutError):
            continue
    result = {"status": "available" if articles else "empty" if succeeded else "unavailable", "articles": articles,
              "provider": provider, "checked_at": checked_at.isoformat(), "cached": False,
              "note": "Headlines matching this company from the last 30 days; full articles and company identity are not independently verified." if articles else "No recent company-matched headlines were returned." if succeeded else "News feeds are temporarily unavailable. Retry shortly."}
    CACHE[key] = (checked_at + timedelta(minutes=10 if succeeded else 1), result)
    CACHE.move_to_end(key)
    while len(CACHE) > 256:
        CACHE.popitem(last=False)
    return result
