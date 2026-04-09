#!/usr/bin/env python3
"""
네이버 카페 인증 게시판(메뉴 154)에서 새로운 글만 크롤링한다.

전제:
- Chrome이 --remote-debugging-port=9222 로 실행 중
- 해당 Chrome에 네이버 로그인 완료
- /Users/yong/wikibook/cafe_articles_full.json 이 누적 저장소

산출:
- /tmp/new_fetched.json — 새 글의 본문/이미지/메타 (data.js 편집용)
- /tmp/list_now.json   — 이번 실행에서 본 전체 목록 (디버그용)
- 표준출력: 새 글 개수와 ID/제목 요약, 그리고 과제 게시판(메뉴 153) 최신 목록
"""
import json
import re
import sys
import time
from pathlib import Path

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.common.by import By

CAFE_BOARD_URL = "https://cafe.naver.com/f-e/cafes/30853297/menus/154"
CURRICULUM_BOARD_URL = "https://cafe.naver.com/f-e/cafes/30853297/menus/153"
FULL_JSON = Path("/Users/yong/wikibook/cafe_articles_full.json")
OUT_NEW = Path("/tmp/new_fetched.json")
OUT_LIST = Path("/tmp/list_now.json")
MAX_PAGES = 15


def make_driver():
    opts = Options()
    opts.add_experimental_option("debuggerAddress", "127.0.0.1:9222")
    return webdriver.Chrome(options=opts)


def fetch_list(driver, existing_ids):
    """목록 페이지를 순회해 글 ID/제목/URL을 모은다. 새 글이 0인 페이지를 만나면 중단."""
    all_list = []
    seen = set()
    for page in range(1, MAX_PAGES + 1):
        url = f"{CAFE_BOARD_URL}?page={page}" if page > 1 else CAFE_BOARD_URL
        driver.get(url)
        time.sleep(2.2)
        anchors = driver.find_elements(By.CSS_SELECTOR, "a[class*='article']")
        real = [a for a in anchors if "commentFocus" not in (a.get_attribute("href") or "")]
        if not real:
            break
        page_added = 0
        for a in real:
            href = a.get_attribute("href")
            title = (a.text or "").strip()
            m = re.search(r"/articles/(\d+)", href or "")
            aid = m.group(1) if m else None
            if not aid or aid in seen:
                continue
            seen.add(aid)
            all_list.append({"id": aid, "title": title, "url": href})
            page_added += 1
        if page_added == 0:
            break
    return all_list


def fetch_article(driver, art):
    """기사 한 건의 본문/이미지/링크/작성자/날짜를 채워 art dict를 반환."""
    driver.switch_to.default_content()
    driver.get(art["url"])
    time.sleep(2.8)

    for ifr in driver.find_elements(By.TAG_NAME, "iframe"):
        src = ifr.get_attribute("src") or ""
        if "articles" in src and "fromNext" in src:
            driver.switch_to.frame(ifr)
            break
    time.sleep(0.8)

    container = None
    content = ""
    for sel in [".se-main-container", ".article_viewer"]:
        elems = driver.find_elements(By.CSS_SELECTOR, sel)
        if elems:
            container = elems[0]
            content = container.text.strip()
            if len(content) > 10:
                break

    images = []
    if container:
        for img in container.find_elements(By.TAG_NAME, "img"):
            src = img.get_attribute("src") or ""
            if "cafeptthumb" in src or "postfiles" in src:
                if src not in images:
                    images.append(src)

    all_urls = []
    for lnk in driver.find_elements(By.TAG_NAME, "a"):
        href = lnk.get_attribute("href") or ""
        if href and "naver.com" not in href and len(href) > 10:
            all_urls.append(href)
    for u in re.findall(r'https?://[^\s<>"\')\]]+', content):
        if u not in all_urls:
            all_urls.append(u)

    github_urls = [u for u in all_urls if "github.com" in u.lower()]
    deploy_urls = [
        u for u in all_urls
        if any(k in u.lower() for k in ["github.io", "vercel.app", "netlify.app"])
    ]

    author = ""
    for sel in [".nickname", ".nick", "[class*='nickname']"]:
        elems = driver.find_elements(By.CSS_SELECTOR, sel)
        if elems:
            author = elems[0].text.strip()
            if author:
                break

    date = ""
    for sel in [".date", "[class*='date']", "time"]:
        elems = driver.find_elements(By.CSS_SELECTOR, sel)
        if elems:
            for e in elems:
                t = e.text.strip()
                if t:
                    date = t
                    break
        if date:
            break

    art.update({
        "content": content,
        "images": images,
        "urls": all_urls,
        "github_urls": github_urls,
        "deploy_urls": deploy_urls,
        "author": author,
        "date": date,
    })
    return art


def fetch_curriculum(driver):
    """과제 게시판 최신 목록을 (id, title) 튜플 리스트로 반환."""
    driver.get(CURRICULUM_BOARD_URL)
    time.sleep(2.5)
    out = []
    seen = set()
    for a in driver.find_elements(By.CSS_SELECTOR, "a[class*='article']"):
        href = a.get_attribute("href") or ""
        if "commentFocus" in href:
            continue
        title = (a.text or "").strip()
        m = re.search(r"/articles/(\d+)", href)
        aid = m.group(1) if m else None
        if aid and aid not in seen and title:
            seen.add(aid)
            out.append((aid, title))
    return out


def main():
    if not FULL_JSON.exists():
        print(f"ERROR: {FULL_JSON} not found", file=sys.stderr)
        sys.exit(1)

    existing = json.loads(FULL_JSON.read_text())
    existing_ids = {a["id"] for a in existing}
    print(f"existing: {len(existing_ids)}")

    driver = make_driver()

    listing = fetch_list(driver, existing_ids)
    OUT_LIST.write_text(json.dumps(listing, ensure_ascii=False, indent=2))
    new_only = [a for a in listing if a["id"] not in existing_ids]
    print(f"fetched {len(listing)}, new {len(new_only)}")
    for a in new_only:
        print(f"  NEW {a['id']}: {a['title'][:70]}")

    fetched = []
    for a in new_only:
        print(f"  fetching body of {a['id']}...")
        fetched.append(fetch_article(driver, dict(a)))
    OUT_NEW.write_text(json.dumps(fetched, ensure_ascii=False, indent=2))
    print(f"-> wrote {OUT_NEW} ({len(fetched)} articles)")

    print("\n--- curriculum board (menu 153) ---")
    for aid, title in fetch_curriculum(driver):
        print(f"  {aid} {title[:80]}")


if __name__ == "__main__":
    main()
