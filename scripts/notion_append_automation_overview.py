#!/usr/bin/env python3
"""Append a polished 'Automation Project Overview' section to a dashboard page.

Usage:
  python3 scripts/notion_append_automation_overview.py <dashboard_page_id> <projects_db_id>

Notes:
- Non-destructive: appends blocks only.
- Tries to find the Couplus/Coupang automation row in the DB by title contains 'Couplus' or 'Coupang'.
"""

from __future__ import annotations

import os
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

NOTION_VERSION = "2022-06-28"


def load_env(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text(errors="ignore").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, v = line.split("=", 1)
        v = v.strip().strip('"').strip("'")
        os.environ.setdefault(k.strip(), v)


def headers() -> dict:
    key = os.environ.get("NOTION_API_KEY")
    if not key:
        raise RuntimeError("NOTION_API_KEY is not set")
    return {
        "Authorization": f"Bearer {key}",
        "Notion-Version": NOTION_VERSION,
        "Content-Type": "application/json",
    }


def append_blocks(block_id: str, blocks: list[dict]) -> None:
    url = f"https://api.notion.com/v1/blocks/{block_id}/children"
    r = requests.patch(url, headers=headers(), json={"children": blocks}, timeout=30)
    if r.status_code >= 300:
        raise RuntimeError(f"append failed: {r.status_code} {r.text[:200]}")


def query_db(db_id: str) -> list[dict]:
    url = f"https://api.notion.com/v1/databases/{db_id}/query"
    r = requests.post(url, headers=headers(), json={"page_size": 100}, timeout=30)
    if r.status_code >= 300:
        raise RuntimeError(f"query failed: {r.status_code} {r.text[:200]}")
    return r.json().get("results", [])


def title_of(row: dict) -> str:
    t = row.get("properties", {}).get("프로젝트", {}).get("title", [])
    return "".join([x.get("plain_text", "") for x in t]).strip()


def find_automation_row(db_id: str) -> dict | None:
    for r in query_db(db_id):
        t = title_of(r)
        if any(k in t for k in ["Couplus", "Coupang", "쿠플", "쿠팡"]):
            return r
    return None


def rt(text: str) -> list[dict]:
    return [{"type": "text", "text": {"content": text}}]


def main() -> int:
    if len(sys.argv) != 3:
        print("usage: notion_append_automation_overview.py <dashboard_page_id> <projects_db_id>", file=sys.stderr)
        return 2

    page_id = sys.argv[1].strip()
    db_id = sys.argv[2].strip()

    if not os.environ.get("NOTION_API_KEY"):
        load_env(Path.home() / "ai-agents" / ".env")

    kst = timezone(timedelta(hours=9))
    now = datetime.now(tz=kst).strftime("%Y-%m-%d %H:%M KST")

    row = find_automation_row(db_id)
    row_url = row.get("url") if row else None

    blocks: list[dict] = [
        {"type": "divider", "divider": {}},
        {"type": "heading_2", "heading_2": {"rich_text": rt("자동화 프로젝트 (문서형 요약)")}},
        {"type": "callout", "callout": {"icon": {"type": "emoji", "emoji": "🤖"}, "rich_text": rt("쿠플러스/쿠팡 자동화의 ‘한눈에 보기’ 요약. 운영/리스크/다음 액션 기준으로 정리.")}},
        {"type": "paragraph", "paragraph": {"rich_text": rt(f"last update: {now}")}},
    ]

    if row_url:
        blocks.append({"type": "paragraph", "paragraph": {"rich_text": [
            {"type": "text", "text": {"content": "프로젝트 카드(상세 문서): "}},
            {"type": "text", "text": {"content": "열기", "link": {"url": row_url}}},
        ]}})

    blocks += [
        {"type": "heading_3", "heading_3": {"rich_text": rt("목표")}},
        {"type": "bulleted_list_item", "bulleted_list_item": {"rich_text": rt("도매매/도매꾹 링크 → 쿠팡 업로드/관리 자동화")}},
        {"type": "bulleted_list_item", "bulleted_list_item": {"rich_text": rt("주문 → 발주 초안 생성 → 최종 결제는 수동(안전장치)")}},
        {"type": "heading_3", "heading_3": {"rich_text": rt("핵심 흐름")}},
        {"type": "numbered_list_item", "numbered_list_item": {"rich_text": rt("소싱 URL 입력(도매매/도매꾹/1688 등)")}},
        {"type": "numbered_list_item", "numbered_list_item": {"rich_text": rt("상품 정보 파싱/정제(옵션, 배송비, 가격 규칙)")}},
        {"type": "numbered_list_item", "numbered_list_item": {"rich_text": rt("중복 방지/재업로드 UX(필요 시 force)")}},
        {"type": "numbered_list_item", "numbered_list_item": {"rich_text": rt("쿠팡 업로드 실행(실패 시 사유 표시)")}},
        {"type": "heading_3", "heading_3": {"rich_text": rt("운영 원칙(리스크 관리)")}},
        {"type": "bulleted_list_item", "bulleted_list_item": {"rich_text": rt("‘자동 결제/발주’는 금지, 초안만 자동화(사고 방지)")}},
        {"type": "bulleted_list_item", "bulleted_list_item": {"rich_text": rt("배송비 불명확(-1) 케이스는 업로드 실패로 처리 → 사용자가 확인 후 진행")}},
        {"type": "bulleted_list_item", "bulleted_list_item": {"rich_text": rt("토큰/세션/키 등 시크릿 값은 Notion에 절대 적지 않음(위치만 기록)")}},
        {"type": "heading_3", "heading_3": {"rich_text": rt("다음 액션")}},
        {"type": "to_do", "to_do": {"rich_text": rt("(P0) 자동화 프로젝트 ‘완료 정의’ 3줄로 확정"), "checked": False}},
        {"type": "to_do", "to_do": {"rich_text": rt("(P1) 실패 케이스 Top 5 수집 → 룰/UX 개선 backlog로 정리"), "checked": False}},
        {"type": "to_do", "to_do": {"rich_text": rt("(P2) 알림/리포트(업로드 성공/실패 요약) 텔레그램/푸시로 전달"), "checked": False}},
    ]

    append_blocks(page_id, blocks)
    print("ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
