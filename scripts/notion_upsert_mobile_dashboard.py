#!/usr/bin/env python3
"""Upsert a mobile-first dashboard section on a Notion page.

- Creates/uses a single managed toggle container: "📱 모바일 대시보드(자동)".
- Replaces only that container's children on each run.
- Shows: P0 list, Blockers list, and per-project quick toggles.

Usage:
  python3 scripts/notion_upsert_mobile_dashboard.py <dashboard_page_id> <projects_db_id>
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
STATE_PATH = Path.home() / ".openclaw" / "workspace" / "memory" / "notion_state.json"


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


def state_load() -> dict:
    if not STATE_PATH.exists():
        return {}
    try:
        return json.loads(STATE_PATH.read_text())
    except Exception:
        return {}


def state_save(st: dict) -> None:
    STATE_PATH.parent.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(json.dumps(st, ensure_ascii=False, indent=2) + "\n")


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


def update_toggle_title(block_id: str, title: str) -> None:
    r = requests.patch(
        f"https://api.notion.com/v1/blocks/{block_id}",
        headers=headers(),
        json={"toggle": {"rich_text": [{"type": "text", "text": {"content": title}}]}},
        timeout=30,
    )
    if r.status_code >= 300:
        raise RuntimeError(f"update title failed: {r.status_code} {r.text[:200]}")


def create_toggle_on_page(page_id: str, title: str) -> str:
    r = requests.patch(
        f"https://api.notion.com/v1/blocks/{page_id}/children",
        headers=headers(),
        json={
            "children": [
                {"type": "toggle", "toggle": {"rich_text": [{"type": "text", "text": {"content": title}}], "children": []}}
            ]
        },
        timeout=30,
    )
    if r.status_code >= 300:
        raise RuntimeError(f"create toggle failed: {r.status_code} {r.text[:200]}")
    js = r.json()
    results = js.get("results") or js.get("children")
    if not results:
        raise RuntimeError("unexpected create response")
    return results[0]["id"]


def db_query(db_id: str, payload: dict) -> list[dict]:
    r = requests.post(
        f"https://api.notion.com/v1/databases/{db_id}/query",
        headers=headers(),
        json=payload,
        timeout=30,
    )
    if r.status_code >= 300:
        raise RuntimeError(f"db query failed: {r.status_code} {r.text[:200]}")
    return r.json().get("results", [])


def title_of(row: dict) -> str:
    t = row.get("properties", {}).get("프로젝트", {}).get("title", [])
    return "".join([x.get("plain_text", "") for x in t]).strip() or "(untitled)"


def select_of(row: dict, prop: str) -> str:
    sel = row.get("properties", {}).get(prop, {}).get("select")
    return (sel or {}).get("name") or "(미설정)"


def rt(text: str) -> list[dict]:
    return [{"type": "text", "text": {"content": text}}]


def link_item(label: str, url: str) -> dict:
    return {
        "type": "bulleted_list_item",
        "bulleted_list_item": {
            "rich_text": [
                {"type": "text", "text": {"content": label, "link": {"url": url}}},
            ]
        },
    }


def main() -> int:
    if len(sys.argv) != 3:
        print("usage: notion_upsert_mobile_dashboard.py <dashboard_page_id> <projects_db_id>", file=sys.stderr)
        return 2

    page_id = sys.argv[1].strip()
    db_id = sys.argv[2].strip()

    if not os.environ.get("NOTION_API_KEY"):
        load_env_from_file(Path.home() / "ai-agents" / ".env")

    kst = timezone(timedelta(hours=9))
    now = datetime.now(tz=kst).strftime("%Y-%m-%d %H:%M KST")

    st = state_load()
    container_id = (st.get("notion", {}) or {}).get("mobile_dashboard_container_id")

    if not container_id:
        # scan existing
        for blk in list_children(page_id):
            if blk.get("type") != "toggle":
                continue
            txt = "".join([x.get("plain_text", "") for x in (blk.get("toggle") or {}).get("rich_text", [])]).strip()
            if txt.startswith("📱 모바일 대시보드"):
                container_id = blk.get("id")
                break

    if not container_id:
        container_id = create_toggle_on_page(page_id, f"📱 모바일 대시보드(자동) — {now}")

    st.setdefault("notion", {})["mobile_dashboard_container_id"] = container_id
    state_save(st)

    update_toggle_title(container_id, f"📱 모바일 대시보드(자동) — {now}")

    # wipe managed children
    for child in list_children(container_id):
        delete_block(child["id"])

    # query P0 and blockers
    p0 = db_query(
        db_id,
        {
            "page_size": 20,
            "filter": {"property": "우선순위", "select": {"equals": "P0"}},
            "sorts": [{"property": "마지막 업데이트", "direction": "descending"}],
        },
    )
    blockers = db_query(
        db_id,
        {
            "page_size": 20,
            "filter": {"property": "상태", "select": {"equals": "🔴"}},
            "sorts": [{"property": "마지막 업데이트", "direction": "descending"}],
        },
    )
    all_rows = db_query(db_id, {"page_size": 100})

    children: list[dict] = [
        {"type": "callout", "callout": {"icon": {"type": "emoji", "emoji": "✅"}, "rich_text": rt("모바일 기준: P0/블로커만 먼저 보고, 각 프로젝트는 ‘다음 액션’ 1~2개만 유지.")}},
        {"type": "heading_3", "heading_3": {"rich_text": rt("P0 (지금)")}},
    ]

    if p0:
        for r in p0[:10]:
            children.append(link_item(title_of(r), r.get("url")))
    else:
        children.append({"type": "bulleted_list_item", "bulleted_list_item": {"rich_text": rt("(없음)")}})

    children.append({"type": "heading_3", "heading_3": {"rich_text": rt("🔴 블로커")}})
    if blockers:
        for r in blockers[:10]:
            children.append(link_item(title_of(r), r.get("url")))
    else:
        children.append({"type": "bulleted_list_item", "bulleted_list_item": {"rich_text": rt("(없음)")}})

    children.append({"type": "divider", "divider": {}})
    children.append({"type": "heading_3", "heading_3": {"rich_text": rt("프로젝트 빠른보기")}})

    # compact per-project toggles
    for r in all_rows:
        t = title_of(r)
        status = select_of(r, "상태")
        prio = select_of(r, "우선순위")
        url = r.get("url")
        children.append(
            {
                "type": "toggle",
                "toggle": {
                    "rich_text": rt(f"{status} {prio} · {t}"),
                    "children": [
                        {"type": "paragraph", "paragraph": {"rich_text": [
                            {"type": "text", "text": {"content": "프로젝트 카드: ",}},
                            {"type": "text", "text": {"content": "열기", "link": {"url": url}}},
                        ]}},
                        {"type": "to_do", "to_do": {"rich_text": rt("다음 액션 1"), "checked": False}},
                        {"type": "to_do", "to_do": {"rich_text": rt("다음 액션 2"), "checked": False}},
                    ],
                },
            }
        )

    append_children(container_id, children)
    print("ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
