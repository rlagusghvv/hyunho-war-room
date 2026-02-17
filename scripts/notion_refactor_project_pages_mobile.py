#!/usr/bin/env python3
"""Refactor each project row page to be mobile-friendly.

For each DB row page, upsert a managed toggle:
  "📱 프로젝트 요약(모바일)"

Inside it, keep content compact:
- Callout: status/prio + one-line memo
- Next actions: 2 checkboxes
- Toggles: Risks / Runbook / Links (kept short)

This replaces only children under the managed toggle per page.

Usage:
  python3 scripts/notion_refactor_project_pages_mobile.py <projects_db_id>
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


def db_query(db_id: str, start_cursor: str | None = None) -> dict:
    url = f"https://api.notion.com/v1/databases/{db_id}/query"
    payload: dict = {"page_size": 100}
    if start_cursor:
        payload["start_cursor"] = start_cursor
    r = requests.post(url, headers=headers(), json=payload, timeout=30)
    if r.status_code >= 300:
        raise RuntimeError(f"db query failed: {r.status_code} {r.text[:200]}")
    return r.json()


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


def create_toggle_on_page(page_id: str, title: str) -> str:
    r = requests.patch(
        f"https://api.notion.com/v1/blocks/{page_id}/children",
        headers=headers(),
        json={"children": [{"type": "toggle", "toggle": {"rich_text": [{"type": "text", "text": {"content": title}}], "children": []}}]},
        timeout=30,
    )
    if r.status_code >= 300:
        raise RuntimeError(f"create toggle failed: {r.status_code} {r.text[:200]}")
    js = r.json()
    results = js.get("results") or js.get("children")
    if not results:
        raise RuntimeError("unexpected create response")
    return results[0]["id"]


def update_toggle_title(block_id: str, title: str) -> None:
    r = requests.patch(
        f"https://api.notion.com/v1/blocks/{block_id}",
        headers=headers(),
        json={"toggle": {"rich_text": [{"type": "text", "text": {"content": title}}]}},
        timeout=30,
    )
    if r.status_code >= 300:
        raise RuntimeError(f"update toggle failed: {r.status_code} {r.text[:200]}")


def title_of(props: dict) -> str:
    t = props.get("프로젝트", {}).get("title", [])
    return "".join([x.get("plain_text", "") for x in t]).strip() or "(untitled)"


def select_of(props: dict, name: str) -> str:
    sel = props.get(name, {}).get("select")
    return (sel or {}).get("name") or "(미설정)"


def rich_of(props: dict, name: str) -> str:
    rt = props.get(name, {}).get("rich_text")
    if not rt:
        return ""
    return "".join([x.get("plain_text", "") for x in rt]).strip()


def url_of(props: dict, name: str) -> str:
    return props.get(name, {}).get("url") or ""


def rt(text: str) -> list[dict]:
    return [{"type": "text", "text": {"content": text}}]


def kst_now() -> str:
    kst = timezone(timedelta(hours=9))
    return datetime.now(tz=kst).strftime("%Y-%m-%d %H:%M KST")


def build_children(props: dict, page_url: str) -> list[dict]:
    status = select_of(props, "상태")
    prio = select_of(props, "우선순위")
    memo = rich_of(props, "메모") or "(메모 없음)"
    link = url_of(props, "링크")

    children: list[dict] = [
        {
            "type": "callout",
            "callout": {
                "icon": {"type": "emoji", "emoji": "📌"},
                "rich_text": rt(f"{status} / {prio} · {memo}"),
            },
        },
        {"type": "paragraph", "paragraph": {"rich_text": rt(f"last update: {kst_now()}")}},
        {"type": "heading_3", "heading_3": {"rich_text": rt("Next actions")}},
        {"type": "to_do", "to_do": {"rich_text": rt("다음 액션 1"), "checked": False}},
        {"type": "to_do", "to_do": {"rich_text": rt("다음 액션 2"), "checked": False}},
        {
            "type": "toggle",
            "toggle": {
                "rich_text": rt("리스크/의존성"),
                "children": [
                    {"type": "bulleted_list_item", "bulleted_list_item": {"rich_text": rt("(없음/미정)")}},
                ],
            },
        },
        {
            "type": "toggle",
            "toggle": {
                "rich_text": rt("운영/런북"),
                "children": [
                    {"type": "bulleted_list_item", "bulleted_list_item": {"rich_text": rt("재시작/장애 대응 요약")}},
                    {"type": "bulleted_list_item", "bulleted_list_item": {"rich_text": rt("시크릿 값은 적지 말고 위치만")}},
                ],
            },
        },
    ]

    if link:
        children.append({
            "type": "toggle",
            "toggle": {
                "rich_text": rt("링크"),
                "children": [
                    {"type": "bulleted_list_item", "bulleted_list_item": {"rich_text": [
                        {"type": "text", "text": {"content": link, "link": {"url": link}}}
                    ]}},
                    {"type": "bulleted_list_item", "bulleted_list_item": {"rich_text": [
                        {"type": "text", "text": {"content": "Notion row URL", "link": {"url": page_url}}}
                    ]}},
                ],
            },
        })
    else:
        children.append({
            "type": "toggle",
            "toggle": {
                "rich_text": rt("링크"),
                "children": [
                    {"type": "bulleted_list_item", "bulleted_list_item": {"rich_text": [
                        {"type": "text", "text": {"content": "Notion row URL", "link": {"url": page_url}}}
                    ]}},
                ],
            },
        })

    return children


def upsert_mobile_toggle(page_id: str, props: dict, page_url: str) -> None:
    prefix = "📱 프로젝트 요약(모바일)"
    toggle_id = None
    for blk in list_children(page_id):
        if blk.get("type") != "toggle":
            continue
        txt = "".join([x.get("plain_text", "") for x in (blk.get("toggle") or {}).get("rich_text", [])]).strip()
        if txt.startswith(prefix):
            toggle_id = blk.get("id")
            break

    title = title_of(props)
    if not toggle_id:
        toggle_id = create_toggle_on_page(page_id, f"{prefix} — {title}")
    else:
        update_toggle_title(toggle_id, f"{prefix} — {title}")

    for child in list_children(toggle_id):
        delete_block(child["id"])

    append_children(toggle_id, build_children(props, page_url))


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: notion_refactor_project_pages_mobile.py <projects_db_id>", file=sys.stderr)
        return 2

    db_id = sys.argv[1].strip()

    if not os.environ.get("NOTION_API_KEY"):
        load_env_from_file(Path.home() / "ai-agents" / ".env")

    cursor = None
    total = 0
    while True:
        js = db_query(db_id, cursor)
        for row in js.get("results", []):
            page_id = row.get("id")
            props = row.get("properties", {})
            url = row.get("url")
            upsert_mobile_toggle(page_id, props, url)
            total += 1
        if not js.get("has_more"):
            break
        cursor = js.get("next_cursor")

    print(f"ok: updated {total} pages")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
