#!/usr/bin/env python3
"""Rebuild the clean dashboard page into a minimal, mobile-first layout.

- Destructive to the page's existing child blocks (page history can restore).
- After rebuild, it creates two managed toggles:
  - "📱 모바일 대시보드(자동)" (empty; you should run notion_upsert_mobile_dashboard.py)
  - "자동 요약" (empty; you should run notion_upsert_db_summary.py)

Usage:
  python3 scripts/notion_rebuild_clean_dashboard_minimal.py <dashboard_page_id> <projects_db_id>
"""

from __future__ import annotations

import os
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

NOTION_VERSION = "2022-06-28"


def load_env_from_file(path: Path) -> None:
    if not path.exists():
        return
    txt = path.read_text(errors="ignore")
    for line in txt.splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        m = re.match(r"^([A-Za-z_][A-Za-z0-9_]*)=(.*)$", line)
        if not m:
            continue
        k, v = m.group(1), m.group(2)
        if len(v) >= 2 and ((v[0] == v[-1] == '"') or (v[0] == v[-1] == "'")):
            v = v[1:-1]
        os.environ.setdefault(k, v)


def headers() -> dict:
    key = os.environ.get("NOTION_API_KEY")
    if not key:
        raise RuntimeError("NOTION_API_KEY is not set")
    return {
        "Authorization": f"Bearer {key}",
        "Notion-Version": NOTION_VERSION,
        "Content-Type": "application/json",
    }


def list_children(block_id: str) -> list[dict]:
    out: list[dict] = []
    cursor = None
    while True:
        url = f"https://api.notion.com/v1/blocks/{block_id}/children?page_size=100"
        if cursor:
            url += f"&start_cursor={cursor}"
        r = requests.get(url, headers=headers(), timeout=30)
        if r.status_code >= 300:
            raise RuntimeError(f"list children failed: {r.status_code} {r.text[:200]}")
        js = r.json()
        out.extend(js.get("results", []))
        if not js.get("has_more"):
            break
        cursor = js.get("next_cursor")
    return out


def delete_block(block_id: str) -> None:
    r = requests.delete(f"https://api.notion.com/v1/blocks/{block_id}", headers=headers(), timeout=30)
    if r.status_code >= 300:
        raise RuntimeError(f"delete failed: {r.status_code} {r.text[:200]}")


def append_children(block_id: str, children: list[dict]) -> None:
    r = requests.patch(
        f"https://api.notion.com/v1/blocks/{block_id}/children",
        headers=headers(),
        json={"children": children},
        timeout=30,
    )
    if r.status_code >= 300:
        raise RuntimeError(f"append failed: {r.status_code} {r.text[:200]}")


def rt(text: str) -> list[dict]:
    return [{"type": "text", "text": {"content": text}}]


def main() -> int:
    if len(sys.argv) != 3:
        print("usage: notion_rebuild_clean_dashboard_minimal.py <dashboard_page_id> <projects_db_id>", file=sys.stderr)
        return 2

    page_id = sys.argv[1].strip()
    db_id = sys.argv[2].strip()

    if not os.environ.get("NOTION_API_KEY"):
        load_env_from_file(Path.home() / "ai-agents" / ".env")

    # wipe all existing children
    for c in list_children(page_id):
        delete_block(c["id"])

    kst = timezone(timedelta(hours=9))
    now = datetime.now(tz=kst).strftime("%Y-%m-%d %H:%M KST")
    db_url = f"https://www.notion.so/{db_id.replace('-', '')}"

    blocks: list[dict] = [
        {"type": "heading_1", "heading_1": {"rich_text": rt("현황 대시보드")}},
        {
            "type": "callout",
            "callout": {
                "icon": {"type": "emoji", "emoji": "📌"},
                "rich_text": rt("모바일 기준: P0/블로커만 먼저 보고, 각 프로젝트는 ‘다음 액션’ 1~2개만 유지."),
            },
        },
        {"type": "paragraph", "paragraph": {"rich_text": rt(f"last rebuild: {now}")}},
        {
            "type": "paragraph",
            "paragraph": {
                "rich_text": [
                    {"type": "text", "text": {"content": "프로젝트 DB: ",}},
                    {"type": "text", "text": {"content": "열기", "link": {"url": db_url}}},
                ]
            },
        },
        {"type": "divider", "divider": {}},
        {"type": "toggle", "toggle": {"rich_text": rt("📱 모바일 대시보드(자동)"), "children": []}},
        {"type": "divider", "divider": {}},
        {"type": "toggle", "toggle": {"rich_text": rt("자동 요약"), "children": []}},
        {"type": "divider", "divider": {}},
        {
            "type": "toggle",
            "toggle": {
                "rich_text": rt("기타(상세/운영 노트)"),
                "children": [
                    {"type": "bulleted_list_item", "bulleted_list_item": {"rich_text": rt("프로젝트별 상세 문서는 각 프로젝트 카드에서 확인")}},
                    {"type": "bulleted_list_item", "bulleted_list_item": {"rich_text": rt("DB 뷰(칸반/P0/진행중)는 Notion UI에서 1회 세팅 권장")}},
                ],
            },
        },
    ]

    append_children(page_id, blocks)
    print("ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
