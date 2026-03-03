#!/usr/bin/env bash
set -euo pipefail

# 사용법:
# MINI_HOST=192.168.0.20 MINI_USER=kimhyunhomacmini bash scripts/setup_macbook.sh
# (기본값) MINI_USER=kimhyunhomacmini, TARGET_DIR=~/projects

MINI_HOST="${MINI_HOST:-}"
MINI_USER="${MINI_USER:-kimhyunhomacmini}"
TARGET_DIR="${TARGET_DIR:-$HOME/projects}"
ARCHIVE_NAME="war-room-dashboard-latest.tgz"
REMOTE_PATH="/Users/kimhyunhomacmini/.openclaw/workspace/${ARCHIVE_NAME}"

if [[ -z "$MINI_HOST" ]]; then
  echo "[ERROR] MINI_HOST를 지정해 주세요. 예) MINI_HOST=192.168.0.20 bash scripts/setup_macbook.sh"
  exit 1
fi

mkdir -p "$TARGET_DIR"
cd "$TARGET_DIR"

echo "[1/5] 맥미니에서 아카이브 받는 중..."
scp "${MINI_USER}@${MINI_HOST}:${REMOTE_PATH}" "./${ARCHIVE_NAME}"

echo "[2/5] 압축 해제..."
rm -rf war-room-dashboard
mkdir -p war-room-dashboard
tar -xzf "${ARCHIVE_NAME}" -C .

echo "[3/5] 의존성 설치..."
cd war-room-dashboard
npm install

echo "[4/5] 서버 실행..."
echo "-----------------------------------------"
echo "접속 URL: http://localhost:4177"
echo "종료: Ctrl + C"
echo "-----------------------------------------"

npm run dev
