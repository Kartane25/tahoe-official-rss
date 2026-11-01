
import re
from datetime import datetime, timezone
from email.utils import format_datetime
from urllib.parse import urljoin
import xml.etree.ElementTree as ET

import requests
from bs4 import BeautifulSoup

BASE = "https://knightmonstershockey.com"
NEWS_URL = BASE + "/news"
FEED_URL = "https://kartane25.github.io/tahoe-official-rss/feed.xml"

session = requests.Session()
session.headers.update({
    "User-Agent": "Mozilla/5.0 (compatible; TahoeNewsRSS/1.0)"
})

def get_soup(url):
    response = session.get(url, timeout=30)
    response.raise_for_status()
    return BeautifulSoup(response.text, "html.parser")

def meta(soup, key):
    tag = soup.find("meta", property=key)
    if not tag:
        tag = soup.find("meta", attrs={"name": key})
    return tag.get("content", "").strip() if tag else ""

def make_feed():
    listing = get_soup(NEWS_URL)
    links = []
    seen = set()

    for a in listing.find_all("a", href=True):
        url = urljoin(BASE, a["href"]).split("?")[0]
        if re.search(r"/news/\d{4}/\d{2}/[^/]+$", url):
            if url not in seen and url.startswith(BASE):
                seen.add(url)
                links.append(url)

    if not links:
        raise RuntimeError("No official Tahoe news articles found.")

    rss = ET.Element("rss", {
        "version": "2.0",
        "xmlns:media": "http://search.yahoo.com/mrss/"
    })
    channel = ET.SubElement(rss, "channel")

    for name, value in [
        ("title", "Tahoe Knight Monsters | Official News"),
        ("link", NEWS_URL),
        ("description", "Official Tahoe Knight Monsters team news"),
        ("language", "en-us"),
        ("ttl", "30"),
        ("atom:link", "")
    ]:
        if name == "atom:link":
            continue
        ET.SubElement(channel, name).text = value

    count = 0

    for url in links[:15]:
        try:
            soup = get_soup(url)
            heading = soup.find("h1")
            title = meta(soup, "og:title") or (
                heading.get_text(" ", strip=True) if heading else ""
            )
            image = meta(soup, "og:image")
            description = meta(soup, "og:description")

            if not description:
                for p in soup.find_all("p"):
                    content = p.get_text(" ", strip=True)
                    if len(content) > 90:
                        description = content
                        break

            if not title:
                continue

            
            # Extract the actual publication date displayed above the article
            published = None
            date_pattern = re.compile(
                r"(Monday|Tuesday|Wednesday|Thursday|Friday|Saturday|Sunday),?\s+"
                r"(January|February|March|April|May|June|July|August|"
                r"September|October|November|December)\s+"
                r"(\d{1,2})(?:st|nd|rd|th)?",
                re.IGNORECASE
            )

            heading = soup.find("h1")
            date_text = heading.find_previous(
                string=date_pattern
            ) if heading else None

            year_match = re.search(r"/news/(\d{4})/", url)

            if date_text and year_match:
                match = date_pattern.search(str(date_text))
                if match:
                    month_day = f"{match.group(2)} {match.group(3)}"
                    year = year_match.group(1)
                    published = datetime.strptime(
                        f"{month_day} {year}", "%B %d %Y"
                    ).replace(tzinfo=timezone.utc)


            
            item = ET.SubElement(channel, "item")
            ET.SubElement(item, "title").text = title
            ET.SubElement(item, "link").text = url
            ET.SubElement(item, "guid", isPermaLink="true").text = url
            ET.SubElement(item, "description").text = description[:700]

            if published:
                ET.SubElement(item, "pubDate").text = format_datetime(published)


            if image:
                image = urljoin(BASE, image)
                ET.SubElement(item, "media:content", {
                    "url": image,
                    "medium": "image"
                })

            count += 1

        except Exception as exc:
            print(f"Unable to process {url}: {exc}")

    if not count:
        raise RuntimeError("No articles could be processed.")

    ET.register_namespace(
        "media", "http://search.yahoo.com/mrss/"
    )
    tree = ET.ElementTree(rss)
    ET.indent(tree, space="  ")
    tree.write("feed.xml", encoding="utf-8", xml_declaration=True)

    print(f"Generated feed.xml with {count} official articles.")

if __name__ == "__main__":
    make_feed()
