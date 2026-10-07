# -*- coding: utf-8 -*-
# [내부 값 전수 2026-10-07] 앞 칸에서 사람 말 가드를 **기록이 있는 상태**로 깨웠다. 같은 상태로 **영문 내부 값** 쪽을 재니 셋이 더 있었다(§7.5 지점).
#
#     /diary      줄마다 출처가 「farmer」                       역할 사람 말(`words.role`)이 있는데 이 자리에 안 닿았다
#     /events     표의 종류 칸이 「decision.noncompliance」      작업 이름이 **없는** 기록(불이행 사유 · 납품 날짜)은 전부 그랬다
#     /diary      「납품 날짜 납품 날짜 2026-10-30」              앞 회차에 내가 넣은 중복(줄머리가 이미 그 이름이다)
#
# 2026-10-04 처방(`words.role` · `words.target` · `words.subject_label`)은 옳았고 **닿은 화면이 둘**이었다. 그 가드도 그 둘만 보고 있었다 —
# 처방이 간 곳만 검사하면 전수는 영원히 그 둘이다. 이제 농가 화면 전부를 걷고(그 검사), 여기서는 **꼴**로도 본다.
#
# 고정하는 것 여섯:
#   ① 농가 화면의 **글**에 점 찍힌 내부 이름(`observation.note` 꼴)이 없다 — 어휘 목록을 몰라도 잡는 꼴 검사(인용 <code> 는 걷는다)
#   ② 일지 줄의 출처는 사람 말이고 **정확한 값은 title** 에 남는다(양방향)
#   ③ 「한 일」 표의 종류 칸도 사람 말 · 정확한 `kind` 는 title
#   ④ 역할 사람 말은 정본 하나에서 오고 모르는 값은 **지어내지 않는다**
#   ⑤ 줄머리와 본문이 **같은 말을 두 번** 하지 않는다(전수 — 내가 만든 중복이 그 자리에서 나왔다)
#   ⑥ 검사의 검사 — 이 상태에 다섯 종류의 기록이 실제로 있다(비면 ①~⑤ 가 눈을 감는다)
from __future__ import annotations

import re
from datetime import date, datetime, timezone
from urllib.parse import quote

from frontend import chat_pages, words
from ingest import chat, events as ev, media, profile
from tests.test_no_internal_values_on_screens import _fill, _said
from tests.test_screen_speaks_plainly import FARMER_PAGES, _get, _visible, srv  # noqa: F401

SID = "p001-jjokpa-2026f"
T = date(2026, 10, 4)
#   kind 꼴(observation.note · decision.noncompliance)을 찾는다. **파일 이름은 일부러 통과시킨다** — 「고칠 파일 jjokpa_autumn.json」 은
#   발행자 몫 문장이 짚어야 하는 것이고 그 결정이 이미 기록돼 있다(`judge.need.DEV_TOKENS` 의 주석 · `test_grid_unit_miss` 가 그 계약을 지킨다).
#   [라이브가 가르쳐 준 것 2026-10-07] 이 예외 없이 보고 확인을 돌리니 그 문장이 「틀림」 으로 떴다 — 막을 것과 **일부러 둔 것**을 가르는 자리다.
DOTTED = re.compile(r"(?<![\w/.])[a-z][a-z_]{2,}\.(?!json|jsonl|bat|py|md|csv|env|html|js|cjs|txt|yml|toml)[a-z][a-z_]{2,}(?![\w/])")


def test_no_farmer_page_shows_a_dotted_inner_name(srv):
    """[①] 어휘 목록을 몰라도 잡는다 — 점 찍힌 내부 이름은 사람이 읽을 말이 아니다."""
    _fill()
    bad = {}
    for tmpl in list(FARMER_PAGES) + ["/changes"]:
        p = tmpl.format(sid=quote(SID))
        st, body = _get(srv, p)
        assert st == 200, p
        hits = sorted(set(DOTTED.findall(_said(body))))
        if hits:
            bad[p] = hits
    assert bad == {}, f"화면의 글에 내부 이름이 그대로 — {bad}"


def test_the_diary_source_is_a_people_word_and_keeps_the_exact_value(srv):
    """[②] 출처는 「농가」 로 보이고 「farmer」 는 **글에 없다** — 정확한 값은 title 에(막는 쪽만 보면 값을 버린 것을 못 본다)."""
    _fill()
    st, body = _get(srv, f"/diary/{quote(SID)}")
    assert st == 200
    seen = _said(body)
    assert words.role("farmer") in seen, seen[:200]
    assert not re.search(r"(?<![A-Za-z_])farmer(?![A-Za-z_])", seen), "출처가 날것으로 나온다"
    assert 'title="farmer"' in body, "정확한 값을 버렸다 — title 에 남긴다"


def test_the_events_table_says_the_kind_in_people_words(srv):
    """[③] 작업 이름이 없는 기록(불이행 사유 · 납품 날짜)의 종류 칸 — 전에는 `kind` 가 날것으로 나왔다."""
    _fill()
    st, body = _get(srv, "/events")
    assert st == 200
    seen = _said(body)
    for kind in ("decision.noncompliance", "plan.target_date"):
        assert chat.KIND_PLAIN[kind] in seen, (kind, "사람 말이 표에 없다")
        assert f'title="{kind}"' in body, (kind, "정확한 종류를 버렸다")
        assert not re.search(rf"(?<![\w.]){re.escape(kind)}(?![\w.])", seen), (kind, "날것이 표에 있다")


def test_the_role_words_come_from_one_canon_and_nothing_is_invented():
    """[④] 사람 말은 정본 하나 · 모르는 값은 그대로 둔다(지어내지 않는다 — 없는 역할을 만들지 않는다)."""
    assert set(words.ROLE_SAID) == set(profile.ROLES)
    for r in profile.ROLES:
        assert words.role(r) != r and words.role(r), r
    assert words.role("없는역할") == "없는역할" and words.role(None) == "" and words.role("") == ""


def test_no_diary_row_says_the_same_word_twice(srv):
    """[⑤] 줄머리와 본문이 같은 말을 두 번 하지 않는다 — 앞 회차에 내가 만든 중복(「납품 날짜 납품 날짜」)이 이 자리에서 나왔다."""
    _fill()
    rows = chat.diary(SID)
    assert rows, "기록이 있어야 이 판정이 성립한다"
    for r in rows:
        assert not r["text"].startswith(r["label"]), (r["label"], r["text"], "본문이 줄머리를 되풀이한다")
    seen = _visible(chat_pages.diary_main(next(s for s in media.load_subjects() if s["id"] == SID), T))
    for r in rows:
        assert f'{r["label"]} {r["label"]}' not in seen, (r["label"], "화면에 같은 말이 두 번")


def test_this_state_really_has_rows(srv):
    """[⑥] 검사의 검사 — 다섯 종류가 실제로 있다(비면 위 다섯이 아무것도 보지 않는다)."""
    _fill()
    kinds = {r["kind"] for r in chat.diary(SID)}
    assert {"event", "decision.noncompliance", "plan.target_date"} <= kinds, sorted(kinds)
    assert any(k in kinds for k in (media.KIND_IMAGE, "observation.video")), sorted(kinds)
    st, body = _get(srv, "/events")
    assert "아직 없다" not in _said(body), "한 일 화면이 비어 있다 — 표 칸을 보지 못한다"
