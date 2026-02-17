#!/usr/bin/env python3
"""Append project-by-project overview sections to the clean dashboard.

Usage:
  python3 scripts/notion_append_all_project_overviews.py <dashboard_page_id> <projects_db_id>

Notes:
- Non-destructive: appends blocks only.
- Builds sections for key projects by matching title keywords.
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


def find_row(rows: list[dict], keywords: list[str]) -> dict | None:
    for r in rows:
        t = title_of(r)
        if all(k.lower() in t.lower() for k in keywords):
            return r
    # fallback: any keyword match
    for r in rows:
        t = title_of(r)
        if any(k.lower() in t.lower() for k in keywords):
            return r
    return None


def rt(text: str) -> list[dict]:
    return [{"type": "text", "text": {"content": text}}]


def link_para(label: str, url: str) -> dict:
    return {
        "type": "paragraph",
        "paragraph": {
            "rich_text": [
                {"type": "text", "text": {"content": label + ": "}},
                {"type": "text", "text": {"content": "열기", "link": {"url": url}}},
            ]
        },
    }


def section(title: str, emoji: str, desc: str, row_url: str | None, bullets: list[str], todos: list[str]) -> list[dict]:
    blocks: list[dict] = [
        {"type": "divider", "divider": {}},
        {"type": "heading_2", "heading_2": {"rich_text": rt(title)}},
        {"type": "callout", "callout": {"icon": {"type": "emoji", "emoji": emoji}, "rich_text": rt(desc)}},
    ]
    if row_url:
        blocks.append(link_para("프로젝트 카드(상세 문서)", row_url))

    blocks.append({"type": "heading_3", "heading_3": {"rich_text": rt("핵심 포인트")}})
    for b in bullets:
        blocks.append({"type": "bulleted_list_item", "bulleted_list_item": {"rich_text": rt(b)}})

    blocks.append({"type": "heading_3", "heading_3": {"rich_text": rt("다음 액션")}})
    for t in todos:
        blocks.append({"type": "to_do", "to_do": {"rich_text": rt(t), "checked": False}})

    return blocks


def main() -> int:
    if len(sys.argv) != 3:
        print("usage: notion_append_all_project_overviews.py <dashboard_page_id> <projects_db_id>", file=sys.stderr)
        return 2

    page_id = sys.argv[1].strip()
    db_id = sys.argv[2].strip()

    if not os.environ.get("NOTION_API_KEY"):
        load_env(Path.home() / "ai-agents" / ".env")

    kst = timezone(timedelta(hours=9))
    now = datetime.now(tz=kst).strftime("%Y-%m-%d %H:%M KST")

    rows = query_db(db_id)

    r_ai = find_row(rows, ["ai-agents"]) or find_row(rows, ["트레이더", "브릿지"]) 
    r_ops = find_row(rows, ["OpenClaw"]) or find_row(rows, ["Telegram", "운영"]) 
    r_tesla = find_row(rows, ["tesla-info"]) or find_row(rows, ["speed", "camera"]) 
    r_front = find_row(rows, ["frontend_skills"]) or find_row(rows, ["Design", "Polish"]) 

    blocks: list[dict] = [
        {"type": "divider", "divider": {}},
        {"type": "heading_2", "heading_2": {"rich_text": rt("프로젝트별 요약")}},
        {"type": "paragraph", "paragraph": {"rich_text": rt(f"last update: {now}")}},
    ]

    blocks += section(
        title="ai-agents (트레이더삼/그로쓰/브릿지)",
        emoji="🧠",
        desc="텔레그램 봇과 내부 에이전트(OpenClaw) 연동 운영. 안정성/UX가 핵심.",
        row_url=(r_ai or {}).get("url") if r_ai else None,
        bullets=[
            "사용자 체감 이슈: 무응답/지연/5xx 메시지 UX",
            "브릿지: typing/진행 알림 + 재시도/백오프 + 장애 원인 로깅",
            "OpenClaw: OAuth 토큰 만료/갱신 실패 시 500 → 재인증/자동 재시작으로 완화",
        ],
        todos=[
            "(P0) 브릿지 long-task UX: typing 유지 + 8초 nudge 1회 + 최종 응답 확실히",
            "(P1) 브릿지 retry/backoff + idempotency(중복 답장 방지) 추가",
            "(P2) 장애 알림: 재시작 루프/업스트림 5xx 감지 시 요약 알림",
        ],
    )

    blocks += section(
        title="OpenClaw Gateway/Telegram 보안·운영",
        emoji="🛡️",
        desc="DM allowlist, heartbeat 절제, self-heal(Colima/OpenClaw)로 운영 안정화.",
        row_url=(r_ops or {}).get("url") if r_ops else None,
        bullets=[
            "Telegram DM: allowlist(현호 id)로 잠금",
            "Heartbeat: 30m + active hours로 스팸 방지",
            "OpenClaw healthwatch: 500/비정상 감지 시 gateway 재시작",
        ],
        todos=[
            "(P0) OpenClaw configure 완전 종료/고정(인증 안정화)",
            "(P1) 보안 점검 deep audit 정기 실행(월 1회)",
        ],
    )

    blocks += section(
        title="tesla-info (speed camera dataset)",
        emoji="🚗",
        desc="속도카메라 데이터 최신화/엔드포인트 검증 + 두 데이터셋(파일/오픈API) 보관.",
        row_url=(r_tesla or {}).get("url") if r_tesla else None,
        bullets=[
            "fileData 방식: 39,735 카메라 / datasetsFetched 126",
            "OpenAPI 방식 결과도 보관(openapi.min.json)",
            "docker-compose env_file + /app/data 볼륨으로 호스트에 영속",
        ],
        todos=[
            "(P1) 업데이트 주기 정하고(예: 월 1회) 자동화 여부 결정",
            "(P2) API 응답 필드(예: datasetsFetched) 일관성 정리",
        ],
    )

    blocks += section(
        title="frontend_skills (Design Contract + Polish Pass)",
        emoji="🎨",
        desc="UI/프론트 작업 품질을 계약(Contract)+검수 Pass로 표준화.",
        row_url=(r_front or {}).get("url") if r_front else None,
        bullets=[
            "contracts/DESIGN_CONTRACT.md 기반",
            "UI_POLISH_PASS / STATE_COVERAGE_PASS 등 패스 프롬프트 구비",
            "ui/young 에이전트 SOUL에 기본 적용",
        ],
        todos=[
            "(P1) 실제 프로젝트 1개에 적용해서 체크리스트 보정",
            "(P2) 릴리즈 전용 UI 체크리스트를 팀 룰로 고정",
        ],
    )

    append_blocks(page_id, blocks)
    print("ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
