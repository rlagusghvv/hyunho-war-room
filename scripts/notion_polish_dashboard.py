#!/usr/bin/env python3
"""Polish the existing Notion dashboard page by appending nicer structure blocks.

Safety:
- Does NOT change database schema.
- Does NOT delete or rewrite existing blocks.
- Reads NOTION_API_KEY from env; if missing, tries to load from ~/ai-agents/.env.

Usage:
  python3 scripts/notion_polish_dashboard.py <page_id> <projects_db_id>
"""

from __future__ import annotations

import os
import re
import sys
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
        # strip optional quotes
        if len(v) >= 2 and ((v[0] == v[-1] == '"') or (v[0] == v[-1] == "'")):
            v = v[1:-1]
        os.environ.setdefault(k, v)


def notion_headers() -> dict:
    key = os.environ.get("NOTION_API_KEY")
    if not key:
        raise RuntimeError("NOTION_API_KEY is not set")
    return {
        "Authorization": f"Bearer {key}",
        "Notion-Version": NOTION_VERSION,
        "Content-Type": "application/json",
    }


def append_blocks(parent_block_id: str, blocks: list[dict]) -> None:
    url = f"https://api.notion.com/v1/blocks/{parent_block_id}/children"
    r = requests.patch(url, headers=notion_headers(), json={"children": blocks}, timeout=30)
    if r.status_code >= 300:
        raise RuntimeError(f"append failed: {r.status_code} {r.text[:300]}")


def rid(id_: str) -> str:
    # Notion accepts both dashed and non-dashed IDs. Keep dashed for readability.
    return id_.strip()


def main() -> int:
    if len(sys.argv) != 3:
        print("usage: notion_polish_dashboard.py <page_id> <projects_db_id>", file=sys.stderr)
        return 2

    page_id = rid(sys.argv[1])
    db_id = rid(sys.argv[2])

    if not os.environ.get("NOTION_API_KEY"):
        load_env_from_file(Path.home() / "ai-agents" / ".env")

    # Use a stable notion URL format users can click.
    db_url = f"https://www.notion.so/{db_id.replace('-', '')}"

    blocks: list[dict] = [
        {"type": "divider", "divider": {}},
        {
            "type": "heading_1",
            "heading_1": {
                "rich_text": [{"type": "text", "text": {"content": "프로젝트 현황"}}],
                "is_toggleable": False,
            },
        },
        {
            "type": "callout",
            "callout": {
                "icon": {"type": "emoji", "emoji": "📌"},
                "rich_text": [
                    {"type": "text", "text": {"content": "아래 DB에서 상태/우선순위/다음 액션만 업데이트하면 끝. (P0 먼저)"}},
                ],
            },
        },
        {
            "type": "paragraph",
            "paragraph": {
                "rich_text": [
                    {"type": "text", "text": {"content": "프로젝트 DB 열기: ",}},
                    {"type": "text", "text": {"content": "Projects Database", "link": {"url": db_url}}},
                ]
            },
        },
        {
            "type": "heading_2",
            "heading_2": {"rich_text": [{"type": "text", "text": {"content": "운영 규칙(간단)"}}]},
        },
        {
            "type": "bulleted_list_item",
            "bulleted_list_item": {"rich_text": [{"type": "text", "text": {"content": "상태: ✅ 완료 / 🟡 진행 / 🔴 블로커 / 🧪 실험"}}]},
        },
        {
            "type": "bulleted_list_item",
            "bulleted_list_item": {"rich_text": [{"type": "text", "text": {"content": "우선순위: P0(즉시)~P3(여유)"}}]},
        },
        {
            "type": "bulleted_list_item",
            "bulleted_list_item": {"rich_text": [{"type": "text", "text": {"content": "각 프로젝트는 ‘다음 액션’ 1줄만 유지(너무 길게 쓰지 않기)"}}]},
        },
        {
            "type": "heading_2",
            "heading_2": {"rich_text": [{"type": "text", "text": {"content": "최근 이슈"}}]},
        },
        {
            "type": "toggle",
            "toggle": {
                "rich_text": [{"type": "text", "text": {"content": "트레이더삼 간헐 무응답(원인/대응)"}}],
                "children": [
                    {"type": "paragraph", "paragraph": {"rich_text": [{"type": "text", "text": {"content": "원인: OpenClaw OAuth 토큰 refresh 실패 → /v1/chat/completions 500"}}]}},
                    {"type": "paragraph", "paragraph": {"rich_text": [{"type": "text", "text": {"content": "대응: OAuth configure 완료 + healthwatch로 500 감지 시 자동 재시작(선택)"}}]}},
                ],
            },
        },
    ]

    append_blocks(page_id, blocks)
    print("ok: appended polish blocks")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
