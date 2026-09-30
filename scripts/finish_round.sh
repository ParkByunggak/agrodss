#!/bin/bash
# scripts/finish_round.sh — 세션 회차의 **마감 체인**을 한 경로로: 문서 검사 → 대장 페이지 생성 → 넘침 검사 → 커밋 → 핸드오버 해시 기재 커밋 → 푸시 → 대장 페이지 재생성.
#
# [R-8 2026-09-30] `pytest … | tail -1 && python build_ledger_page.py … | tail -1 && git commit` 체인이 관문 수집 오류와 생성기 단언 실패를
# **둘 다** tail 의 rc 0 뒤에 삼켜 8b0b8c8 이 빨간 채 원격에 갔다. 셸 except fail-open 의 파이프 형태(HEREDOC-1 의 `>/dev/null` 과 뿌리가 같다).
# 규율("체인은 set -o pipefail · 출력은 파일로 받고 rc 를 본다")을 문서에만 두면 세 번째에 또 난다 — HEREDOC-1 이 그랬다. 그래서 경로다.
#
# 쓰는 법   bash scripts/finish_round.sh <커밋 메시지 파일> [해시 기재 커밋의 짧은 설명]
#          LEDGER_OUT=<대장 페이지 출력 경로>(기본 $TMPDIR/agrodss_ledger.html) · NO_PUSH=1 이면 푸시하지 않는다
# 하는 일   ① 문서·대장 페이지 검사(pytest → 파일 · rc) ② 대장 페이지 생성(→ 파일 · rc) ③ 정적 넘침 검사(rc) ④ git add -A · commit -F
#          ⑤ 핸드오버의 "(이 커밋 X)" · "이 커밋 X" 자리를 방금 해시로 채우고 그 한 파일만 커밋 ⑥ 푸시(지수 대기 · 네 번) ⑦ 대장 페이지 재생성
# 규율     set -euo pipefail — 어느 단계든 rc≠0 이면 거기서 멈추고 **그 단계의 로그 꼬리**를 보인다(조용히 다음으로 가지 않는다)
#          관문(전체 pytest)·주입·걷기는 이 스크립트 **앞**의 몫이다 — 여기는 그 뒤의 마감만
set -euo pipefail
MSG="${1:?커밋 메시지 파일}"
LABEL="${2:-표 행}"
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/.." && pwd)"
OUT="${LEDGER_OUT:-${TMPDIR:-/tmp}/agrodss_ledger.html}"
LOG="$(mktemp "${TMPDIR:-/tmp}/agrodss_finish_XXXX.log")"
cd "$ROOT"

step() { echo "== $1"; }
fail() { echo "!! $1 실패 (rc=$2) — 로그 꼬리:"; tail -n 15 "$LOG"; exit "$2"; }

step "문서·대장 페이지 검사"
TZ=Asia/Seoul python -B -m pytest -p no:cacheprovider -q tests/test_build_ledger_page.py tests/test_first_farm_literals.py > "$LOG" 2>&1 || fail "검사" $?
tail -n 1 "$LOG"

step "대장 페이지 생성 → $OUT"
python scripts/build_ledger_page.py "$OUT" > "$LOG" 2>&1 || fail "대장 페이지 생성" $?
tail -n 1 "$LOG"

step "정적 넘침 검사"
NODE_PATH="$(npm root -g)" node scripts/browser/static_overflow.cjs "$OUT" > "$LOG" 2>&1 || fail "넘침 검사" $?
tail -n 3 "$LOG"

step "커밋"
git add -A
git status --short
git commit -q -F "$MSG"
H="$(git rev-parse --short HEAD)"
echo "HEAD $H"

if grep -q "이 커밋 X" docs/handover_20260919.md; then
  step "핸드오버 해시 기재 → $H"
  sed -i "s/(이 커밋 X)/$H/; s/이 커밋 X\b/$H/g" docs/handover_20260919.md
  printf 'docs: 핸드오버 — %s 해시 기재(%s)\n\nCo-Authored-By: Claude Fable 5.1 <noreply@anthropic.com>\nClaude-Session: https://claude.ai/code/session_01QP3adTM3PKy9M3tMgSUL4L\n' "$H" "$LABEL" > "$LOG"
  git commit -q -am "$(cat "$LOG")"
  echo "docs $(git rev-parse --short HEAD)"
fi

if [ "${NO_PUSH:-0}" != "1" ]; then
  step "푸시"
  ok=0
  for d in 0 2 4 8 16; do
    sleep "$d"
    if git push -u origin main > "$LOG" 2>&1; then ok=1; break; fi
    echo "푸시 실패 — ${d}s 뒤 다시"
  done
  [ "$ok" = "1" ] || fail "푸시" 1
  tail -n 1 "$LOG"
fi

step "대장 페이지 재생성(해시 기재 뒤)"
python scripts/build_ledger_page.py "$OUT" > "$LOG" 2>&1 || fail "대장 페이지 재생성" $?
tail -n 1 "$LOG"
git log --oneline -3
git status -sb | head -n 1
