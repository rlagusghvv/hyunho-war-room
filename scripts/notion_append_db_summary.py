#!/usr/bin/env python3
"""Append a compact generated summary of the Projects DB to a dashboard page.

- Non-destructive: only appends blocks.
- Reads NOTION_API_KEY from env; if missing, loads from ~/ai-agents/.env.

Usage:
  python3 scripts/notion_append_db_summary.py <dashboard_page_id> <projects_db_id>
"""

from __future__ import annotations

import os
import re
import sys
from datetime import datetime, timezone, timedelta
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


def query_db(db_id: str, payload: dict) -> list[dict]:
    url = f"https://api.notion.com/v1/databases/{db_id}/query"
    r = requests.post(url, headers=headers(), json=payload, timeout=30)
    if r.status_code >= 300:
        raise RuntimeError(f"query failed: {r.status_code} {r.text[:300]}")
    return r.json().get("results", [])


def append_blocks(page_id: str, blocks: list[dict]) -> None:
    url = f"https://api.notion.com/v1/blocks/{page_id}/children"
    r = requests.patch(url, headers=headers(), json={"children": blocks}, timeout=30)
    if r.status_code >= 300:
        raise RuntimeError(f"append failed: {r.status_code} {r.text[:300]}")


def page_title(row: dict) -> str:
    props = row.get("properties", {})
    # Title prop named '프로젝트'
    t = props.get("프로젝트", {}).get("title", [])
    return "".join([x.get("plain_text", "") for x in t]).strip() or "(untitled)"


def page_url(row: dict) -> str:
    return row.get("url")


def make_bullets(rows: list[dict]) -> list[dict]:
    out = []
    for r in rows[:10]:
        title = page_title(r)
        url = page_url(r)
        out.append(
            {
                "type": "bulleted_list_item",
                "bulleted_list_item": {
                    "rich_text": [
                        {"type": "text", "text": {"content": title, "link": {"url": url}}}
                    ]
                },
            }
        )
    if not out:
        out.append(
            {
                "type": "bulleted_list_item",
                "bulleted_list_item": {"rich_text": [{"type": "text", "text": {"content": "(없음)"}}]},
            }
        )
    return out


def main() -> int:
    if len(sys.argv) != 3:
        print("usage: notion_append_db_summary.py <dashboard_page_id> <projects_db_id>", file=sys.stderr)
        return 2

    dashboard_id = sys.argv[1].strip()
    db_id = sys.argv[2].strip()

    if not os.environ.get("NOTION_API_KEY"):
        load_env_from_file(Path.home() / "ai-agents" / ".env")

    kst = timezone(timedelta(hours=9))
    now = datetime.now(tz=kst).strftime("%Y-%m-%d %H:%M KST")

    # P0 first
    p0 = query_db(
        db_id,
        {
            "page_size": 20,
            "filter": {"property": "우선순위", "select": {"equals": "P0"}},
            "sorts": [{"property": "마지막 업데이트", "direction": "descending"}],
        },
    )
    blockers = query_db(
        db_id,
        {
            "page_size": 20,
            "filter": {"property": "상태", "select": {"equals": "🔴"}},
            "sorts": [{"property": "마지막 업데이트", "direction": "descending"}],
        },
    )

    blocks: list[dict] = [
        {"type": "divider", "divider": {}},
        {
            "type": "heading_2",
            "heading_2": {"rich_text": [{"type": "text", "text": {"content": f"자동 요약 ({now})"}}]},
        },
        {
            "type": "heading_3",
            "heading_3": {"rich_text": [{"type": "text", "text": {"content": "P0 (즉시 처리)"}}]},
        },
        *make_bullets(p0),
        {
            "type": "heading_3",
            "heading_3": {"rich_text": [{"type": "text", "text": {"content": "🔴 블로커"}}]},
        },
        *make_bullets(blockers),
        {
            "type": "callout",
            "callout": {
                "icon": {"type": "emoji", "emoji": "🛠️"},
                "rich_text": [
                    {
                        "type": "text",
                        "text": {
                            "content": "Notion API는 ‘DB 뷰(칸반/필터뷰)’ 생성은 제한이 있어서, 뷰는 Notion UI에서 1회만 만들어두면 끝. 아래 가이드 참고.",
                        },
                    }
                ],
            },
        },
        {
            "type": "toggle",
            "toggle": {
                "rich_text": [{"type": "text", "text": {"content": "권장 뷰 세팅(수동 3분)"}}],
                "children": [
                    {"type": "bulleted_list_item", "bulleted_list_item": {"rich_text": [{"type": "text", "text": {"content": "테이블: 전체 (정렬: 우선순위↑, 마지막업데이트↓)"}}]}},
                    {"type": "bulleted_list_item", "bulleted_list_item": {"rich_text": [{"type": "text", "text": {"content": "칸반: 상태별 (그룹=상태, 필터: 상태!=✅)"}}]}},
                    {"type": "bulleted_list_item", "bulleted_list_item": {"rich_text": [{"type": "text", "text": {"content": "테이블: P0만 (필터: 우선순위=P0)"}}]}},
                ],
            }
        },
    ]

    append_blocks(dashboard_id, blocks)
    print("ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
