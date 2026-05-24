from __future__ import annotations

import argparse
import csv
import html
import re
import time
from dataclasses import dataclass
from html.parser import HTMLParser
from pathlib import Path
from typing import Iterable

import requests


BLOG_UID = "1215172700"
CATEGORY_ID = "10"
LESSON_PREFIX = "\u6559\u4f60\u7092\u80a1\u7968"
DEFAULT_OUTPUT_DIR = Path("data") / "chanzhongshuochan_lessons"
BASE36_ALPHABET = "0123456789abcdefghijklmnopqrstuvwxyz"
EASTMONEY_SINA_INDEX_URL = "https://blog.eastmoney.com/lsg8810/blog_217642958.html"
CHZH_MIRROR_INDEX_URL = "https://chzh1019.github.io/chzhshch/"


@dataclass(frozen=True)
class LessonLink:
    number: int
    list_title: str
    url: str


@dataclass(frozen=True)
class LessonArticle:
    number: int
    title: str
    published_at: str
    url: str
    body: str


class SinaContentParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.skip_depth = 0
        self.last_was_break = True

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        tag = tag.lower()
        if tag in {"script", "style"}:
            self.skip_depth += 1
            return
        if self.skip_depth:
            return
        if tag in {"p", "div", "br", "tr", "li"}:
            self._break()
        elif tag == "img":
            attr_map = dict(attrs)
            src = attr_map.get("real_src") or attr_map.get("src")
            if src:
                if src.startswith("//"):
                    src = "https:" + src
                alt = attr_map.get("alt") or "image"
                self.parts.append(f"![{alt}]({src})")
                self.last_was_break = False

    def handle_endtag(self, tag: str) -> None:
        tag = tag.lower()
        if tag in {"script", "style"} and self.skip_depth:
            self.skip_depth -= 1
            return
        if self.skip_depth:
            return
        if tag in {"p", "div", "tr", "li"}:
            self._break()

    def handle_data(self, data: str) -> None:
        if self.skip_depth:
            return
        text = html.unescape(data).replace("\xa0", " ")
        text = re.sub(r"[ \t\r\f\v]+", " ", text)
        if text.strip():
            self.parts.append(text.strip())
            self.last_was_break = False

    def _break(self) -> None:
        if not self.last_was_break:
            self.parts.append("\n\n")
            self.last_was_break = True

    def text(self) -> str:
        text = "".join(self.parts)
        text = re.sub(r"\n{3,}", "\n\n", text)
        lines = [line.strip() for line in text.splitlines()]
        return "\n".join(line for line in lines).strip()


def make_session() -> requests.Session:
    session = requests.Session()
    session.trust_env = False
    session.headers.update(
        {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/125.0 Safari/537.36"
            ),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "zh-CN,zh;q=0.9,en;q=0.8",
            "Referer": "https://blog.sina.com.cn/",
        }
    )
    return session


def fetch_text(session: requests.Session, url: str, timeout: int) -> str:
    response = session.get(url, timeout=timeout)
    response.raise_for_status()
    response.encoding = "utf-8"
    return response.text


def absolutize_url(url: str) -> str:
    if url.startswith("//"):
        return "https:" + url
    if url.startswith("http://"):
        return "https://" + url[len("http://") :]
    return url


def article_suffix(url: str) -> str | None:
    match = re.search(r"blog_486e105c010([0-9a-z]{5})\.html", url)
    return match.group(1) if match else None


def base36_to_int(value: str) -> int:
    result = 0
    for char in value:
        result = result * 36 + BASE36_ALPHABET.index(char)
    return result


def int_to_base36(value: int, width: int = 5) -> str:
    chars: list[str] = []
    for _ in range(width):
        value, remainder = divmod(value, 36)
        chars.append(BASE36_ALPHABET[remainder])
    return "".join(reversed(chars))


def clean_inline_html(value: str) -> str:
    return html.unescape(re.sub(r"<.*?>", "", value, flags=re.S)).strip()


def normalize_lesson_title(title: str) -> str:
    return re.sub(rf"{LESSON_PREFIX}\s+(\d+)", rf"{LESSON_PREFIX}\1", title).strip()


def discover_lessons(
    session: requests.Session,
    max_pages: int,
    delay: float,
    timeout: int,
) -> list[LessonLink]:
    lessons: dict[int, LessonLink] = {}
    link_pattern = re.compile(r'<a[^>]*href="([^"]+)"[^>]*>(.*?)</a>', re.S | re.I)
    lesson_pattern = re.compile(rf"{LESSON_PREFIX}\s*(\d+)")

    for page in range(1, max_pages + 1):
        url = f"https://blog.sina.com.cn/s/articlelist_{BLOG_UID}_{CATEGORY_ID}_{page}.html"
        text = fetch_text(session, url, timeout)
        if "articleList" not in text and page > 1:
            break

        page_hits = 0
        for href, raw_title in link_pattern.findall(text):
            title = clean_inline_html(raw_title)
            match = lesson_pattern.search(title)
            if not match:
                continue
            number = int(match.group(1))
            lessons[number] = LessonLink(number=number, list_title=title, url=absolutize_url(href))
            page_hits += 1

        print(f"page {page}: found {page_hits} lesson links")
        if 1 in lessons and len(lessons) >= 108:
            break
        time.sleep(delay)

    return [lessons[key] for key in sorted(lessons)]


def extract_title(page_html: str) -> str:
    title_match = re.search(r'<h2[^>]*class\s*=\s*["\']?[^>]*titName[^>]*>(.*?)</h2>', page_html, re.S | re.I)
    if not title_match:
        title_match = re.search(r"<title>(.*?)</title>", page_html, re.S | re.I)
    title = clean_inline_html(title_match.group(1)) if title_match else ""
    return normalize_lesson_title(title.replace("_新浪博客", ""))


def recover_from_chzh_mirror(
    session: requests.Session,
    links: list[LessonLink],
    expected: int,
    timeout: int,
) -> list[LessonLink]:
    lessons = {link.number: link for link in links}
    missing = [number for number in range(1, expected + 1) if number not in lessons]
    if not missing:
        return [lessons[key] for key in sorted(lessons)]

    try:
        page_html = fetch_text(session, CHZH_MIRROR_INDEX_URL, timeout)
    except requests.RequestException as exc:
        print(f"chzh mirror index unavailable: {exc}")
        return [lessons[key] for key in sorted(lessons)]

    link_pattern = re.compile(r'<a[^>]+href\s*=\s*["\']?([^"\'\s>]+)[^>]*>(.*?)</a>', re.S | re.I)
    lesson_pattern = re.compile(rf"{LESSON_PREFIX}\s*(\d+)")
    for href, raw_title in link_pattern.findall(page_html):
        title = normalize_lesson_title(clean_inline_html(raw_title))
        match = lesson_pattern.search(title)
        if not match:
            continue
        number = int(match.group(1))
        if number not in missing or number in lessons:
            continue
        url = html.unescape(href)
        if url.startswith("/"):
            url = "https://chzh1019.github.io" + url
        lessons[number] = LessonLink(number=number, list_title=title, url=url)
        print(f"recovered lesson {number:03d} from chzh mirror: {url}")

    return [lessons[key] for key in sorted(lessons)]


def recover_missing_lessons(
    session: requests.Session,
    links: list[LessonLink],
    expected: int,
    max_candidates_per_gap: int,
    timeout: int,
) -> list[LessonLink]:
    lessons = {link.number: link for link in links}
    missing = [number for number in range(1, expected + 1) if number not in lessons]
    if not missing:
        return [lessons[key] for key in sorted(lessons)]

    print(f"recovering missing lessons: {missing}")
    for number in missing:
        lower = max((key for key in lessons if key < number), default=None)
        upper = min((key for key in lessons if key > number), default=None)
        if lower is None or upper is None:
            continue

        lower_suffix = article_suffix(lessons[lower].url)
        upper_suffix = article_suffix(lessons[upper].url)
        if lower_suffix is None or upper_suffix is None:
            continue

        low, high = sorted((base36_to_int(lower_suffix), base36_to_int(upper_suffix)))
        candidate_count = high - low - 1
        if candidate_count <= 0 or candidate_count > max_candidates_per_gap:
            print(f"skip lesson {number}: candidate range {candidate_count}")
            continue

        target = f"{LESSON_PREFIX}{number}"
        print(f"scan lesson {number}: {candidate_count} candidates")
        for candidate in range(low + 1, high):
            suffix = int_to_base36(candidate)
            url = f"https://blog.sina.com.cn/s/blog_486e105c010{suffix}.html"
            try:
                page_html = fetch_text(session, url, timeout)
            except requests.RequestException:
                continue
            title = extract_title(page_html)
            if target in title:
                lessons[number] = LessonLink(number=number, list_title=title, url=url)
                print(f"recovered lesson {number:03d}: {title}")
                break

    return [lessons[key] for key in sorted(lessons)]


def recover_from_eastmoney_index(
    session: requests.Session,
    links: list[LessonLink],
    expected: int,
    timeout: int,
) -> list[LessonLink]:
    lessons = {link.number: link for link in links}
    missing = [number for number in range(1, expected + 1) if number not in lessons]
    if not missing:
        return [lessons[key] for key in sorted(lessons)]

    try:
        page_html = fetch_text(session, EASTMONEY_SINA_INDEX_URL, timeout)
    except requests.RequestException as exc:
        print(f"eastmoney index unavailable: {exc}")
        return [lessons[key] for key in sorted(lessons)]

    compact_html = re.sub(r"\s+", " ", page_html)
    for number in missing:
        pattern = re.compile(
            rf"{LESSON_PREFIX}\s*{number}\D.*?(https?://blog\.sina\.com\.cn/s/blog_[0-9a-z]+\.html)",
            re.I,
        )
        match = pattern.search(compact_html)
        if not match:
            continue
        url = absolutize_url(html.unescape(match.group(1)))
        lessons[number] = LessonLink(number=number, list_title=f"{LESSON_PREFIX}{number}", url=url)
        print(f"recovered lesson {number:03d} from Eastmoney index: {url}")

    return [lessons[key] for key in sorted(lessons)]


def extract_article(number: int, url: str, page_html: str) -> LessonArticle:
    title = extract_title(page_html) or f"{LESSON_PREFIX}{number}"

    date_match = re.search(r'<span[^>]*class\s*=\s*["\']?[^>]*time[^>]*>\((.*?)\)</span>', page_html, re.S | re.I)
    published_at = clean_inline_html(date_match.group(1)) if date_match else ""

    body_match = re.search(
        r'<div[^>]+id\s*=\s*["\']?sina_keyword_ad_area2["\']?[^>]*>(.*?)(?:<!--\s*正文结束\s*-->|<div[^>]+class\s*=\s*["\']?articalInfo|<div[^>]+id\s*=\s*["\']?share|<div[^>]+class\s*=\s*["\']?share)',
        page_html,
        re.S | re.I,
    )
    if not body_match:
        body_match = re.search(
            r'<div[^>]+id\s*=\s*["\']?sina_keyword_ad_area2["\']?[^>]*>(.*?)<div[^>]+class\s*=\s*["\']?articalInfo',
            page_html,
            re.S | re.I,
        )
    if not body_match:
        raise ValueError(f"Could not locate article body for lesson {number}: {url}")

    body_html = re.sub(r"<!--.*?-->", "", body_match.group(1), flags=re.S)
    body_html = body_html.replace("<wbr>", "").replace("<WBR>", "")
    parser = SinaContentParser()
    parser.feed(body_html)
    body = parser.text()
    if not body:
        raise ValueError(f"Empty article body for lesson {number}: {url}")

    return LessonArticle(number=number, title=title, published_at=published_at, url=url, body=body)


def download_articles(
    session: requests.Session,
    links: Iterable[LessonLink],
    delay: float,
    timeout: int,
) -> list[LessonArticle]:
    articles: list[LessonArticle] = []
    for link in links:
        page_html = fetch_text(session, link.url, timeout)
        article = extract_article(link.number, link.url, page_html)
        articles.append(article)
        print(f"downloaded lesson {article.number:03d}: {article.title}")
        time.sleep(delay)
    return articles


def safe_filename(value: str, max_len: int = 80) -> str:
    value = re.sub(r"[\\/:*?\"<>|\r\n]+", "_", value).strip(" ._")
    value = re.sub(r"\s+", " ", value)
    return value[:max_len].strip() or "untitled"


def render_markdown(article: LessonArticle) -> str:
    metadata = [
        f"# {article.title}",
        "",
        f"- Lesson: {article.number}",
        f"- Published: {article.published_at or 'unknown'}",
        f"- Source: {article.url}",
        "",
        article.body,
        "",
    ]
    return "\n".join(metadata)


def write_outputs(articles: list[LessonArticle], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    articles_dir = output_dir / "articles_md"
    articles_dir.mkdir(parents=True, exist_ok=True)

    index_path = output_dir / "index.csv"
    with index_path.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.writer(file)
        writer.writerow(["lesson", "title", "published_at", "url", "file"])
        for article in articles:
            filename = f"lesson_{article.number:03d}_{safe_filename(article.title)}.md"
            relative_path = Path("articles_md") / filename
            (output_dir / relative_path).write_text(render_markdown(article), encoding="utf-8")
            writer.writerow([article.number, article.title, article.published_at, article.url, relative_path.as_posix()])

    combined = ["# 缠中说禅《教你炒股票》108课", ""]
    for article in articles:
        combined.append(render_markdown(article))
        combined.append("---")
        combined.append("")
    (output_dir / "教你炒股票_108课合集.md").write_text("\n".join(combined), encoding="utf-8")


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Download Chan Zhong Shuo Chan Sina blog stock lessons.")
    parser.add_argument("--output-dir", type=Path, default=DEFAULT_OUTPUT_DIR)
    parser.add_argument("--max-pages", type=int, default=30)
    parser.add_argument("--delay", type=float, default=0.5)
    parser.add_argument("--timeout", type=int, default=20)
    parser.add_argument("--expected", type=int, default=108)
    parser.add_argument("--recover-missing", action="store_true", default=True)
    parser.add_argument("--no-recover-missing", dest="recover_missing", action="store_false")
    parser.add_argument("--max-candidates-per-gap", type=int, default=2000)
    parser.add_argument("--allow-partial", action="store_true")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    session = make_session()
    links = discover_lessons(session, args.max_pages, args.delay, args.timeout)
    if args.recover_missing and len(links) != args.expected:
        links = recover_from_chzh_mirror(session, links, args.expected, args.timeout)
    if args.recover_missing and len(links) != args.expected:
        links = recover_from_eastmoney_index(session, links, args.expected, args.timeout)
    if args.recover_missing and len(links) != args.expected:
        links = recover_missing_lessons(
            session,
            links,
            args.expected,
            args.max_candidates_per_gap,
            args.timeout,
        )
    if len(links) != args.expected:
        message = f"found {len(links)} lessons, expected {args.expected}"
        if not args.allow_partial:
            raise SystemExit(message + "; rerun with --max-pages or --allow-partial")
        print("WARNING:", message)

    articles = download_articles(session, links, args.delay, args.timeout)
    write_outputs(articles, args.output_dir)
    print(f"wrote {len(articles)} lessons to {args.output_dir}")


if __name__ == "__main__":
    main()