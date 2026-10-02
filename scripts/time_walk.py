# -*- coding: utf-8 -*-
# FILE: scripts/time_walk.py
# ROLE: 앞날 걷기 — 실제 재배 단위의 **모든 판정**을 지정한 날짜들(기본: 수확 창 앞뒤)에 미리 돌려 농가가 그날 받을 답의 종류·요약·메모를 한 표로 본다.
#   읽기 전용 측정 도구(원장은 읽기만 · 외부 원천은 키가 있으면 부른다 — 컨테이너엔 없어 '못 받은 이유' 가 그대로 보인다).
#
#   [U-35 형태 2026-10-02] 스크래치패드에서 한 번 돌려 결함 하나(수확 뒤 칸의 가뭄 답이 판단 불가(지식) — N/A 를 미채움으로 읽음)와 물음 하나(수확 칸 임계)를
#   잡았다. 세션이 끝나면 사라지므로 여기 둔다 — 칸 경계(10 · 30 · 50 · 70일)가 다가올 때마다 다음 사람이 같은 길로 미리 본다. pytest 는 고정된 날짜의
#   한 판정만 보고, 걷기(walk.sh)는 한 날짜의 화면만 본다 — **날짜를 가로지르는** 종류의 결함은 이것이 본다.
#
#   쓰는 법   python -m scripts.time_walk [YYYY-MM-DD ...]        날짜가 없으면 기준점 뒤 38 · 50 · 60 · 71 · 87일(칸 4 · 4/5 경계 · 5 · 6 · 6)
#            --only <재배 단위 id>  · --kind <종류>(그 종류만)
#   규율     아무것도 쓰지 않는다(검사가 data/ 해시를 전후 대조) · 값을 제안하지 않는다 — 종류와 문장을 보일 뿐이다
from __future__ import annotations

import argparse
import os
import sys
from datetime import date, timedelta
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
os.environ.setdefault("TZ", "Asia/Seoul")

from ingest import media  # noqa: E402
from judge import run as judge_run  # noqa: E402

DEFAULT_OFFSETS = (38, 50, 60, 71, 87)      # 칸 4 · 칸 4/5 경계일 · 칸 5 · 칸 6 첫날 · 칸 6 — 격자 jjokpa_autumn 의 경계 10/30/50/70 기준


def default_days(anchor: date) -> list[date]:
    return [anchor + timedelta(days=k) for k in DEFAULT_OFFSETS]


def walk(days: list[date], only: str | None = None) -> list[dict[str, Any]]:
    """날짜 × 재배 단위 × 판정 → 행. 봉투를 그대로 옮긴다(요약 · 사유 · 메모) — 가공하지 않는다."""
    rows: list[dict[str, Any]] = []
    for today in days:
        for s, envs, status in judge_run.all_judgments(today, only=only):
            anchor = s.get("anchor")
            day = (today - date.fromisoformat(anchor)).days if anchor else None
            for e in envs:
                r = e.result or {}
                rows.append({"date": today.isoformat(), "day": day, "subject": s.get("id"), "decision": e.decision_id, "kind": e.kind,
                             "grade": e.grade, "summary": str(r.get("summary") or ""), "why": str(r.get("why") or ""),
                             "notes": list(e.notes or []), "status": dict(status)})
    return rows


def render(rows: list[dict[str, Any]]) -> str:
    out: list[str] = []
    last = None
    for r in rows:
        key = (r["date"], r["subject"])
        if key != last:
            out.append(f"\n===== {r['date']} · {r['subject']} · 기준점 뒤 {r['day']}일 =====")
            out.append("  원천: " + " · ".join(f"{k}={v[:50]}" for k, v in r["status"].items()))
            last = key
        text = (r["summary"] or r["why"])[:140].replace("\n", " ")
        out.append(f"  {r['decision']:20} {r['kind']:12} {r['grade'] or '-':4} | {text}")
    return "\n".join(out).lstrip("\n")


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="앞날 걷기 — 모든 판정을 날짜별로 미리 돌린다(읽기 전용)")
    ap.add_argument("days", nargs="*", help="YYYY-MM-DD … (없으면 기준점 뒤 38·50·60·71·87일)")
    ap.add_argument("--only", help="재배 단위 id")
    ap.add_argument("--kind", help="이 종류만(예: '판단 불가(지식)')")
    a = ap.parse_args(argv)
    subs = [s for s in media.load_subjects() if (not a.only or s.get("id") == a.only) and s.get("anchor")]
    if not subs:
        print("기준점(심은 날)이 있는 재배 단위가 없다 — 걷기 대상 없음")
        return 1
    days = [date.fromisoformat(d) for d in a.days] if a.days else default_days(date.fromisoformat(subs[0]["anchor"]))
    rows = walk(days, only=a.only)
    if a.kind:
        rows = [r for r in rows if r["kind"] == a.kind]
    print(render(rows))
    print(f"\n행 {len(rows)} · 날짜 {len(days)} · 종류: " + " · ".join(f"{k} {sum(1 for r in rows if r['kind'] == k)}" for k in sorted({r['kind'] for r in rows})))
    return 0


if __name__ == "__main__":
    sys.exit(main())
