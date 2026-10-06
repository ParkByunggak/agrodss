# -*- coding: utf-8 -*-
# [WO-ASK-01 §12 · §14 의 5 · 2026-10-03] 답한 것이 무엇을 바꿨는지 — *"요청이 많으면 안 쓰지만, 답했는데 아무것도 안 바뀌면 더 안 쓴다. 답을 받은 직후 그 답이
# 연 판정을 말한다 — '이제 과습 판정이 섭니다'. 연 것이 없으면 그 질문은 애초에 하지 말았어야 한다(§5-1 소비자 0)."*
#
#   읽는 판정이 있는 필드마다 **누가 읽는가**(parcels.FIELD_CONSUMERS) — 키는 FIELDS_READ_BY_JUDGMENT 와 같고 비지 않는다(§5-1 과 한 쌍) · 이름은 실제 결정 ·
#   그 결정의 코드가 정말 그 필드를 읽는다 · 답을 넣는 두 자리(채팅 초안 줄 · 확인 직후 줄)가 사람 말로 연 판단을 말한다.
#   라이브 실측 2026-10-03(발행자 일지 문장 "고랑 물 빠짐이 잘 되고 있고, 잎 끝 황화 현상은 더 진행이 되지 않음") — 관찰로는 읽혔으나 배수 값(좋음 · 보통 · 나쁨)으로
#   묶이지 않았다: 어휘 밖의 답은 아무것도 열지 않는다 — §7 기준 문면(발행자 몫)이 그 자리다.
from __future__ import annotations

from datetime import date, datetime, timezone
from pathlib import Path

from frontend import serve, words
from ingest import asks, chat, parcels
from judge import registry
from tests.test_parcel_form import _post, srv  # noqa: F401 — 같은 폼 걷기
from tests.test_screen_speaks_plainly import JARGON

ROOT = Path(__file__).resolve().parent.parent
SID = "p001-jjokpa-2026f"
T34 = date(2026, 9, 28)
NOW = datetime(2026, 9, 28, 9, 0, tzinfo=timezone.utc)
CORE = {"harvest_timing", "risk_alert", "material_citation", "plan_vs_actual"}


def test_every_field_a_judgment_reads_names_its_readers_and_they_are_real_decisions_that_read_it():
    assert tuple(parcels.FIELD_CONSUMERS) == parcels.FIELDS_READ_BY_JUDGMENT
    known = CORE | set(registry.all_decisions())
    # (필드, 결정) → 그 결정의 코드가 **그 필드를 읽는 자리**의 표지. 용도는 이름이 아니라 기구로 읽는다(격자 use_gap/use_key) — 2026-10-05 측정에서 셋으로 늘었다
    readers = {("use", "ship_or_store"): ("judge/stage_decisions.py", '"use"'),
               ("use", "harvest_timing"): ("judge/harvest_timing.py", "use_gap("),
               ("use", "risk_alert"): ("judge/risk_alert.py", "use_gap("),
               ("use", "plan_vs_actual"): ("judge/plan_vs_actual.py", "use_gap("),
               ("use", "drainage_alert"): ("judge/stage_decisions.py", '_delegate_risk(subject, "drainage_alert"'),
               ("environment", "base_fertilization"): ("ingest/fertilizer.py", '"environment"'),
               ("drainage", "risk_alert"): ("judge/risk_alert.py", '"drainage"'),
               ("drainage", "drainage_alert"): ("judge/stage_decisions.py", '_delegate_risk(subject, "drainage_alert"')}
    for field, ids in parcels.FIELD_CONSUMERS.items():
        assert ids, field
        for d in ids:
            assert d in known, (field, d)
            rel, token = readers[(field, d)]
            assert token in (ROOT / rel).read_text(encoding="utf-8"), (d, rel, token)      # 선언이 사실이다 — 그 코드가 그 필드 이름을 읽는다
            assert words.decision(d) != d, d                                               # 사람 말 이름이 있다
    for f in parcels.FIELDS_STORED_ONLY:
        assert f not in parcels.FIELD_CONSUMERS                                             # 소비자 0 인 필드는 연 것이 없다 — 묻지도 않고(§5-1) 열었다고도 안 한다


def test_the_reply_to_an_answer_says_which_judgment_it_opens_and_so_does_the_confirm():
    _, r = chat.send(SID, "풀 뽑았다", today=T34, now=NOW)
    assert asks.pending(SID)["fields"] == ["drainage"]
    m, r2 = chat.send(SID, "나쁨", today=T34, now=NOW)
    # 문면은 **정본에서 만든다** — 이름 목록을 검사에 박으면 소비자를 재측정할 때마다 거짓 실패가 난다(2026-10-05 배수 1→2 에서 실제로 났다)
    said = " · ".join(words.decision(d) for d in parcels.FIELD_CONSUMERS["drainage"])
    # [2026-10-06] 카드는 **아직 안 넣은** 상태라 「넣으면 …」 이고, 넣은 뒤(확인 줄)가 「이것으로 …」 다 — 같은 문장, 다른 때(조건 없는 안내는 다른 사실)
    assert f"넣으면 {said} 판단이 배수 값 '나쁨' 을 읽습니다 — 지금 답은 그 값 없이 낸 것입니다" in r2["text"], r2["text"][:200]
    assert "이것으로" not in r2["text"]                                                        # 넣기 전에 이미 읽는다고 말하지 않는다
    rec = chat.confirm(m["id"], 0, now=NOW)
    assert rec["opens"] == list(parcels.FIELD_CONSUMERS["drainage"]) and rec["opens_line"].startswith(f"이것으로 {said} 판단이 배수 값 '나쁨' 을 읽습니다")
    for text in (rec["opens_line"], words.opened("use", "종구 생산"), words.opened("use", "종구 생산", pending=True), words.opened("use", "판매")):
        assert not [w for w in JARGON if w in text], text
        assert words.plain(text) == text
    assert "종구 기준으로 읽습니다" in words.opened("use", "종구 생산") and "종구" not in words.opened("use", "판매")
    assert words.opened("soil_texture", "양토") == ""                                       # 읽는 판단이 없는 값은 열었다고 말하지 않는다
    src = (ROOT / "frontend" / "serve.py").read_text(encoding="utf-8")
    body = src[src.index('p.endswith("/confirm")'):src.index('p.endswith("/choose")')]
    assert 'rec.get("opens_line")' in body and "rec['opens_line']" in body                 # 확인 직후 화면 줄이 그것을 싣는다(배선)
    assert serve.make_server                                                               # 화면 모듈이 적재된다(배선 검사가 본 소스가 그 모듈이다)


def test_the_parcel_form_is_the_third_place_an_answer_lands_and_it_speaks_the_same_line(srv):
    """[§7.5 지점] 답을 넣는 자리는 셋 — 채팅 초안 줄 · 확인 직후 줄 · 밭 정보 폼. 셋 다 words.opened 하나를 부른다(폼만 키 이름 'drainage' 를 내고 무엇이 열렸는지
    말하지 않았다 — 발행자가 10-14 전에 여기서 「종구 생산」 을 넣는다)."""
    import html
    st, body = _post(srv, "/me/parcel", {"id": "p001", "drainage": "나쁨"})
    body = html.unescape(body)
    said = " · ".join(words.decision(d) for d in parcels.FIELD_CONSUMERS["drainage"])
    assert st == 200 and f"이것으로 {said} 판단이 배수 값 '나쁨' 을 읽습니다" in body and "판정이 읽는 값 drainage" not in body and "배수" in body
    st, body = _post(srv, "/me/parcel", {"id": "p001", "use": "종구 생산"})
    body = html.unescape(body)
    assert st == 200 and "용도 값 '종구 생산' 을 읽습니다" in body and "재배 달력도 종구 기준으로 읽습니다" in body
    st, body = _post(srv, "/me/parcel", {"id": "p001", "soil_texture": "양토"})
    body = html.unescape(body)
    assert st == 200 and "이것으로" not in body and "지금 판단이 읽는 값은 없습니다" in body and "토성" in body     # 소비자 0 — 열렸다고 말하지 않는다
    # 셋이 한 문장을 부른다 — 사본이 없다. [2026-10-06] `send` 는 카드 문장 정본(`chat.card_line`)을 거쳐 부른다(그 정본도 여기서 본다 — 한 겹 깊어진 것이지 느슨해진 것이 아니다)
    for rel, fn, reach in (("frontend/chat_pages.py", "def handle_parcel_form", ("words.opened(", "_w.opened(")),
                           ("ingest/chat.py", "def _confirm_locked", ("words.opened(", "_w.opened(")),
                           ("ingest/chat.py", "def send", ("card_line(",)),
                           ("ingest/chat.py", "def card_line", ("words.opened(", "_w.opened("))):
        src = (ROOT / rel).read_text(encoding="utf-8")
        body_ = src[src.index(fn):src.index("\ndef ", src.index(fn) + 10)]
        assert any(t in body_ for t in reach), (rel, fn, reach)
    assert "이것으로 " not in (ROOT / "ingest" / "chat.py").read_text(encoding="utf-8") and "이것으로 " not in (ROOT / "frontend" / "chat_pages.py").read_text(encoding="utf-8")


def test_an_answer_outside_the_vocabulary_opens_nothing_and_says_so_by_not_claiming_it():
    """라이브 실측 2026-10-03 — 발행자 일지 문장. 관찰로는 읽히되 배수 값으로 묶이지 않는다(기준 문면 전 · §7 발행자 몫) — 그래서 「연 판단」 줄도 나가지 않는다."""
    _, r = chat.send(SID, "풀 뽑았다", today=T34, now=NOW)
    assert asks.pending(SID)["fields"] == ["drainage"]
    t = "밭에 나가 확인하니 고랑 물 빠짐이 잘 되고 있고, 잎 끝 황화 현상은 더 진행이 되지 않음이 확인이 되었다."
    m, r2 = chat.send(SID, t, today=T34, now=NOW)
    assert all(d["kind"] != "parcel.field" for d in m["drafts"]) and m["drafts"][0]["kind"] == "observation.note"
    assert "이것으로" not in r2["text"].split("하나 물을 것")[0] and parcels.by_id("p001").get("drainage") is None
