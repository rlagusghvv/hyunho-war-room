#!/usr/bin/env python3
"""Create a clean dashboard page (no Notion onboarding clutter) and link to the existing Projects DB.

Usage:
  python3 scripts/notion_create_clean_dashboard.py <old_dashboard_page_id> <projects_db_id>

Notes:
- Non-destructive: does not delete old page content.
- Creates a new page under the same parent as the old page.
- Updates old page title to mark it as archive and appends a link to the new page.
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


def get_page(page_id: str) -> dict:
    r = requests.get(f"https://api.notion.com/v1/pages/{page_id}", headers=headers(), timeout=30)
    if r.status_code >= 300:
        raise RuntimeError(f"get page failed: {r.status_code} {r.text[:200]}")
    return r.json()


def update_page_title(page_id: str, title: str) -> None:
    url = f"https://api.notion.com/v1/pages/{page_id}"
    payload = {"properties": {"title": {"title": [{"type": "text", "text": {"content": title}}]}}}
    r = requests.patch(url, headers=headers(), json=payload, timeout=30)
    if r.status_code >= 300:
        raise RuntimeError(f"update title failed: {r.status_code} {r.text[:200]}")


def append_blocks(parent_block_id: str, blocks: list[dict]) -> None:
    url = f"https://api.notion.com/v1/blocks/{parent_block_id}/children"
    r = requests.patch(url, headers=headers(), json={"children": blocks}, timeout=30)
    if r.status_code >= 300:
        raise RuntimeError(f"append failed: {r.status_code} {r.text[:200]}")


def create_page(parent: dict, title: str, children: list[dict]) -> dict:
    url = "https://api.notion.com/v1/pages"
    payload = {
        "parent": parent,
        "properties": {"title": {"title": [{"type": "text", "text": {"content": title}}]}},
        "children": children,
    }
    r = requests.post(url, headers=headers(), json=payload, timeout=30)
    if r.status_code >= 300:
        raise RuntimeError(f"create page failed: {r.status_code} {r.text[:200]}")
    return r.json()


def main() -> int:
    if len(sys.argv) != 3:
        print("usage: notion_create_clean_dashboard.py <old_dashboard_page_id> <projects_db_id>", file=sys.stderr)
        return 2

    old_page_id = sys.argv[1].strip()
    db_id = sys.argv[2].strip()

    if not os.environ.get("NOTION_API_KEY"):
        load_env_from_file(Path.home() / "ai-agents" / ".env")

    # Notion API cannot create a page with parent type=workspace unless the integration has special capabilities.
    # We'll always create the clean dashboard as a CHILD of the existing (cluttered) page.
    parent = {"page_id": old_page_id}

    kst = timezone(timedelta(hours=9))
    now = datetime.now(tz=kst).strftime("%Y-%m-%d %H:%M KST")
    db_url = f"https://www.notion.so/{db_id.replace('-', '')}"

    new_title = "현황 대시보드"

    children = [
        {"type": "heading_1", "heading_1": {"rich_text": [{"type": "text", "text": {"content": "현황 대시보드"}}]}},
        {
            "type": "callout",
            "callout": {
                "icon": {"type": "emoji", "emoji": "📌"},
                "rich_text": [{"type": "text", "text": {"content": "P0/블로커 확인 → 각 프로젝트 ‘다음 액션’ 1~2개만 갱신."}}],
            },
        },
        {"type": "paragraph", "paragraph": {"rich_text": [{"type": "text", "text": {"content": f"last update: {now}"}}]}},
        {
            "type": "paragraph",
            "paragraph": {
                "rich_text": [
                    {"type": "text", "text": {"content": "프로젝트 DB 바로가기: ",}},
                    {"type": "text", "text": {"content": "열기", "link": {"url": db_url}}},
                ]
            },
        },
        {"type": "divider", "divider": {}},
        {
            "type": "toggle",
            "toggle": {
                "rich_text": [{"type": "text", "text": {"content": "자동 요약"}}],
                "children": [
                    {"type": "paragraph", "paragraph": {"rich_text": [{"type": "text", "text": {"content": "(요약은 자동 갱신됨)"}}]}},
                ],
            },
        },
        {"type": "divider", "divider": {}},
        {"type": "heading_2", "heading_2": {"rich_text": [{"type": "text", "text": {"content": "운영 상태"}}]}},
        {"type": "bulleted_list_item", "bulleted_list_item": {"rich_text": [{"type": "text", "text": {"content": "Mac mini: 상시 구동"}}]}},
        {"type": "bulleted_list_item", "bulleted_list_item": {"rich_text": [{"type": "text", "text": {"content": "Colima/Docker: watchdog로 자동 복구"}}]}},
        {"type": "bulleted_list_item", "bulleted_list_item": {"rich_text": [{"type": "text", "text": {"content": "OpenClaw: 127.0.0.1:18789"}}]}},
    ]

    new_page = create_page(parent=parent, title=new_title, children=children)
    new_page_id = new_page.get("id")
    new_page_url = new_page.get("url")

    # Mark old as archive and add link
    try:
        update_page_title(old_page_id, "(아카이브) 기존 온보딩/대시보드")
    except Exception:
        pass

    try:
        append_blocks(
            old_page_id,
            [
                {"type": "divider", "divider": {}},
                {
                    "type": "callout",
                    "callout": {
                        "icon": {"type": "emoji", "emoji": "➡️"},
                        "rich_text": [
                            {"type": "text", "text": {"content": "새 대시보드(깔끔한 버전): ",}},
                            {"type": "text", "text": {"content": "현황 대시보드", "link": {"url": new_page_url}}},
                        ],
                    },
                },
            ],
        )
    except Exception:
        pass

    print(new_page_id)
    print(new_page_url)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
