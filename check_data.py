#!/usr/bin/env python3
"""
data.js 구조/무결성 점검 스크립트.
개인정보를 참조하지 않으므로 리포지토리에 커밋 가능.

점검 항목:
  1. 모든 day 엔트리에 cafe_url 필드 존재 (구 url 필드 금지)
  2. max_day가 days 키의 최댓값과 일치
  3. participants 배열 순서: max_day 내림차순 (같으면 원래 순서 유지)
  4. stats.day_counts가 실제 집계와 일치
  5. stats.total_participants가 participants 길이와 일치
  6. safe_images의 각 URL이 해당 참가자 days 내 images에 존재
  7. day 엔트리 필수 필드(day, title, content, images, cafe_url) 존재
"""
import json, sys, os

DATA_FILE = os.path.join(os.path.dirname(__file__), "data.js")

def load_data():
    with open(DATA_FILE, "r", encoding="utf-8") as f:
        content = f.read()
    return json.loads(content.replace("const STUDY_DATA = ", "").strip().rstrip(";"))

REQUIRED_DAY_FIELDS = ["day", "title", "content", "images", "cafe_url"]

def check_day_fields(data):
    issues = []
    for p in data["participants"]:
        for dk, day in p["days"].items():
            if "url" in day and "cafe_url" not in day:
                issues.append(f"{p['masked_nickname']} Day{dk}: 'url' 필드 사용 (→ 'cafe_url'로 변경 필요)")
            for f in REQUIRED_DAY_FIELDS:
                if f not in day:
                    issues.append(f"{p['masked_nickname']} Day{dk}: '{f}' 필드 누락")
    return issues

def check_max_day(data):
    issues = []
    for p in data["participants"]:
        keys = [int(k) for k in p["days"].keys()]
        expected = max(keys) if keys else 0
        if p.get("max_day", 0) != expected:
            issues.append(
                f"{p['masked_nickname']}: max_day={p.get('max_day')} but days max={expected}"
            )
    return issues

def check_order(data):
    issues = []
    prev_max = 99
    prev_nick = None
    zero_started = False
    for p in data["participants"]:
        md = p.get("max_day", 0)
        if md == 0:
            zero_started = True
            continue
        if zero_started:
            issues.append(f"{p['masked_nickname']}: Day 0 그룹 뒤에 활성 참가자(max_day={md}) 배치됨")
        if md > prev_max:
            issues.append(
                f"{p['masked_nickname']}(max_day={md})이 이전 참가자"
                f"({prev_nick}, max_day={prev_max})보다 뒤에 있음 (내림차순 위반)"
            )
        prev_max = md
        prev_nick = p['masked_nickname']
    return issues

def check_day_counts(data):
    issues = []
    actual = {}
    for p in data["participants"]:
        for dk in p["days"].keys():
            actual[dk] = actual.get(dk, 0) + 1
    declared = data["stats"].get("day_counts", {})
    for dk, cnt in actual.items():
        if declared.get(dk, 0) != cnt:
            issues.append(f"day_counts['{dk}']: 선언={declared.get(dk,0)}, 실제={cnt}")
    return issues

def check_total_participants(data):
    declared = data["stats"].get("total_participants", 0)
    actual = len(data["participants"])
    if declared != actual:
        return [f"total_participants: 선언={declared}, 실제={actual}"]
    return []

def check_safe_images(data):
    issues = []
    for p in data["participants"]:
        safe = p.get("safe_images", []) or []
        if not safe:
            continue
        all_imgs = set()
        for day in p["days"].values():
            for img in day.get("images", []) or []:
                all_imgs.add(img)
        for s in safe:
            if s not in all_imgs:
                issues.append(f"{p['masked_nickname']}: safe_images에 등록된 URL이 days 내 images에 존재하지 않음")
                break
    return issues

def main():
    data = load_data()
    checks = [
        ("day 필드 구조", check_day_fields(data)),
        ("max_day 정합성", check_max_day(data)),
        ("참가자 배열 순서", check_order(data)),
        ("day_counts 정합성", check_day_counts(data)),
        ("total_participants 정합성", check_total_participants(data)),
        ("safe_images 유효성", check_safe_images(data)),
    ]
    all_pass = True
    for name, issues in checks:
        if issues:
            print(f"  ❌ {name}")
            for issue in issues:
                print(f"     → {issue}")
            all_pass = False
        else:
            print(f"  ✅ {name}")
    print()
    if all_pass:
        print("🟢 데이터 구조 점검 통과")
        return 0
    else:
        print("🔴 데이터 구조 이슈 발견 — 수정 필요")
        return 1

if __name__ == "__main__":
    sys.exit(main())
