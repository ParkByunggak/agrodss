#!/bin/bash
# scripts/gate.sh — 전체 관문을 **한 경로**로: 돌리고 · 출력을 파일로 받고 · 셈을 세어 한 줄로 낸다.
#
# [자기 도구 축 2026-10-06] 세션이 쓰던 명령에는 `-q` 가 붙어 있었고 `pytest.ini` 에 이미 `-q` 가 있어 **-qq** 가 됐다 — 그러면 집계 줄(「N passed」)이
# 안 찍힌다. 그런데 완료 보고 규율은 그 숫자를 요구한다(CLAUDE.md). 실제로 그 빈자리를 **사람이 손으로 점을 세어** 메웠고, 한 번은 집계 줄을 기다리는
# 폴링 루프가 **영원히 안 오는 줄**을 20분 기다렸다(그 줄은 올 수 없었다). 명령을 문서에 적어 두는 것으로는 세 번째에 또 난다 — 그래서 경로다(HEREDOC-1 과 같은 길).
#
# 쓰는 법   bash scripts/gate.sh [pytest 인자…]      — 인자 없으면 전체
#          GATE_OUT=<출력 파일>(기본 $TMPDIR/agrodss_gate.txt)
# 하는 일   ① TZ=Asia/Seoul · NODE_PATH(전역 npm) 을 **여기서** 세운다(잊을 자리를 없앤다 — 시각 결함은 TZ 없이는 재현되지 않는다)
#          ② `-q` 를 **더하지 않는다**(ini 의 -q 하나로 집계 줄이 남는다) · `-p no:cacheprovider` · `-B`
#          ③ 출력을 파일로 받고 **rc 를 보존**한다(파이프가 rc 를 삼킨 R-8 과 같은 축)
#          ④ `scripts/gate_count.py` 가 셈·증분·초록 여부를 판정한다 — rc≠0 이거나 실패·오류가 있거나 **집계 줄이 없으면** 이 스크립트도 rc≠0
# 규율     관문이 도는 동안 소스를 고치지 않는다(계측 오염). 주입·걷기·마감은 이 스크립트 밖(finish_round.sh 가 마감)
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/.." && pwd)"
OUT="${GATE_OUT:-${TMPDIR:-/tmp}/agrodss_gate.txt}"
cd "$ROOT"

export TZ="${TZ:-Asia/Seoul}"
if [ -z "${NODE_PATH:-}" ] && command -v npm > /dev/null 2>&1; then
  NODE_PATH="$(npm root -g 2>/dev/null)" && export NODE_PATH
fi

PARTIAL=""
[ "$#" -gt 0 ] && PARTIAL="--partial"        # 인자가 있으면 부분 스코프다 — 그 수를 직전 회차와 견주지 않는다

echo "== 관문 (TZ=$TZ · 출력 $OUT)${PARTIAL:+ · 부분 스코프}"
python -B -m pytest -p no:cacheprovider "$@" > "$OUT" 2>&1
rc=$?
tail -n 3 "$OUT"
python -m scripts.gate_count "$OUT" "$rc" $PARTIAL
gc=$?
[ "$rc" = "0" ] && [ "$gc" = "0" ] || { echo "!! 관문이 초록이 아니다 — 출력: $OUT"; grep -E "^(FAILED|ERROR) " "$OUT" | head -n 20; exit 1; }
