# -*- coding: utf-8 -*-
# [대파 걷기 2026-10-04 · 묻기 전 원장 읽기의 §7.5 지점 판] 발행자 화면의 두 작목(쪽파 · 대파)은 **같은 밭(p001)** 이다. 10-03 일지의 「고랑 물 빠짐이 잘 되고 있다」 는
# 쪽파 채팅에 적혔고, 규칙(ingest.known)은 **그 작목의 일지만** 읽었다 — 대파 채팅은 배수를 모른 채 다시 물을 자리였다(실측: known_field(대파, drainage) = None).
# 밭 정보 값(배수 · 용도)은 필지의 것이라 같은 밭의 모든 작목 일지가 한 원장이다. 농사 값(인증)은 작목의 것 — 그대로 작목 일지만.
from __future__ import annotations

import inspect
from datetime import date, datetime, timezone

from ingest import chat, known, parcels, subjects

T = date(2026, 10, 4)
NOW = datetime(2026, 10, 4, 9, 0, tzinfo=timezone.utc)
SID = "p001-jjokpa-2026f"
DRAIN_LINE = "밭에 나가 확인하니 고랑 물 빠짐이 잘 되고 있다"


def _second(parcel="p001"):
    return subjects.add("대파", "2026 가을", status="재배 중", parcel=parcel, anchor="2026-10-01")["id"]


def test_a_parcel_value_written_in_one_crops_diary_is_known_to_the_other_crop_on_the_same_parcel():
    sid2 = _second()
    assert set(known.parcel_siblings(subjects.by_id(sid2))) == {SID, sid2}
    m, _ = chat.send(SID, DRAIN_LINE, today=T, now=NOW)
    chat.confirm(m["id"], 0, now=NOW)                                                      # 쪽파 일지에 들어갔다
    k = known.known_field(subjects.by_id(sid2), "drainage")
    assert k and k["from"] == "observation" and k["value"] == "좋음" and k["subject"] == SID       # 대파가 읽는다 · 어느 작목의 일지였는지 안다
    props = known.proposals(subjects.by_id(sid2), parcels.FIELDS_READ_BY_JUDGMENT)
    d = next(p for p in props if p["field"] == "drainage")
    assert d["kind"] == "parcel.field" and d["value"] == "좋음" and "같은 밭의 다른 작목" in d["why"] and "쪽파" in d["why"]
    m2, r2 = chat.send(sid2, "오늘 물 줬다", today=T, now=NOW)
    assert any(x.get("kind") == "parcel.field" and x.get("field") == "drainage" for x in m2["drafts"])    # 대파 채팅에 배수 카드가 선다
    assert "배수(좋음 · 보통 · 나쁨" not in r2["text"]                                                   # 그리고 배수를 묻지 않는다


def test_the_card_already_standing_in_the_other_crops_chat_is_not_raised_twice_and_the_question_still_does_not_come():
    sid2 = _second()
    m, _ = chat.send(SID, DRAIN_LINE, today=T, now=NOW)
    chat.confirm(m["id"], 0, now=NOW)                                                      # 본 것이 일지에 들어갔다
    m1, _ = chat.send(SID, "오늘 트랩 봤다", today=T, now=NOW)                               # 다음 말에 배수 카드가 쪽파 채팅에 선다(넣지 않고 둔다)
    assert any(x.get("kind") == "parcel.field" for x in m1["drafts"])                      # 쪽파에 카드
    m2, r2 = chat.send(sid2, "오늘 물 줬다", today=T, now=NOW)
    assert not any(x.get("kind") == "parcel.field" for x in m2["drafts"])                  # 대파에는 같은 카드를 또 안 올린다
    assert "배수(좋음 · 보통 · 나쁨" not in r2["text"]                                     # 그래도 묻지 않는다 — 일지가 읽힌다


def test_a_crop_on_another_parcel_does_not_read_this_parcels_diary_and_cert_stays_per_crop():
    far = _second(parcel="p002")
    m, _ = chat.send(SID, DRAIN_LINE + ". 인증은 무농약이다", today=T, now=NOW)
    for i in range(len(m["drafts"])):
        if m["drafts"][i].get("kind") == "observation.note":
            chat.confirm(m["id"], i, now=NOW)
    assert known.known_field(subjects.by_id(far), "drainage") is None                       # 다른 밭 — 안 읽는다
    sid2 = _second()
    assert known.known_subject_field(subjects.by_id(sid2), "cert") is None                   # 같은 밭이라도 인증은 작목의 것
    assert known.known_subject_field(subjects.by_id(SID), "cert")                            # 쪽파 자신은 읽는다


def test_a_use_declared_in_one_crops_diary_does_not_become_the_other_crops_card():
    """용도는 등록부엔 밭 값이지만 선언은 작목의 것 — 「이 쪽파는 종구생산을 위한 목적이다」 가 같은 밭의 대파에 종구 카드를 세우면 틀린다(밭 값인지 작목 값인지는 발행자 결정)."""
    sid2 = _second()
    m, _ = chat.send(SID, "이 쪽파는 종구생산을 위한 목적이다", today=T, now=NOW)
    assert m["drafts"][0]["kind"] == "parcel.field" and m["drafts"][0]["field"] == "use"      # 쪽파 채팅엔 카드(선언 갈래)
    assert known.known_use_differs(subjects.by_id(sid2)) is None                              # 대파는 그 선언을 자기 것으로 읽지 않는다
    m2, _ = chat.send(sid2, "오늘 물 줬다", today=T, now=NOW)
    assert not any(x.get("kind") == "parcel.field" and x.get("field") == "use" for x in m2["drafts"])
    assert "use" not in known.PARCEL_SHARED_FIELDS and set(known.PARCEL_SHARED_FIELDS) == {"drainage", "environment"}


def test_parcel_readers_go_through_the_sibling_canon_and_the_crop_readers_do_not():
    src = inspect.getsource(known.known_field)
    assert "parcel_siblings(subject) if field in PARCEL_SHARED_FIELDS else" in src              # 밭이 공유하는 값만 같은 밭 전체
    for fn in (known.known_use_differs, known.known_subject_field):
        assert "parcel_siblings" not in inspect.getsource(fn), fn.__name__                      # 용도 선언 · 인증은 작목의 것
    assert "known.parcel_siblings(s)" in inspect.getsource(chat.send) and "known.PARCEL_SHARED_FIELDS" in inspect.getsource(chat.send)   # 채팅도 같은 밭의 카드를 한 번만 — 공유 값만
