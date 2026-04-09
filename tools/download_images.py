#!/usr/bin/env python3
"""
시각 검토용 이미지 일괄 다운로드.

사용:
  python3 tools/download_images.py NAME=URL [NAME=URL ...]
  python3 tools/download_images.py --json /tmp/new_fetched.json
  python3 tools/download_images.py --stdin   # JSON 배열 또는 라인별 NAME=URL

기본 저장 경로: /tmp/study_imgs/
--json 모드: /tmp/new_fetched.json 의 각 article의 images를 자동 명명해 저장.
  파일명은 {author로마자화 불가시 id}_{day태그 또는 idx}_{n}.png
"""
import json
import re
import sys
import urllib.request
from pathlib import Path

OUT_DIR = Path("/tmp/study_imgs")
HEADERS = {"Referer": "https://cafe.naver.com/", "User-Agent": "Mozilla/5.0"}


def safe_name(s):
    return re.sub(r"[^A-Za-z0-9_.-]", "_", s)[:60]


def download(name, url):
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    path = OUT_DIR / name
    req = urllib.request.Request(url, headers=HEADERS)
    data = urllib.request.urlopen(req, timeout=15).read()
    path.write_bytes(data)
    print(f"  {name}  ({len(data)} bytes)")
    return path


def from_json(json_path):
    items = json.loads(Path(json_path).read_text())
    if isinstance(items, dict) and "new_articles" in items:
        items = items["new_articles"]
    pairs = []
    for art in items:
        aid = art.get("id", "x")
        author = art.get("author", "")
        title = art.get("title", "")
        m = re.search(r"day\s*(\d+)", title, re.I)
        day = m.group(1) if m else "x"
        base = safe_name(author) if author else aid
        for i, url in enumerate(art.get("images", []), 1):
            pairs.append((f"{base}_day{day}_{i}.png", url))
    return pairs


def main():
    args = sys.argv[1:]
    if not args:
        print(__doc__)
        sys.exit(1)

    pairs = []
    if args[0] == "--json":
        pairs = from_json(args[1])
    elif args[0] == "--stdin":
        text = sys.stdin.read().strip()
        try:
            data = json.loads(text)
            for i, url in enumerate(data, 1):
                pairs.append((f"img_{i}.png", url))
        except json.JSONDecodeError:
            for line in text.splitlines():
                if "=" in line:
                    n, u = line.split("=", 1)
                    pairs.append((n.strip(), u.strip()))
    else:
        for a in args:
            if "=" not in a:
                print(f"skip (no NAME=URL): {a}")
                continue
            n, u = a.split("=", 1)
            pairs.append((n, u))

    print(f"downloading {len(pairs)} images to {OUT_DIR}/")
    for name, url in pairs:
        try:
            download(name, url)
        except Exception as e:
            print(f"  ERR {name}: {e}")


if __name__ == "__main__":
    main()
