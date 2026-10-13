# -*- coding: utf-8 -*-
# [앞날 걷기 2026-10-13 — 발행자 한 수 하루 전] 발행자가 10/14 에 누를 단추는 「용도 → 종구 생산」 카드의 「밭 정보에 넣기」 다. 그 길을 걸으니 화면이 그 카드를
# 넣기 **전** 에만 바른 자리(밭 정보)로 말하고, 나머지 세 자리는 한 곳(일지)으로 말했다:
#   ① 셈 줄   「아직 안 넣은 것 2 — 대화에서 넣기를 누르시면 영농일지에 들어갑니다」(기다리는 둘이 다 밭 정보 카드) · 영농일지 머리도 같은 말
#   ② 넣은 뒤 「일지에 넣었습니다 · parcel 2026-10-14」(자리가 틀리고 원장 레코드의 안쪽 종류가 보였다) · 넣은 카드는 「일지에 넣었습니다 밭 정보 · 2026-10-04」(일지에서 읽은 날)
#   ③ 카드 몸 「일지에 이미 적힌 말에서 읽었습니다 … 맞으면 넣기, 아니면 그냥 두시면 됩니다」 — 누르면 무엇이 달라지는지는 **답 줄**에만 있었고, 대장 페이지가 보낸 길
#      (「아무 말이나 한 줄」)의 답은 그 줄을 안 실었다. 옛 메시지의 카드(발행자 PC 의 그 카드)는 어디에서도 그 말을 안 했다
# 2026-10-04 · 10-07 에 넣기 전 쪽(단추 CONFIRM_LABELS · 문장 PLACE_SAID)만 고친 §7.5 지점이다. 처방: 자리 이름을 종류마다 하나(chat.place_noun — 일지로 가는 종류는
# DIARY_SHOWS 에서 센다) · 넣은 뒤 줄(saved_parts · saved_line — 종류는 **초안의** 것 · 날은 원장이 적은 날) · 셈 줄(pending_said) · 카드 뒷말(두 문장 — 답이 이미 한 문장은 안 한다).
# 처방 뒤 적대 검토(렌즈 넷 · 검증 스물둘)가 같은 자리를 더 찾았다 — 넣은 카드가 원장 날이 아니라 초안 날 · 옛 꼴 답에서 누르면 문장이 두 번 · 카드 여럿이면 답이 세 배 ·
# 고른 못 한 이유를 못 알아봄(표지 뒤에 사유가 붙는다). 아래가 그것까지 고정한다.
from __future__ import annotations

import ast
import html
import re
from datetime import date, datetime, timezone
from pathlib import Path
from urllib.parse import quote

import pytest

from frontend import chat_pages, config, words
from ingest import chat, events as ev, media, parcels
from tests.test_brand_home import srv  # noqa: F401
from tests.test_publisher_path_http import _get, _post

ROOT = Path(__file__).resolve().parent.parent
SID = "p001-jjokpa-2026f"
DAY = "2026-10-14"
T = date(2026, 10, 14)
NOW = datetime(2026, 10, 14, 9, 0, tzinfo=timezone.utc)
USE_LINE = "이 쪽파는 종구생산을 위한 목적이다"


def _visible(page: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]*>", " ", re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", page, flags=re.S))))


def _confirmable_kinds() -> list[str]:
    """confirm() 가 **실제로 받는** 종류 — 소스의 갈래에서 센다(표를 손으로 적지 않는다)."""
    src = (ROOT / "ingest" / "chat.py").read_text(encoding="utf-8")
    fn = next(n for n in ast.walk(ast.parse(src)) if isinstance(n, ast.FunctionDef) and n.name == "_confirm_locked")
    kinds = []
    for n in ast.walk(fn):
        if isinstance(n, ast.Compare) and isinstance(n.left, ast.Name) and n.left.id == "k":
            kinds += [c.value for c in n.comparators if isinstance(c, ast.Constant) and isinstance(c.value, str)]
    return kinds


def test_every_kind_confirm_accepts_has_one_place_and_the_saved_line_says_that_place():
    kinds = _confirmable_kinds()
    assert len(kinds) >= 9, kinds                                                  # 측정이 살아 있다(한 일 · 본 것 · 할 일 · 납품 · 고쳐 달라는 말 · 못 한 이유 · 농사 끝 · 밭 정보 · 농사 정보)
    for k in kinds:
        place = chat.place_noun(k)
        assert place, f"{k}: 넣으면 어디로 가는지 이름이 없다"
        saved = chat.saved_label(k)
        if k in chat.DIARY_SHOWS:
            assert saved == chat.SAVED_LABEL and place == "영농일지", (k, saved, place)
        else:
            assert "일지" not in saved and "일지" not in place, (k, saved, place)  # 일지로 안 가는 것을 일지라고 하지 않는다(양방향)
    for k, said in chat.PLACE_SAID.items():                                        # 넣기 전 문장과 같은 자리
        assert chat.place_noun(k) in said or (k == "subject.end" and "마친" in said) or (k == "plan.target_date" and "납품" in said), (k, said)
    assert chat.place_noun("subject.end") == chat.KIND_PLAIN["subject.end"]          # 화면에 한 번만 나오는 이름을 새로 짓지 않는다(카드 머리와 같은 이름)


def test_unknown_kind_is_not_given_a_place():
    assert chat.place_noun("없는종류") is None and chat.saved_label("없는종류") == "넣었습니다"
    assert chat.pending_said(["없는종류", "event"]) == "그 밖 1 · 영농일지 1"


def _use_card_state():
    ev.add_observation(SID, USE_LINE, "2026-10-04")                               # 발행자 PC 그대로 — 일지에 선언이 이미 있다(용도 칸은 다른 값)
    m, r = chat.send(SID, "안녕하세요", today=T, now=NOW)
    use = [(i, d) for i, d in enumerate(m["drafts"]) if d["kind"] == "parcel.field" and d.get("field") == "use"]
    assert use, [d["kind"] for d in m["drafts"]]
    return m, r, use[0]


def test_the_guided_path_reply_says_where_each_field_card_goes_and_what_it_opens():
    m, r, (i, d) = _use_card_state()
    for x in (x for x in m["drafts"] if x["kind"] in chat.FIELD_KINDS):            # 「아무 말이나 한 줄」 길에서도 카드마다
        assert chat.field_place_said(x) in r["text"] and chat.field_opens_said(x) in r["text"], (x.get("field"), r["text"][:300])
    assert r["text"].count(chat.field_place_said(d)) == 1                          # 같은 누르면 문장은 한 번(카드가 여럿이어도)
    assert f"밭 정보({parcels.FIELD_WORDS['use']})" in r["text"]                     # 목록이 두 밭 정보를 같은 이름으로 부르지 않는다
    assert re.search(r"\d\) 밭 정보 ·|\d\) 밭 정보 —", r["text"]) is None, r["text"][:300]


def test_two_field_cards_say_the_shared_sentences_once():
    """[검토 2026-10-13 길이] 카드마다 card_line 을 붙이면 같은 두 문장이 두 번 — 답이 218자에서 754자. 같은 말은 한 번 · 값과 「넣으면 …」 은 카드마다."""
    a = {"kind": "parcel.field", "field": "use", "value": "종구 생산", "why_key": "from_diary"}
    b = {"kind": "parcel.field", "field": "drainage", "value": "좋음", "why_key": "from_diary"}
    two = chat._field_cards_said([a, b])
    assert two.count(chat.plain_why(a)) == 1 and two.count(chat.field_place_said(a)) == 1, two
    assert chat.field_opens_said(a) in two and chat.field_opens_said(b) in two and "용도: 종구 생산 · 배수: 좋음" in two, two
    assert len(two) < len(chat.card_line(a)) + len(chat.card_line(b)), (len(two), len(chat.card_line(a)) + len(chat.card_line(b)))
    assert chat._field_cards_said([a]) == " " + chat.card_line(a)                    # 하나면 전과 같은 문장(바꿀 이유가 없는 쪽은 안 바꾼다)


def test_the_count_lines_say_where_the_waiting_cards_go(srv, monkeypatch):
    monkeypatch.setenv(config.TODAY_ENV, DAY)
    _use_card_state()
    kinds = [d["kind"] for _, _, d in chat.pending_drafts(SID)]
    want = chat.pending_said(kinds)
    assert "밭 정보" in want and kinds.count("parcel.field") >= 1
    for path in (f"/c/{quote(SID)}", f"/diary/{quote(SID)}"):
        st, _, page = _get(srv, path)
        v = _visible(page)
        assert st == 200 and f"{chat.PENDING_LABEL} {len(kinds)} — " in v and want in v, (path, v[:400])
        assert "영농일지에 들어갑니다" not in v.split(chat.PENDING_LABEL, 1)[1][:80], path        # 셈 줄이 다 일지라고 하지 않는다


def test_after_pressing_the_field_card_the_banner_and_the_card_say_field_info_not_the_diary(srv, monkeypatch):
    monkeypatch.setenv(config.TODAY_ENV, DAY)
    m, _, (i, d) = _use_card_state()
    st, _, page = _post(srv, f"/c/{quote(SID)}/confirm", {"msg": m["id"], "i": i})
    v = _visible(page)
    head = f"밭 정보에 넣었습니다 · {parcels.FIELD_WORDS['use']} → {d['value']}"
    assert st == 200 and head in v, v[:400]
    assert " parcel " not in f" {v} " and "일지에 넣었습니다 · parcel" not in v      # 원장 레코드의 안쪽 종류가 안 보인다
    after = chat.get_message(m["id"])
    cv = _visible(chat_pages._draft_html(after, i, after["drafts"][i]))
    assert "밭 정보에 넣었습니다" in cv and f"{parcels.FIELD_WORDS['use']} → {d['value']}" in cv, cv
    assert chat.SAVED_LABEL not in cv and (d.get("observed_at") or "@@") not in cv, cv   # 일지라고도 · 일지에서 읽은 날로도 말하지 않는다


@pytest.mark.parametrize("text,kind,saved", [("오늘 물 줬다", "event", "일지에 넣었습니다 · 한 일 · "),
                                             ("농사 끝났어요", "subject.end", "이 농사를 마친 것으로 닫았습니다")])
def test_other_kinds_keep_their_own_saved_line(srv, monkeypatch, text, kind, saved):
    """양방향 — 일지로 가는 종류는 전과 같은 말(종류 · 날짜)이고, 농사 끝은 닫았다고 말한다(안쪽 이름 subject 없이)."""
    monkeypatch.setenv(config.TODAY_ENV, DAY)
    m, _ = chat.send(SID, text, today=T, now=NOW)
    i = next(n for n, d in enumerate(m["drafts"]) if d["kind"] == kind)
    st, _, page = _post(srv, f"/c/{quote(SID)}/confirm", {"msg": m["id"], "i": i, "day": DAY})
    v = _visible(page)
    assert st == 200 and saved in v, (kind, v[:300])
    assert " subject " not in f" {v} " and " event " not in f" {v} ", v[:300]
    if kind == "subject.end":
        after = chat.get_message(m["id"])
        cv = _visible(chat_pages._draft_html(after, i, after["drafts"][i]))
        assert cv.count(chat.KIND_PLAIN[kind]) == 0 and DAY in cv, cv             # 일지 밖 종류는 종류 이름을 또 말하지 않는다 · 닫은 날은 말한다


def test_the_done_card_says_the_day_the_ledger_wrote_not_the_drafts_day(srv, monkeypatch):
    """[검토 2026-10-13 즉시] 날짜 칸을 고쳐 넣으면 배너(원장 날)와 넣은 카드(초안 날)가 다른 날을 말했고, 새로 읽으면 배너는 사라지고 틀린 날만 남았다."""
    monkeypatch.setenv(config.TODAY_ENV, DAY)
    m, _ = chat.send(SID, "어제 물 줬다", today=T, now=NOW)
    i = next(n for n, d in enumerate(m["drafts"]) if d["kind"] == "event")
    assert m["drafts"][i]["observed_at"] == "2026-10-13"
    st, _, page = _post(srv, f"/c/{quote(SID)}/confirm", {"msg": m["id"], "i": i, "day": "2026-10-10"})
    assert st == 200 and "일지에 넣었습니다 · 한 일 · 2026-10-10" in _visible(page)
    stored = [r for r in ev.list_records(SID) if r.get("kind") == "event"][-1]["observed_at"]
    after = chat.get_message(m["id"])
    cv = _visible(chat_pages._draft_html(after, i, after["drafts"][i]))
    assert stored == "2026-10-10" and stored in cv and "2026-10-13" not in cv, cv


def test_an_old_card_carries_what_entering_changes_and_a_new_card_does_not_say_it_twice():
    """옛 메시지(답에 그 줄이 없다)의 카드는 몸에 싣고 · 답이 이미 한 문장은 카드가 다시 하지 않는다 — **문장마다** 본다."""
    m, r, (i, d) = _use_card_state()
    place, opens = chat.field_place_said(d), chat.field_opens_said(d)
    old = _visible(chat_pages._draft_html(m, i, d, ""))
    assert place in old and opens in old, old                                     # 옛 답(그 줄 없음) — 카드가 말한다
    assert re.search(r"[^.] '" + re.escape(chat.confirm_label("parcel.field")), old) is None, old   # 앞말과 마침표로 갈린다(한 문장으로 붙지 않는다)
    new = _visible(chat_pages._draft_html(m, i, d, r["text"]))
    assert place not in new and opens not in new, new                             # 이번 답이 이미 말했다 — 카드는 안 한다
    # 옛 꼴 답(10-04~06): 누르면 문장은 같고 읽는 판단 문장은 넣은 뒤 꼴 — 누르면 문장은 다시 안 하고, 읽는 판단 문장만 지금 꼴로 싣는다
    old_form = f"{chat.plain_why(d)} — 용도: {d['value']}. {place} " + words.opened(d["field"], d["value"])
    mixed = _visible(chat_pages._draft_html(m, i, d, old_form))
    assert place not in mixed and opens in mixed, mixed
    page = _visible(chat_pages.thread_main(next(s for s in media.load_subjects() if s["id"] == SID), T))
    assert page.count(place) == 1, page.count(place)                               # 화면 전체에서 한 번(답에서) — 카드가 또 하지 않는다


def test_choosing_a_kind_that_does_not_go_to_the_diary_says_its_own_button_and_place():
    m, _ = chat.send(SID, "오늘 물 줬다", today=T, now=NOW)
    chat.choose_kind(m["id"], "feedback.request", today=T)
    said = chat_pages.chosen_reply(chat.get_message(m["id"]))
    assert said and chat.confirm_label("feedback.request") in said and chat.PLACE_SAID["feedback.request"] in said, said
    assert "영농일지" not in said and chat.CONFIRM_LABEL not in said, said


def test_a_chosen_noncompliance_is_still_recognised_as_chosen():
    """[검토 2026-10-13] 고른 못 한 이유는 계획표 잇기가 표지 뒤에 사유를 덧붙여 같다(==)로 보던 자리가 못 알아봤다 — 고른 뒤 확인 줄이 안 섰다."""
    m, _ = chat.send(SID, "오늘 물 줬다", today=T, now=NOW)
    chat.choose_kind(m["id"], "decision.noncompliance", today=T)
    d = chat.get_message(m["id"])["drafts"][0]
    assert d["why"].startswith(chat.CHOSEN_WHY) and chat.is_chosen(d), d["why"]
    said = chat_pages.chosen_reply(chat.get_message(m["id"]))
    assert said and chat.PLACE_SAID["decision.noncompliance"] in said, said
    assert not chat.is_chosen({"why": "규칙이 종류를 못 정했다"}) and not chat.is_chosen({})       # 양방향 — 표지 없는 초안은 아니다


def test_the_place_lines_are_wired_to_the_one_canon():
    """배선 — 화면 자리가 정본을 **부른다**(호출형만 본다 · 인자 모양은 박지 않는다 · 함수 본문을 구조로 자른다)."""
    cp = (ROOT / "frontend" / "chat_pages.py").read_text(encoding="utf-8")
    sv = (ROOT / "frontend" / "serve.py").read_text(encoding="utf-8")

    def body(src: str, name: str) -> str:
        fn = next(n for n in ast.walk(ast.parse(src)) if isinstance(n, ast.FunctionDef) and n.name == name)
        return ast.get_source_segment(src, fn)
    assert "chat.pending_said(" in body(cp, "thread_panel") and "chat.pending_said(" in body(cp, "diary_main")
    assert "chat.saved_parts(" in body(cp, "_draft_html") and "chat.field_place_said(" in body(cp, "_draft_html") and "chat.field_opens_said(" in body(cp, "_draft_html")
    assert "chat.is_chosen(" in body(cp, "chosen_reply") and "영농일지에 들어갑니다" not in body(cp, "chosen_reply")
    conf = sv[sv.index('p.endswith("/confirm")'):]
    conf = conf[:conf.index("elif p.startswith", 10)]
    assert "chat.saved_line(" in conf and "rec['kind']" not in conf and 'rec["kind"]' not in conf
    cs = (ROOT / "ingest" / "chat.py").read_text(encoding="utf-8")
    assert "confirmed_day=" in body(cs, "_confirm_locked")                         # 넣은 날을 찍는 자리(넣은 카드가 원장 날을 말하는 근거)
