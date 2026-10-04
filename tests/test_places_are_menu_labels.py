# -*- coding: utf-8 -*-
# [발행자 §2 둘째 측정 2026-10-04] *"「밭 정보 메뉴를 찾지 못함」 — 이 다섯 글자 그대로입니다. 첫 번째(「무엇을 요구하는지 모르겠다」)보다 구체적입니다. '어디서' 에 적힌 이름이
# 화면에 없다. 처방은 둘 중 하나 — 화면 메뉴 이름을 보고에 그대로 쓰거나, 보고에 쓴 이름대로 메뉴를 바꾸거나. 같은 화면에 이름이 하나여야 한다. 요구 문장 정본이 '어디서' 를 만들 때
# 화면 메뉴 레이블 목록에서만 고르게 하면 없는 이름이 나갈 수 없다. 검사도 거기 걸린다."*
#
#   실측: 보고 「왼쪽 메뉴 설정(/me) → 밭 정보」 · 요구 문장 「밭 정보 화면(/me 의 밭 칸)」 ↔ 화면: 왼쪽 메뉴에 /me 없음(사용자 탭 안 「설정」) · /me 구역 이름 「필지」. 이름 셋.
#   처방: 화면 이름 계약 하나(schema.labels) — 메뉴 · 구역 · 단추가 거기서 그려지고, 요구 문장(judge.need.PLACES)과 보고(BEST.where)는 거기서만 고른다 · 「…」 로 감싼 이름이 화면에
#   없으면 검사가 붉다 · /me 가 왼쁜 메뉴에 「밭 정보 · 설정」 으로 있고 구역은 「밭 정보」.
from __future__ import annotations

import html as _html
import re
from datetime import date
from pathlib import Path

from frontend import chat_pages
from ingest import media
from judge import need as N
from schema import labels
from scripts import build_ledger_page as blp
from tests.test_screen_speaks_plainly import _get, _visible, srv  # noqa: F401

ROOT = Path(__file__).resolve().parent.parent
T = date(2026, 10, 4)


def test_every_place_in_a_requirement_sentence_names_only_labels_that_are_on_the_screen():
    assert N.PLACES == labels.PLACES                                                        # 요구 문장의 어디서 = 화면 이름 계약(사본 아님)
    side = _html.unescape(chat_pages.sidebar("", [], T))
    me = _html.unescape(chat_pages.me_main())
    screen = side + me
    for key, place in labels.PLACES.items():
        assert labels.unknown_quoted(place) == [], (key, place)                             # 「…」 는 전부 화면 이름(또는 농가가 칠 말의 예시)
        for q in labels.quoted(place):
            if q in labels.menu_labels():
                assert q in screen, (key, q)                                                # 그 이름이 실제로 그려진다
    assert "「밭 정보 · 설정」 → 「밭 정보」" in labels.PLACES["parcel"]
    assert labels.unknown_quoted("왼쪽 메뉴 「밭 정보 화면」") == ["밭 정보 화면"] and labels.unknown_quoted("「설정」 → 「필지」") == ["설정", "필지"]   # 옛 이름 셋은 이제 없는 이름이다


def test_the_me_screen_is_reachable_from_the_left_menu_and_calls_the_section_what_the_sentence_calls_it(srv):
    st, body = _get(srv, f"/c/{media.load_subjects()[0]['id']}")
    assert st == 200 and f'href="/me">{labels.label("/me")}</a>' in _html.unescape(body)   # 왼쪽 메뉴 「화면」 묶음에 /me 가 있다 — 사용자 탭 안에만 있던 것
    st, body = _get(srv, "/me")
    seen = _visible(body)
    assert st == 200 and "밭 정보" in seen and "밭 정보 저장" in seen and "필지</h2>" not in body
    assert labels.USER_MENU_ME[1] == labels.label("/me")                                   # 사용자 탭의 /me 항목도 같은 이름


def test_screen_names_live_in_one_file_only():
    """같은 화면에 이름이 하나 — 메뉴·구역 이름의 글자가 다른 파일에 박혀 있으면 두 벌이 된다(한쪽만 바뀌면 또 못 찾는다)."""
    files = [p for d in ("frontend", "ingest", "judge", "scripts") for p in (ROOT / d).glob("*.py")] + [ROOT / "scripts" / "build_ledger_page.py"]
    for lit in ("밭 정보 · 설정", "판단 전체", "고쳐 달라는 말 · 스스로 개선", "자기 점검 — 화면이 스스로 확인", "밭 정보 저장"):
        where = sorted({p.relative_to(ROOT).as_posix() for p in files if lit in re.sub(r"#.*", "", p.read_text(encoding="utf-8"))} - {"scripts/build_ledger_page.py"})
        assert where == [], (lit, where)                                                  # 코드에는 schema/labels.py 밖에 없다(보고 글은 예외 — 그쪽은 check_best 가 본다)
    assert "밭 정보 · 설정" in (ROOT / "schema" / "labels.py").read_text(encoding="utf-8")


def test_retired_screen_names_cannot_come_back_into_the_publisher_lists_or_requirement_sentences():
    """물러난 이름(밭 정보 화면 · 밭 칸 · 설정(/me) · 필지 저장 …)은 화면에 없다 — 두 목록 · 요구 문장에 다시 들어오면 붉다(거부·통과)."""
    assert blp.check_retired(blp.NEXT_PUBLISHER + blp.NEXT_SESSION) == []
    assert blp.check_retired([("⓪ 밭 정보 화면(/me 의 밭 칸)에서", "…")]) and blp.check_retired([("x", "사용자 탭 「설정」 → 「필지」")])
    assert blp.check_retired([("x", "왼쪽 메뉴 「밭 정보 · 설정」 → 「밭 정보」")]) == []
    for place in labels.PLACES.values():
        assert labels.retired_in(place) == [], place
    src = (ROOT / "scripts" / "build_ledger_page.py").read_text(encoding="utf-8")
    assert "assert not check_retired(NEXT_PUBLISHER + NEXT_SESSION)" in src                 # 배선 — 적재 때 멈춘다


def test_the_report_cannot_name_a_menu_that_is_not_on_the_screen():
    import copy
    ok = copy.deepcopy(blp.BEST)
    assert blp.check_best(ok) == [] and "「밭 정보 · 설정」" in ok["do"]["where"]
    b = copy.deepcopy(ok); b["do"]["where"] = "왼쪽 메뉴 「설정」 → 「밭 정보」"                  # 10-04 전의 보고가 쓴 이름 — 화면에 없다
    bad = blp.check_best(b)
    assert any("「설정」" in x and "화면에 없는 이름" in x for x in bad), bad
    b = copy.deepcopy(ok); b["do"]["where"] = "밭 정보 화면(/me 의 밭 칸)"                      # 「」 없이 쓰면 래칫이 못 본다 — 그래서 어디서는 「」 로 쓴다(검사 가능한 형태)
    assert blp.check_best(b) == []
