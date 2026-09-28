#!/bin/bash
# scripts/browser/walk.sh — 격리된 서버를 띄워 실제 브라우저(Chromium + Playwright)로 화면을 걷는다. 읽기 전용 측정 도구.
#
# [U-35 2026-09-27] 2026-09-26 에 화면 처방 셋(입력칸 엔터 · 반응형 · 발행자 경로)을 이 길로 확인했는데 도구가 스크래치패드에만
# 있었다 — 세션이 끝나면 사라진다. 여기 두어 다음 사람이 같은 길로 확인한다. pytest 는 CSS 가 실제로 어떻게 놓이는지,
# 스크립트가 실제로 도는지 못 본다 — 그 빈틈을 이것이 메운다.
#
# 쓰는 법   bash scripts/browser/walk.sh [스크립트.cjs]      기본 walk.cjs · overflow.cjs 는 WIDTHS=390,768,1024,1400 로
# 필요     node · playwright(npm -g) · Chromium(/opt/pw-browsers/chromium 또는 PLAYWRIGHT_CHROMIUM 로 지정)
# 규율     운영 data/ 에는 아무것도 쓰지 않는다 — 모든 AGRODSS_* 경로를 tmp 아래로 돌린다(conftest 와 같은 목록 · 검사가 대조한다)
#          내리는 것은 이 스크립트가 띄운 PID 하나뿐이다(이름으로 죽이지 않는다)
set -u
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/../.." && pwd)"
W=$(mktemp -d "${TMPDIR:-/tmp}/agrodss_walk_XXXX")
PORT="${AGRODSS_WALK_PORT:-8799}"
cp "$ROOT/data/subjects.json" "$W/subjects.json"
cp "$ROOT/data/parcels_seed.json" "$W/parcels.json"
cp "$ROOT/data/crop_names.csv" "$W/crop_names.csv"
cp "$ROOT/data/organic/organic_materials_public.json" "$W/organic_materials_public.json"
# 사진 올리기 걷기용 — EXIF 없는 JPEG 하나(검사 헬퍼 재사용 · tmp 에만)
( cd "$ROOT" && PYTHONDONTWRITEBYTECODE=1 python -B -c 'import sys; sys.path.insert(0, "."); from tests.test_chat_upload_voice_lan import make_jpeg_with_exif; open(sys.argv[1], "wb").write(make_jpeg_with_exif(None))' "$W/KakaoTalk_20260923_074025068_04.jpg" )
export TZ=Asia/Seoul AGRODSS_TODAY="${AGRODSS_TODAY:-2026-09-24}" AGRODSS_FRONTEND_PORT="$PORT" AGRODSS_RELOAD=0
export AGRODSS_MEDIA_DIR="$W/media" AGRODSS_EVENTS_DIR="$W/events" AGRODSS_FEEDBACK_DIR="$W/feedback" AGRODSS_CHAT_DIR="$W/chat"
export AGRODSS_SUBJECTS_PATH="$W/subjects.json" AGRODSS_SUBJECTS_LOCAL_PATH="$W/subjects_local.json" AGRODSS_SUBJECTS_BACKUP_PATH="$W/subjects_backup.json"
export AGRODSS_PARCELS_PATH="$W/parcels.json" AGRODSS_PARCELS_LOCAL_PATH="$W/parcels_local.json" AGRODSS_PARCELS_LEGACY_PATH="$W/none.json"
export AGRODSS_PROFILE_PATH="$W/profile.json" AGRODSS_SOIL_DIR="$W/soil" AGRODSS_PSIS_DIR="$W/psis" AGRODSS_NAMES_DIR="$W/names" AGRODSS_NAMES_CSV="$W/crop_names.csv"
export AGRODSS_ORGANIC_PATH="$W/organic_materials_public.json"
export AGRODSS_NAMES_LOCAL_CSV="$W/crop_names_local.csv" AGRODSS_NAMES_BACKUP_CSV="$W/crop_names_backup.csv"
export AGRODSS_OUTLOOK_PATH="$W/climate_outlook.json"
cd "$ROOT"
PYTHONDONTWRITEBYTECODE=1 python -B frontend/serve.py --no-browser > "$W/server.log" 2>&1 &
PID=$!
for i in $(seq 1 30); do curl -s -m 2 "http://127.0.0.1:$PORT/running" >/dev/null 2>&1 && break; sleep 0.5; done
echo "server pid=$PID  $(curl -s -m 2 "http://127.0.0.1:$PORT/running" | tr '\n' ' ')"
SID=$(python -c 'import json,sys; print(json.load(open(sys.argv[1], encoding="utf-8"))["subjects"][0]["id"])' "$W/subjects.json")
NODE_PATH="$(npm root -g)" node "$HERE/${1:-walk.cjs}" "http://127.0.0.1:$PORT" "$SID" "$W"
RC=$?
kill "$PID" 2>/dev/null
wait "$PID" 2>/dev/null
echo "node rc=$RC"
echo "--- 운영 data 잔여(비어야 한다) ---"; git -C "$ROOT" status --short data/ | head
exit $RC
