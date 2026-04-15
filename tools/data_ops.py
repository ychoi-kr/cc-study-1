#!/usr/bin/env python3
"""
study-update 워크플로에서 매 실행마다 반복되는 data.js 조작을 모아둔 헬퍼.

per-run에 달라지는 LLM 판단(어떤 day로 매핑할지, journey_excerpt 본문, safe_images 선정,
thumb 후보)은 호출자가 직접 넘긴다. 이 모듈은 그 외의 기계적 작업만 담당한다.

사용 예:
    from study_showcase.tools.data_ops import (
        load_data, save_data, mask_content,
        add_day_entry, recount_stats, append_raw_articles,
    )

    data = load_data()
    content = mask_content(article['content'], author=article['author'])
    add_day_entry(data, participant_id=mid, day=10,
                  title=masked_title, content=content,
                  images=article['images'], cafe_url=article['url'],
                  journey_excerpt=my_excerpt)
    recount_stats(data)
    save_data(data)
    append_raw_articles(new_articles)
"""
from __future__ import annotations

import hashlib
import json
import re
from collections import Counter
from pathlib import Path
from typing import Iterable

SHOWCASE_DIR = Path(__file__).resolve().parent.parent
DATA_PATH = SHOWCASE_DIR / "data.js"
KNOWN_IDS_PATH = SHOWCASE_DIR / ".known_ids.json"
CAFE_ARTICLES_PATH = Path("/Users/yong/wikibook/cafe_articles_full.json")

_DATA_PREFIX = "const STUDY_DATA = "
_DATA_SUFFIX = ";"


# ---------- load / save ----------

def load_data() -> dict:
    text = DATA_PATH.read_text()
    body = text.replace(_DATA_PREFIX, "", 1).strip()
    if body.endswith(_DATA_SUFFIX):
        body = body[: -len(_DATA_SUFFIX)]
    return json.loads(body)


def save_data(data: dict) -> None:
    DATA_PATH.write_text(
        _DATA_PREFIX + json.dumps(data, ensure_ascii=False, indent=2) + _DATA_SUFFIX + "\n"
    )


def load_known_ids() -> list[str]:
    if not KNOWN_IDS_PATH.exists():
        return []
    return json.loads(KNOWN_IDS_PATH.read_text()).get("known_ids", [])


# ---------- id / masking ----------

def participant_id(author: str) -> str:
    return hashlib.md5(author.encode()).hexdigest()[:8]


def mask_nickname(nick: str) -> str:
    if len(nick) <= 2:
        return nick[0] + "*"
    return nick[0] + "*" * (len(nick) - 2) + nick[-1]


def _mask_github_id(text: str, known_ids: Iterable[str]) -> str:
    for gid in sorted(known_ids, key=len, reverse=True):
        if len(gid) < 3:
            continue
        masked = gid[0] + "*" * (len(gid) - 2) + gid[-1]
        text = text.replace(gid, masked)
    return text


def _mask_author_nick(text: str, author: str) -> str:
    if author == "위키북스":
        return text
    return text.replace(author, mask_nickname(author))


def _strip_deploy_urls(text: str) -> str:
    text = re.sub(r"https?://[^\s]*vercel\.app[^\s]*", "[배포 URL 생략]", text)
    text = re.sub(r"https?://[^\s]*\.github\.io[^\s]*", "[배포 URL 생략]", text)
    text = re.sub(r"[a-zA-Z0-9-]+\.vercel\.app", "[배포 URL 생략]", text)
    return text


def mask_content(
    text: str,
    *,
    author: str | None = None,
    known_ids: Iterable[str] | None = None,
    strip_urls: bool = True,
) -> str:
    """본문/제목/발췌 텍스트를 한 번에 마스킹한다."""
    if known_ids is None:
        known_ids = load_known_ids()
    out = _mask_github_id(text, known_ids)
    if author:
        out = _mask_author_nick(out, author)
    if strip_urls:
        out = _strip_deploy_urls(out)
    return out


# ---------- day entry ----------

def add_day_entry(
    data: dict,
    *,
    participant_id: str,
    day: int,
    title: str,
    content: str,
    images: list[str],
    cafe_url: str,
    journey_excerpt: str = "",
    overwrite: bool = False,
) -> bool:
    """참가자의 days에 새 엔트리를 추가하고 max_day를 갱신한다.

    Returns:
        True if added, False if skipped (already exists and overwrite=False).
    """
    p_map = {p["id"]: p for p in data["participants"]}
    p = p_map.get(participant_id)
    if p is None:
        raise KeyError(f"participant {participant_id} not in data.js")

    day_key = str(day)
    if day_key in p["days"] and not overwrite:
        return False

    p["days"][day_key] = {
        "day": day,
        "title": title,
        "content": content,
        "images": list(images),
        "cafe_url": cafe_url,
        "journey_excerpt": journey_excerpt,
    }
    if day > p.get("max_day", 0):
        p["max_day"] = day
    return True


def add_safe_images(data: dict, participant_id: str, images: Iterable[str]) -> int:
    """safe_images에 중복 제거하며 추가. 추가된 개수 반환."""
    p_map = {p["id"]: p for p in data["participants"]}
    p = p_map[participant_id]
    p.setdefault("safe_images", [])
    added = 0
    for img in images:
        if img not in p["safe_images"]:
            p["safe_images"].append(img)
            added += 1
    return added


def set_thumb(data: dict, participant_id: str, thumb) -> None:
    """thumb 지정. string 또는 2장짜리 list(모바일 듀얼)."""
    p_map = {p["id"]: p for p in data["participants"]}
    p_map[participant_id]["thumb"] = thumb


# ---------- stats / sort ----------

def recount_stats(data: dict) -> None:
    """day_counts, current_day 재집계 + days 키 숫자 정렬 + participants max_day 정렬."""
    counter: Counter[int] = Counter()
    for p in data["participants"]:
        p["days"] = dict(sorted(p["days"].items(), key=lambda kv: int(kv[0])))
        for d in p["days"]:
            counter[int(d)] += 1

    total_days = data["meta"].get("total_days", 10)
    day_counts = data["stats"].setdefault("day_counts", {})
    for d in range(1, total_days + 1):
        day_counts[str(d)] = counter.get(d, 0)

    # current_day = 공개된 최대 day (day_counts 기준이 아니라 curriculum 기준)
    done_days = [c["day"] for c in data.get("curriculum", []) if c.get("status") == "done"]
    if done_days:
        cur = max(done_days)
        data["meta"]["current_day"] = cur
        data["stats"]["current_day"] = cur

    data["participants"].sort(key=lambda p: -p.get("max_day", 0))


def mark_curriculum_done(data: dict, day: int, title: str | None = None) -> None:
    """커리큘럼의 특정 day를 done으로 표시하고, 필요하면 제목도 갱신한다."""
    for c in data.get("curriculum", []):
        if c["day"] == day:
            if title:
                c["title"] = title
            c["status"] = "done"
            return


# ---------- cafe_articles_full.json ----------

def append_raw_articles(articles: list[dict]) -> int:
    """중복 id는 건너뛰고 추가. 추가된 개수 반환."""
    existing: list[dict] = []
    if CAFE_ARTICLES_PATH.exists():
        existing = json.loads(CAFE_ARTICLES_PATH.read_text())
    ex_ids = {a["id"] for a in existing}
    added = 0
    for a in articles:
        if a["id"] not in ex_ids:
            existing.append(a)
            added += 1
    CAFE_ARTICLES_PATH.write_text(json.dumps(existing, ensure_ascii=False, indent=2))
    return added
