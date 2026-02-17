#!/usr/bin/env python3
"""Rebuild a Notion page into a simple redirect stub pointing to a new page.

Usage:
  python3 scripts/notion_rebuild_redirect_page.py <old_page_id> <new_page_url>

Destructive: deletes all child blocks under old_page_id.
"""

from __future__ import annotations

import os
import re
import sys
from pathlib import Path

import requests

NOTION_VERSION = "2022-06-28"


def load_env(path: Path) -> None:
    if not path.exists():
        return
    for line in path.read_text(errors="ignore").splitlines():
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
    out = []
    cursor = None
    while True:
        url = f"https://api.notion.com/v1/blocks/{block_id}/children?page_size=100"
        if cursor:
            url += f"&start_cursor={cursor}"
        r = requests.get(url, headers=headers(), timeout=30)
        r.raise_for_status()
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


def main() -> int:
    if len(sys.argv) != 3:
        print("usage: notion_rebuild_redirect_page.py <old_page_id> <new_page_url>", file=sys.stderr)
        return 2

    old_page_id = sys.argv[1].strip()
    new_url = sys.argv[2].strip()

    if not os.environ.get("NOTION_API_KEY"):
        load_env(Path.home() / "ai-agents" / ".env")

    for c in list_children(old_page_id):
        delete_block(c["id"])

    children = [
        {"type": "heading_1", "heading_1": {"rich_text": [{"type": "text", "text": {"content": "(이 페이지는 아카이브)"}}]}},
        {
            "type": "callout",
            "callout": {
                "icon": {"type": "emoji", "emoji": "➡️"},
                "rich_text": [
                    {"type": "text", "text": {"content": "새 대시보드로 이동: ",}},
                    {"type": "text", "text": {"content": "현황 대시보드", "link": {"url": new_url}}},
                ],
            },
        },
        {"type": "paragraph", "paragraph": {"rich_text": [{"type": "text", "text": {"content": "이 페이지 내용은 정리/이관 완료. 앞으로는 위 링크만 사용."}}]}},
    ]

    append_children(old_page_id, children)
    print("ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
