#!/bin/bash
# scripts/date_sweep.sh — 전체 검사를 **앞날 몇 날로 옮겨** 돌린다. 달력이 움직이면 붉어질 검사를 미리 센다(읽기 전용 측정).
#
# [달력 걷기 2026-10-14] 10-14(수확 창이 열린 날) 새 컨테이너의 첫 관문이 붉었다 — 코드는 그대로인데 **날이 바뀌어서**. 몰 검사가 「촬영 예정」 을
# 실제 오늘로 찾았고 그날 마지막 촬영 창이 열려 그 말이 화면에서 사라졌다(화면은 맞았다). 셋 날(오늘 · 10-20 · 11-10)로 전체를 돌려 같은 꼴을 세니
# 둘(몰 · 판단 화면)이었다. 그 측정은 일회용 명령이었다 — 다음 경계(11-03 수확 창 끝 · 달력 끝)에 다시 해야 하므로 경로로 둔다(time_walk · answer_walk 와 같은 길).
#
# 쓰는 법   bash scripts/date_sweep.sh YYYY-MM-DD [YYYY-MM-DD …]       날짜마다 전체 검사 1회 — 날짜 하나에 3~4분
#          SWEEP_DIR=<출력 폴더>(기본 $TMPDIR/agrodss_sweep)
# 내는 것   날짜마다 「N passed · M failed · K error」 와 실패 이름 — 셋 중 하나라도 붉으면 rc≠0
# 규율     AGRODSS_TODAY 만 바꾼다(화면 · 판정이 읽는 오늘). 검사가 날짜를 스스로 고정한 곳은 그대로다 — 붉은 것은 **오늘에 기대는 검사**다.
#          관문(gate.sh)을 대신하지 않는다 — 관문은 실제 오늘 한 번이고, 이것은 그 옆의 측정이다. 도는 동안 소스를 고치지 않는다
set -uo pipefail
HERE="$(cd "$(dirname "$0")" && pwd)"
ROOT="$(cd "$HERE/.." && pwd)"
DIR="${SWEEP_DIR:-${TMPDIR:-/tmp}/agrodss_sweep}"
mkdir -p "$DIR"
cd "$ROOT"
export TZ="${TZ:-Asia/Seoul}"
[ "$#" -gt 0 ] || { echo "날짜를 하나 이상 주세요 — 예: bash scripts/date_sweep.sh 2026-11-03 2026-11-24"; exit 2; }

bad=0
for d in "$@"; do
  out="$DIR/sweep_$d.txt"
  AGRODSS_TODAY="$d" python -B -m pytest -p no:cacheprovider > "$out" 2>&1
  rc=$?
  line="$(grep -E "[0-9]+ (passed|failed)" "$out" | tail -n 1)"
  echo "== $d · rc=$rc · ${line:-집계 줄 없음 — 출력 $out}"
  grep -E "^(FAILED|ERROR) " "$out" | sed 's/^/   /'
  [ "$rc" = "0" ] && [ -n "$line" ] || bad=1
done
exit $bad
