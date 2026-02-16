#!/usr/bin/env python3
"""Fill each project row page in the Projects DB with a detailed documentation-style template.

Approach
- For each database row (page), upsert a single managed toggle block titled "프로젝트 문서(자동 생성)".
- Replace that toggle's children on each run (delete old children under the managed toggle only).

Safety
- Does not change DB schema.
- Does not delete anything outside the managed toggle per project page.
- Reads NOTION_API_KEY from env; if missing, loads from ~/ai-agents/.env.

Usage
  python3 scripts/notion_fill_project_pages.py <projects_db_id>

Optional env
  NOTION_PROJECT_DOC_STATE=path/to/state.json
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
    p = os.environ.get("NOTION_PROJECT_DOC_STATE")
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
    url = f"https://api.notion.com/v1/blocks/{block_id}"
    r = requests.delete(url, headers=headers(), timeout=30)
    if r.status_code >= 300:
        raise RuntimeError(f"delete failed: {r.status_code} {r.text[:200]}")


def append_children(block_id: str, children: list[dict]) -> None:
    url = f"https://api.notion.com/v1/blocks/{block_id}/children"
    r = requests.patch(url, headers=headers(), json={"children": children}, timeout=30)
    if r.status_code >= 300:
        raise RuntimeError(f"append failed: {r.status_code} {r.text[:200]}")


def create_toggle_on_page(page_id: str, title: str) -> str:
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
    results = js.get("results") or js.get("children")
    if not results:
        raise RuntimeError("unexpected create response (no results)")
    return results[0]["id"]


def update_toggle_title(block_id: str, title: str) -> None:
    url = f"https://api.notion.com/v1/blocks/{block_id}"
    payload = {
        "toggle": {
            "rich_text": [{"type": "text", "text": {"content": title}}]
        }
    }
    r = requests.patch(url, headers=headers(), json=payload, timeout=30)
    if r.status_code >= 300:
        raise RuntimeError(f"update toggle failed: {r.status_code} {r.text[:200]}")


def get_prop_select(props: dict, name: str) -> str | None:
    v = props.get(name)
    if not v:
        return None
    sel = v.get("select")
    if sel and isinstance(sel, dict):
        return sel.get("name")
    return None


def get_prop_rich_text(props: dict, name: str) -> str | None:
    v = props.get(name)
    if not v:
        return None
    rt = v.get("rich_text")
    if rt and isinstance(rt, list):
        return "".join([x.get("plain_text", "") for x in rt]).strip() or None
    return None


def get_prop_url(props: dict, name: str) -> str | None:
    v = props.get(name)
    if not v:
        return None
    return v.get("url") or None


def get_title(props: dict) -> str:
    t = props.get("프로젝트", {}).get("title", [])
    return "".join([x.get("plain_text", "") for x in t]).strip() or "(untitled)"


def kst_now() -> str:
    kst = timezone(timedelta(hours=9))
    return datetime.now(tz=kst).strftime("%Y-%m-%d %H:%M KST")


def build_doc_children(title: str, props: dict, page_url: str) -> list[dict]:
    status = get_prop_select(props, "상태") or "(미설정)"
    prio = get_prop_select(props, "우선순위") or "(미설정)"
    memo = get_prop_rich_text(props, "메모") or "(없음)"
    link = get_prop_url(props, "링크") or ""

    def p(text: str) -> dict:
        return {"type": "paragraph", "paragraph": {"rich_text": [{"type": "text", "text": {"content": text}}]}}

    def h2(text: str) -> dict:
        return {"type": "heading_2", "heading_2": {"rich_text": [{"type": "text", "text": {"content": text}}]}}

    def h3(text: str) -> dict:
        return {"type": "heading_3", "heading_3": {"rich_text": [{"type": "text", "text": {"content": text}}]}}

    def b(text: str) -> dict:
        return {"type": "bulleted_list_item", "bulleted_list_item": {"rich_text": [{"type": "text", "text": {"content": text}}]}}

    blocks: list[dict] = [
        h2("요약"),
        p(f"- 현재 상태: {status} / 우선순위: {prio}"),
        p(f"- 마지막 템플릿 갱신: {kst_now()}"),
        p(f"- DB 메모: {memo}"),
    ]
    if link:
        blocks.append({
            "type": "paragraph",
            "paragraph": {
                "rich_text": [
                    {"type": "text", "text": {"content": "관련 링크: ",}},
                    {"type": "text", "text": {"content": link, "link": {"url": link}}},
                ]
            },
        })

    blocks += [
        h2("목표 / Done 정의"),
        b("이 프로젝트가 ‘완료’라고 말할 수 있는 조건을 2~5개로 정의"),
        b("사용자/운영 관점에서 성공 기준 포함"),
        h2("현재 상황"),
        b("최근 변경/결정 사항 요약"),
        b("막히는 지점/리스크/의존성"),
        h2("다음 액션"),
        {"type": "to_do", "to_do": {"rich_text": [{"type": "text", "text": {"content": "가장 중요한 다음 행동 1개"}}], "checked": False}},
        {"type": "to_do", "to_do": {"rich_text": [{"type": "text", "text": {"content": "그 다음 행동 1개"}}], "checked": False}},
        h2("운영/배포/런북"),
        b("서비스 재시작/장애 대응 방법"),
        b("중요 환경변수/시크릿 위치(값은 적지 말고 ‘어디에 있다’만)"),
        b("로그/모니터링 포인트"),
        h2("관련 자료"),
        {"type": "bulleted_list_item", "bulleted_list_item": {"rich_text": [
            {"type": "text", "text": {"content": "Notion row URL: ",}},
            {"type": "text", "text": {"content": page_url, "link": {"url": page_url}}},
        ]}},
    ]

    return blocks


def upsert_project_doc(page_id: str, title: str, props: dict, page_url: str) -> None:
    # Find managed toggle
    container_title_prefix = "프로젝트 문서(자동 생성)"
    container_id = None
    for blk in list_children(page_id):
        if blk.get("type") != "toggle":
            continue
        rt = (blk.get("toggle") or {}).get("rich_text", [])
        text = "".join([x.get("plain_text", "") for x in rt]).strip()
        if text.startswith(container_title_prefix):
            container_id = blk.get("id")
            break

    if not container_id:
        container_id = create_toggle_on_page(page_id, f"{container_title_prefix} — {kst_now()}")
    else:
        update_toggle_title(container_id, f"{container_title_prefix} — {kst_now()}")

    # wipe children under container
    for child in list_children(container_id):
        delete_block(child["id"])

    append_children(container_id, build_doc_children(title, props, page_url))


def main() -> int:
    if len(sys.argv) != 2:
        print("usage: notion_fill_project_pages.py <projects_db_id>", file=sys.stderr)
        return 2

    db_id = sys.argv[1].strip()

    if not os.environ.get("NOTION_API_KEY"):
        load_env_from_file(Path.home() / "ai-agents" / ".env")

    cursor = None
    total = 0
    while True:
        js = db_query(db_id, cursor)
        rows = js.get("results", [])
        for r in rows:
            page_id = r.get("id")
            props = r.get("properties", {})
            title = get_title(props)
            url = r.get("url")
            upsert_project_doc(page_id, title, props, url)
            total += 1
        if not js.get("has_more"):
            break
        cursor = js.get("next_cursor")

    print(f"ok: updated {total} pages")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
