# -*- coding: utf-8 -*-
# FILE: judge/need.py
# ROLE: [WO-ASK-01 §2 · 결정 ① 2026-10-03] **요구 문장의 정본 한 자리.** 판단 불가(데이터)가 "무엇이 없다" 고 말할 때 농가에게
#   가는 문장(`missing[].who_can_fill`)은 여기서만 만든다. 발행자 지시서 §0: *"답은 사람 말로 바뀌었으나 요구는 아직 안 바뀌었다"* —
#   코드로 재니(2026-10-02) 요구 문장 17곳 중 3곳이 명령줄·환경변수(`python -m …` · `.env …_KEY`)를 농가에게 말했고, 나머지는
#   "농가 — 파종일" 처럼 **어디서 · 왜 지금**이 없었다. 17곳이 제각각 문장을 지었기 때문이다(§7.5 지점 축).
#
#   한 문장은 넷으로 선다 —  누가 · 무엇을 · 어디서 · 왜 지금.
#     who      농가 / 발행자 — 그 값을 **고칠 수 있는 사람**(§10)
#     what     그 값(농가 말로 · 예시 한 토막)
#     where    PLACES 의 한 자리 — 채팅 · 밭 정보 화면 · 밭에서 보고 채팅에 · 발행자 PC … (§13-7 "어디서가 있다")
#     why_now  그 값이 오면 **어느 판단이 열리는지** — 조건 없는 요구는 헛걸음을 시킨다(G1 반대형)
#   개발자에게 필요한 정확한 명령·파일은 `detail` 에 따로 — 화면은 title 로 내리고 농가 문장에는 싣지 않는다(words.plain 과 같은 가름).
#
#   관문은 **값이 만들어지는 자리**에 있다(§7.5 관문의 입력): 농가 문장에 명령줄·환경변수가 들어오면 여기서 ValueError —
#   어느 판정기가 새로 생겨도 같은 관문을 지난다. 그리고 §5-1 — **읽는 판정이 없는 필지 값은 요구하지 않는다**(소비자 0 을
#   농가에게 묻는 것은 헛걸음). `ingest.parcels.FIELDS_STORED_ONLY` 의 이름이 문장에 들어오면 같은 자리에서 막는다.
from __future__ import annotations

import re
from typing import Any

# 농가가 **가는 곳** — 문장에 이 가운데 하나가 있어야 한다. 화면 경로는 농가도 보는 주소라 그대로 둔다(/me · /judge).
PLACES: dict[str, str] = {
    "chat": "채팅에 한 줄",
    "field": "밭에서 보고 채팅에 한 줄",
    "parcel": "밭 정보 화면(/me 의 밭 칸)",
    "subject": "작목 칸(/me 의 재배 목록)",
    "judge": "판단 화면(/judge)",
    "publisher": "발행자 PC",
}
WHO = ("농가", "발행자", "농가 또는 발행자")
# 농가 문장에 들어오면 안 되는 것 — 명령줄 · 환경변수 · 키 이름 · 파일 경로 토큰. 정확한 명령은 detail 로.
DEV_TOKENS = ("python", "-m ", ".env", "_KEY", "API", "<주소>", "--")     # 파일 이름은 막지 않는다 — 발행자 몫 문장은 고칠 파일을 짚어야 한다(test_grid_unit_miss)


class NeedError(ValueError):
    pass


def _stored_only_words() -> dict[str, str]:
    from ingest import parcels          # 함수 안에서 — 3층이 1층 등록부를 모듈 수준에서 들지 않는다(층 뒤집힘 금지)
    return {f: parcels.FIELD_WORDS[f] for f in parcels.FIELDS_STORED_ONLY}


def need(axis: str, who: str, what: str, where: str, why_now: str, detail: str | None = None, ask: bool = True) -> dict[str, Any]:
    """`missing` 항목 하나 — {axis, who_can_fill, where, why_now[, detail][, ask]}. 틀린 문장은 만들지 않는다(ValueError).
    [2026-10-04 거꾸로 세는 검사 전수] `ask=False` 는 **보이면 적는 것**(증상) — 카드에는 요구로 남되 질문 생성이 답 끝에 묻지 않는다(§3 "판정이 못 실은 값" 이 아니다 —
    아무 일도 없는 밭에 「밭에서 본 것 한 줄」 이 세 번 나가던 것)."""
    if who not in WHO:
        raise NeedError(f"누가 고칠 수 있는지는 {' / '.join(WHO)} 중 하나 — {who!r}")
    if where not in PLACES:
        raise NeedError(f"어디서는 PLACES 의 한 자리 — {where!r} (있는 자리: {', '.join(PLACES)})")
    if not what.strip() or not why_now.strip():
        raise NeedError("무엇을 · 왜 지금 은 비울 수 없다")
    farmer_text = f"{who} — {what} · 어디서: {PLACES[where]} · 왜 지금: {why_now}"
    hit = [t for t in DEV_TOKENS if t in farmer_text]
    if hit:
        raise NeedError(f"농가 문장에 개발자 토큰 {hit} — 정확한 명령은 detail 로 보낸다: {farmer_text!r}")
    for field, word in _stored_only_words().items():
        if word in farmer_text:
            raise NeedError(f"읽는 판정이 없는 필지 값 '{word}'({field}) 을 농가에게 요구한다 — 배선이 서기 전엔 묻지 않는다(§5-1)")
    out: dict[str, Any] = {"axis": axis, "who_can_fill": farmer_text, "where": PLACES[where], "why_now": why_now}
    if detail:
        out["detail"] = detail
    if not ask:
        out["ask"] = False
    return out


_SETUP = re.compile(r"\s*\[설정: [^\]]*\]")


def plain_reason(reason: str | None) -> str | None:
    """원천을 못 받은 이유에서 **설정 꼬리**(`[설정: .env …]`)를 뗀 농가용 줄. 원문(`why`)은 그대로 둔다 — 정확함은 안 버린다.
    원천 수집(judge.run)이 열쇠 이름을 그 꼬리에만 적는다 — 그래서 농가 요약에 환경변수가 안 간다(관문의 입력)."""
    return None if reason is None else _SETUP.sub("", reason)


def need_anchor(why_now: str) -> dict[str, Any]:
    """심은 날 — 아홉 판정이 같은 값을 요구한다. 문장은 하나, 열리는 판단만 다르다."""
    return need("anchor", "농가", "심은 날(파종일 — '8월 25일에 심었다' 처럼)", "chat", why_now)
