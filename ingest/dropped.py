# -*- coding: utf-8 -*-
# FILE: ingest/dropped.py
# ROLE: [R-6 후속 전수 2026-09-21] **조용히 버린 것**의 정본 하나. 시스템이 제 손으로 쓴 파일을 읽다 실패하면,
#       그 사실이 어디에도 안 남아서는 안 된다.
#
# 왜 생겼나 — R-6 에서 서버가 에러 한 줄 없이 사라졌고, 발행자가 브라우저를 열어야만 알았다. 같은 형태를 전수로 세니
# except 핸들러 83개 중 24개가 조용했고, 그중 셋이 **판독을 오염시키는 급**이었다.
#
#   soil_store.latest / prescriptions_for   처방 정본이 있는데 스키마가 안 맞으면 None → 판정은 "정본 **미도착**"
#                                           이라고 말한다. 원인이 뒤바뀐다 — 농가는 없는 것을 다시 받으러 간다.
#   subjects.grid_unit_for                  격자 파일 하나가 깨지면 그 작목은 **격자가 없는 것처럼** 되고
#                                           판정이 통째로 '해당 없음' 이 된다.
#
# 나머지 스물 하나는 **다른 급**이다(§7.5 같은 형태 ≠ 같은 급): kma·ncpms·media 의 파싱 실패는 외부 응답에 값이
# 없다는 뜻이고, None 은 그것을 정직하게 말하는 것이다. 그것까지 여기 실으면 신호가 묻힌다.
#
# 이 기록은 **프로세스 안에만** 있다(원장이 아니다 — 원장은 사실의 자리이고 이것은 운영 상태다). 읽을 때마다 다시
# 쌓이므로 기동 시 비어 있는 것이 정상이다. 소비자는 /changes 화면 하나 — 만들면서 그 자리를 함께 만들었다.
from __future__ import annotations

import sys
import threading
from typing import Any

_lock = threading.RLock()
_drops: list[dict[str, Any]] = []
MAX = 200                     # 같은 실패가 매 요청마다 쌓이지 않게 — 넘으면 오래된 것부터 버린다(그 사실도 화면이 말한다)


def note(where: str, path: str, why: str, quiet: bool = False) -> dict[str, Any]:
    """읽다 버린 것 한 건. 같은 (where, path) 는 한 줄로 합치고 횟수만 센다."""
    rec = {"where": where, "path": str(path), "why": why, "count": 1}
    with _lock:
        for d in _drops:
            if d["where"] == where and d["path"] == rec["path"]:
                d["count"] += 1
                d["why"] = why
                return d
        _drops.append(rec)
        if len(_drops) > MAX:
            del _drops[0]
    if not quiet:
        # 콘솔에도 한 번은 찍는다 — 화면을 안 보는 사람에게도 닿아야 한다(침묵이 가장 나쁜 실패다)
        print(f"[agrodss] 읽다 버렸다 — {where}: {path} ({why})", file=sys.stderr)
    return rec


def all_drops() -> list[dict[str, Any]]:
    with _lock:
        return [dict(d) for d in _drops]


def clear() -> None:
    with _lock:
        _drops.clear()
