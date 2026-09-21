# -*- coding: utf-8 -*-
# [발행자 2026-09-21 — 절차를 장치로] *"입력 자리를 만든 그 자리에서 소비자를 센 것이 이걸 잡은 방법입니다. 이건 절차로 굳힐
# 값이 있어 보입니다 — 새 입력 필드를 만들 때 그 값을 읽는 곳을 함께 세는 것. §7.5 전수와 같은 계열인데 트리거가 다릅니다."*
#
# 그래서 세는 일을 **사람의 성실성에 맡기지 않는다.** 화면이 받는 필드는 둘 중 하나로 선언돼야 하고, 선언이 사실인지를
# **동작으로** 확인한다. 새 필드를 넣으면 어느 쪽인지 적기 전까지 관문이 빨갛다.
#
#   FIELDS_READ_BY_JUDGMENT   그 값을 바꾸면 봉투가 바뀐다      ← 바뀌지 않으면 거짓 선언이다
#   FIELDS_STORED_ONLY        바꿔도 봉투가 그대로다(G1 소비자 0) ← 바뀌면 이제 소비자가 생긴 것이니 표지를 고쳐야 한다
#
# 이 형태가 앞의 G1 셋과 다른 점(발행자 판독): 앞의 셋은 **한쪽만 지어진 것**이고 이번 것은 **양쪽이 다 지어졌는데 사이가
# 안 이어진 것**이다. 축 등록 · 격자 칸 선언 · 문서 "필지 보정 ②" · 입력 폼이 다 있는데 값이 판정으로 가는 경로만 없다.
# 세 곳이 서로를 지지하므로 **문서를 읽어서는 절대 안 보인다** — 전수로 세야 나오고, 이 검사가 그 셈을 대신한다.
from __future__ import annotations

from datetime import date

import pytest

from ingest import media, parcels
from judge import stage_decisions as SD

SID = "p001-jjokpa-2026f"
TODAY = date(2026, 9, 21)

# 각 필드에 넣어 볼 값 — 어휘가 있으면 그 어휘에서, 없으면 그럴듯한 값 하나(대리값이 아니라 **검사용 자극**이다)
PROBE = {"area_m2": 330, "use": "판매", "microclimate": "사방 트임 · 안개 없음",
         "seed_source": "자가 채종", "cert_legal": "제0000호 · 어느 인증기관"}


def _value(field: str):
    opts = parcels.FIELD_CHOICES.get(field)
    return opts[-1] if opts else PROBE[field]


def _subject() -> dict:
    raw = next(s for s in media.load_subjects() if s["id"] == SID)
    return parcels.enrich_subject(raw, parcels.by_id("p001"))


def _bodies(subject: dict) -> list[tuple[str, str]]:
    """그 재배 단위의 단계 결정 봉투 전부 — 시각만 뺀 본문(무엇이 달라졌는지 견주려고)."""
    out = []
    for e in SD.judge_all(subject, TODAY):
        d = e.to_dict()
        d.pop("as_of")
        out.append((e.decision_id, repr(d)))
    return out


def test_every_input_field_is_declared_as_read_or_stored_only():
    """분할 고정 — 새 입력 필드를 만들면 **어느 쪽인지 적기 전까지** 여기가 빨갛다(이것이 발행자가 말한 트리거다)."""
    fields = set(parcels.input_fields())
    read, stored = set(parcels.FIELDS_READ_BY_JUDGMENT), set(parcels.FIELDS_STORED_ONLY)
    assert not (read & stored), sorted(read & stored)                     # 양쪽에 동시에 있을 수 없다
    assert fields - (read | stored) == set(), f"선언 없는 입력 필드: {sorted(fields - (read | stored))} — 읽는 곳을 세고 적는다"
    assert (read | stored) - fields == set(), f"입력 필드가 아닌 것을 선언했다: {sorted((read | stored) - fields)}"


@pytest.mark.parametrize("field", parcels.FIELDS_STORED_ONLY)
def test_a_field_declared_stored_only_really_changes_no_judgment(field):
    """선언이 사실인가 — **동작으로** 잰다. 소비자가 생기는 날 이 검사가 깨지고, 그때 화면 표지도 함께 고쳐진다(G1 래칫)."""
    before = _bodies(_subject())
    parcels.set_fields("p001", overwrite=True, **{field: _value(field)})
    after = _bodies(_subject())
    changed = [a for (a, b), (_, c) in zip(before, after) if b != c]
    assert not changed, f"'{field}' 를 넣으니 결정 {changed} 의 답이 달라졌다 — 이제 소비자가 있다. FIELDS_READ_BY_JUDGMENT 로 옮기고 화면 표지를 고친다"


def test_a_field_declared_read_really_does_change_a_judgment():
    """반대편 — 막는 것을 검사하면 통과하는 것도 검사한다. '읽는다'는 선언이 빈말이면 화면이 거짓을 말하게 된다."""
    parcels.set_fields("p001", mall_supply=True, overwrite=True)          # 몰 납품 게이트를 열고 use 만 흔든다
    before = _bodies(_subject())
    parcels.set_fields("p001", use="판매", overwrite=True)
    assert [a for (a, b), (_, c) in zip(before, _bodies(_subject())) if b != c] == ["ship_or_store"]
