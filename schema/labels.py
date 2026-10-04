# -*- coding: utf-8 -*-
# FILE: schema/labels.py
# ROLE: [발행자 §2 둘째 측정 2026-10-04 "밭 정보 메뉴를 찾지 못함"] **화면 이름의 계약 하나.** 메뉴 · 구역 · 단추의 이름은 여기서만 나오고, 요구 문장의 「어디서」(judge.need)와
#   보고(대장 페이지 BEST)는 이 목록에서만 고른다 — 그래서 **화면에 없는 이름이 농가 문장으로 나갈 수 없다**(검사가 거기 걸린다).
#
#   실측 2026-10-04: 보고와 요구 문장은 「밭 정보 화면(/me 의 밭 칸)」 · 「왼쪽 메뉴 설정(/me) → 밭 정보」 라고 썼는데, 화면은 — 왼쪽 메뉴에 /me 링크가 없었고(사용자 탭을 눌러야
#   「설정」 이 나왔다) /me 의 구역 이름은 「필지」 였다. 같은 것에 이름이 셋(밭 정보 · 설정 · 필지). 발행자: *"화면 메뉴 이름을 보고에 그대로 쓰거나, 보고에 쓴 이름대로 메뉴를
#   바꾸거나 — 같은 화면에 이름이 하나여야 한다."* 농가 말(밭 정보)로 맞췄다 — 「필지」 는 지적(地籍) 말이다.
from __future__ import annotations

import re

NEW_CHAT = "＋ 새 채팅 (작목 추가 · 계획)"
# 왼쪽 메뉴 「화면」 묶음 — 순서가 화면 순서. /me 가 여기 **있다**(전엔 사용자 탭 안에만 있어 찾지 못했다)
SIDEBAR: tuple[tuple[str, str], ...] = (
    ("/improve", "고쳐 달라는 말 · 스스로 개선"),
    ("/judge", "판단 전체"),
    ("/selfcheck", "자기 점검 — 화면이 스스로 확인"),
    ("/me/decisions", "결정 — 한 화면에서 답하기"),
    ("/me", "밭 정보 · 설정"),
    ("/media", "영상 반입"),
    ("/events", "한 일 · 못 한 이유(표)"),
)
MALL = "몰 상세페이지 목업 (M-11)"
# /me 화면의 구역 머리 — 「밭 정보」 가 구역 이름이다(요구 문장 · 보고 · 폼 단추가 같은 말)
ME_SECTIONS = {"outlook": "장기 전망", "decisions": "결정", "parcel": "밭 정보", "sync": "설정 · 동기화"}
ME_TITLE = "사용자 정보"
PARCEL_SAVE = "밭 정보 저장"
# 사용자 탭 메뉴(계정 메뉴 형식) — /me 항목은 왼쪽 메뉴와 같은 이름
USER_MENU_ME = ("/me", "밭 정보 · 설정", "밭 정보 · 사용자 · 동기화")


def label(href: str) -> str:
    for h, lab in SIDEBAR:
        if h == href:
            return lab
    raise KeyError(href)


# 요구 문장의 「어디서」 — 농가가 가는 곳. 메뉴 이름은 위 목록에서만(「…」 로 감싼 것은 전부 화면에 있는 이름이어야 한다 · 검사가 본다)
PLACES: dict[str, str] = {
    "chat": "채팅에 한 줄",
    "field": "밭에서 보고 채팅에 한 줄",
    "parcel": f"왼쪽 메뉴 「{label('/me')}」 → 「{ME_SECTIONS['parcel']}」",
    "subject": f"채팅에 한 줄(「인증은 유기다」 처럼) · 또는 왼쪽 메뉴 「{NEW_CHAT}」 의 인증 칸",
    "judge": f"왼쪽 메뉴 「{label('/judge')}」",
    "publisher": "발행자 PC",
}
_QUOTED = re.compile(r"「([^」]+)」")
# 「…」 안에 와도 되는 것 가운데 메뉴 이름이 아닌 것 — 농가가 칠 말의 예시(채팅 한 줄 · 값 이름)만. 화면 이름은 전부 목록에서.
EXAMPLE_QUOTES: frozenset[str] = frozenset({"인증은 유기다", "종구 생산"})


# 물러난 이름 — 10-04 전 보고·요구 문장이 쓰던 말. 화면에 없으니 농가에게 가는 글(요구 문장 · 대장 페이지 두 목록 · 보고)에 다시 들어오면 검사가 붉다.
RETIRED: tuple[str, ...] = ("밭 정보 화면", "밭 칸", "설정(/me)", "재배 목록", "작목 칸", "판단 화면(/judge)", "필지 저장", "「설정」", "「필지」")


def retired_in(text: str) -> list[str]:
    return [r for r in RETIRED if r in (text or "")]


def menu_labels() -> frozenset[str]:
    out = {NEW_CHAT, MALL, ME_TITLE, PARCEL_SAVE, USER_MENU_ME[1]} | {lab for _, lab in SIDEBAR} | set(ME_SECTIONS.values())
    return frozenset(out)


def quoted(text: str) -> list[str]:
    return _QUOTED.findall(text or "")


def unknown_quoted(text: str) -> list[str]:
    """글 안의 「…」 가운데 화면 이름도 예시도 아닌 것 — 있으면 그 이름은 화면에 없다(발행자 §2 둘째 측정의 형태)."""
    ok = menu_labels() | EXAMPLE_QUOTES
    return [q for q in quoted(text) if q not in ok]
