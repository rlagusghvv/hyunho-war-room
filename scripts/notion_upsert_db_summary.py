#!/usr/bin/env python3
"""Upsert (update-in-place) a Projects DB summary section on a Notion dashboard page.

Goal
- Keep a single, reusable "자동 요약" container block on the dashboard.
- On each run: replace the container's children (delete old, append new) and refresh the title.

Behavior
- If a container toggle block with title starting with "자동 요약" exists on the page, reuse it.
- Else, create it at the bottom and persist its block_id to a local state file.

Safety
- Does not change DB schema.
- Deletes only children under the managed container toggle.
- Reads NOTION_API_KEY from env; if missing, loads from ~/ai-agents/.env.

Usage
  python3 scripts/notion_upsert_db_summary.py <dashboard_page_id> <projects_db_id>

Optional env
  NOTION_SUMMARY_STATE=path/to/state.json
"""

from __future__ import annotations

import json
import os
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

import requests

NOTION_VERSION = "2022-06-28"
DEFAULT_STATE_PATH = Path.home() / ".openclaw" / "workspace" / "memory" / "notion_state.json"


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


def state_path() -> Path:
    p = os.environ.get("NOTION_SUMMARY_STATE")
    return Path(p).expanduser() if p else DEFAULT_STATE_PATH


def load_state() -> dict:
    p = state_path()
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text())
    except Exception:
        return {}


def save_state(st: dict) -> None:
    p = state_path()
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(json.dumps(st, ensure_ascii=False, indent=2) + "\n")


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
    url = f"https://api.notion.com/v1/blocks/{block_id}"
    r = requests.delete(url, headers=headers(), timeout=30)
    if r.status_code >= 300:
        raise RuntimeError(f"delete failed: {r.status_code} {r.text[:200]}")


def append_children(block_id: str, children: list[dict]) -> None:
    url = f"https://api.notion.com/v1/blocks/{block_id}/children"
    r = requests.patch(url, headers=headers(), json={"children": children}, timeout=30)
    if r.status_code >= 300:
        raise RuntimeError(f"append failed: {r.status_code} {r.text[:200]}")


def update_toggle_title(block_id: str, title: str) -> None:
    url = f"https://api.notion.com/v1/blocks/{block_id}"
    payload = {
        "toggle": {
            "rich_text": [{"type": "text", "text": {"content": title}}]
        }
    }
    r = requests.patch(url, headers=headers(), json=payload, timeout=30)
    if r.status_code >= 300:
        raise RuntimeError(f"update block failed: {r.status_code} {r.text[:200]}")


def create_toggle_on_page(page_id: str, title: str) -> str:
    # Create a toggle as a child of page
    url = f"https://api.notion.com/v1/blocks/{page_id}/children"
    payload = {
        "children": [
            {
                "type": "toggle",
                "toggle": {
                    "rich_text": [{"type": "text", "text": {"content": title}}],
                    "children": [],
                },
            }
        ]
    }
    r = requests.patch(url, headers=headers(), json=payload, timeout=30)
    if r.status_code >= 300:
        raise RuntimeError(f"create toggle failed: {r.status_code} {r.text[:200]}")
    js = r.json()
    # response returns updated block children; first result is the new block
    results = js.get("results") or js.get("children")
    if not results:
        # Fallback: fetch last children and find by title later
        raise RuntimeError("unexpected create response (no results)")
    return results[0]["id"]


def find_container_toggle(page_id: str) -> str | None:
    # Try state first (but ignore archived/missing blocks)
    st = load_state()
    cid = st.get("notion", {}).get("dashboard_summary_container_id")
    if cid:
        try:
            r = requests.get(f"https://api.notion.com/v1/blocks/{cid}", headers=headers(), timeout=30)
            if r.status_code < 300 and not (r.json() or {}).get("archived"):
                return cid
        except Exception:
            pass

    # Else scan page children for a toggle whose text starts with "자동 요약"
    for blk in list_children(page_id):
        if blk.get("type") != "toggle":
            continue
        rt = (blk.get("toggle") or {}).get("rich_text", [])
        text = "".join([x.get("plain_text", "") for x in rt]).strip()
        if text.startswith("자동 요약"):
            return blk.get("id")
    return None


def query_db(db_id: str, payload: dict) -> list[dict]:
    url = f"https://api.notion.com/v1/databases/{db_id}/query"
    r = requests.post(url, headers=headers(), json=payload, timeout=30)
    if r.status_code >= 300:
        raise RuntimeError(f"query failed: {r.status_code} {r.text[:200]}")
    return r.json().get("results", [])


def page_title(row: dict) -> str:
    props = row.get("properties", {})
    t = props.get("프로젝트", {}).get("title", [])
    return "".join([x.get("plain_text", "") for x in t]).strip() or "(untitled)"


def make_bullets(rows: list[dict]) -> list[dict]:
    out: list[dict] = []
    for r in rows[:10]:
        title = page_title(r)
        url = r.get("url")
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


def build_children(db_id: str) -> list[dict]:
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

    return [
        {"type": "heading_3", "heading_3": {"rich_text": [{"type": "text", "text": {"content": "P0 (즉시 처리)"}}]}},
        *make_bullets(p0),
        {"type": "heading_3", "heading_3": {"rich_text": [{"type": "text", "text": {"content": "🔴 블로커"}}]}},
        *make_bullets(blockers),
        {
            "type": "toggle",
            "toggle": {
                "rich_text": [{"type": "text", "text": {"content": "권장 뷰 세팅(수동 3분)"}}],
                "children": [
                    {"type": "bulleted_list_item", "bulleted_list_item": {"rich_text": [{"type": "text", "text": {"content": "테이블: 전체 (정렬: 우선순위↑, 마지막업데이트↓)"}}]}},
                    {"type": "bulleted_list_item", "bulleted_list_item": {"rich_text": [{"type": "text", "text": {"content": "칸반: 상태별 (그룹=상태, 필터: 상태!=✅)"}}]}},
                    {"type": "bulleted_list_item", "bulleted_list_item": {"rich_text": [{"type": "text", "text": {"content": "테이블: P0만 (필터: 우선순위=P0)"}}]}},
                ],
            },
        },
    ]


def main() -> int:
    if len(sys.argv) != 3:
        print("usage: notion_upsert_db_summary.py <dashboard_page_id> <projects_db_id>", file=sys.stderr)
        return 2

    dashboard_id = sys.argv[1].strip()
    db_id = sys.argv[2].strip()

    if not os.environ.get("NOTION_API_KEY"):
        load_env_from_file(Path.home() / "ai-agents" / ".env")

    kst = timezone(timedelta(hours=9))
    now = datetime.now(tz=kst).strftime("%Y-%m-%d %H:%M KST")
    title = f"자동 요약 ({now})"

    container_id = find_container_toggle(dashboard_id)
    if not container_id:
        container_id = create_toggle_on_page(dashboard_id, title)

    # persist
    st = load_state()
    st.setdefault("notion", {})["dashboard_summary_container_id"] = container_id
    save_state(st)

    # update title
    update_toggle_title(container_id, title)

    # wipe children
    for child in list_children(container_id):
        delete_block(child["id"])

    # append new children
    append_children(container_id, build_children(db_id))

    print("ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
