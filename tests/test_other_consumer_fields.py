# -*- coding: utf-8 -*-
# [낡음 대조 2026-10-06] 대장 U-20(「필지 축 열이 선언만 있고 읽는 쪽이 없다」)의 근거는 **2026-09-21 측정**이었다. 그 사이 용도·배수는 다시 재서 늘었는데(1→5 · 1→2)
# 「소비자 0」 여덟은 보름 동안 다시 재지 않았다 — 숫자는 시점을 잃으면 사실이 아니라 인상이다(§7.5 시점 축). 그래서 같은 방법으로 다시 쟀다.
#
#   재측정 2026-10-06(값을 넣고 날 셋 09-20 · 10-07 · 10-20 의 봉투 전부 대조)
#     토성 · 경사 · 관수 시설 · 야간 조명 · 미기상 · 면적 · 종구 출처   **0**(여전히)
#     대조군 배수                                                  2 — 도구가 살아있다(「전부 0」 은 도구 버그의 표지라 대조군을 함께 돌린다)
#     인증 근거                                                    0 **이 아니었다** — 판정은 안 읽지만 **몰 상품의 인증 표기**가 읽는다
#
# 봉투만 대조하는 측정은 그 소비자를 못 본다(사건 쪽 EVENT_CONSUMERS 의 「측정 경계」 와 같은 자리). 그 사이 화면은 인증 근거를 「읽는 판정 없음」 으로 표시했고,
# 그것은 **적을 이유를 지우는 거짓 표지**다 — 그 값이 없으면 법정 인증 표기는 영구히 「인증 표기 없음」 이다.
#
# **직렬 게이트가 하나 더 있다**(§7.5): 폼은 인증 근거를 **문자열**로 받고 소비자는 `cert_legal is True` 를 본다 — 문자열도 「true」 도 표기를 못 켠다(실측).
# 앞 게이트(표지)만 고치면 증상이 남는다. **뒤 게이트는 세션이 열지 않는다**(「인증서 확인」 의 요건은 법정 판단 · 발행자 몫) — 대신 그 사실을 검사가 적어 둔다.
#
# 이 검사가 고정하는 것 여섯:
#   ① 「소비자 0」 은 **다시 재서** 확인한다(대조군을 함께 — 쏠린 결과는 도구 버그의 표지)
#   ② 판정이 아닌 소비자는 **동작으로** 증명한다(값을 바꾸면 몰 표기가 바뀐다 · 양방향)
#   ③ 화면 표지가 셋으로 갈린다(판정이 읽음 · 다른 것이 읽음 · 아무도 안 읽음) — 그 값에 「읽는 판정 없음」 이 안 붙는다
#   ④ 넣은 직후 줄도 빈 문장이 아니다(빈 문장은 「아무 일도 안 생긴다」 로 읽힌다)
#   ⑤ 조건을 함께 싣는다(조건 없는 값은 근거 없는 값처럼 보인다 — G1 반대형)
#   ⑥ 뒤 게이트가 **아직 닫혀 있다는 사실**을 검사가 문서화한다(안 하기로 한 것 ≠ 빠뜨린 것 · 열리는 날 이 검사가 그것을 말한다)
from __future__ import annotations

import json
import re
import shutil
from datetime import date
from pathlib import Path

import pytest

from frontend import chat_pages, words
from ingest import media, parcels
from judge import run as judge_run
from mall import product
from tests.test_screen_speaks_plainly import JARGON

ROOT = Path(parcels.__file__).resolve().parent.parent
SID = "p001-jjokpa-2026f"
DAYS = (date(2026, 9, 20), date(2026, 10, 7), date(2026, 10, 20))
# 넣어 볼 값 — 대리값이 아니라 검사용 자극(어휘가 있으면 그 어휘에서)
PROBE = {"soil_texture": "사질토", "slope": "경사 15도", "irrigation": "스프링클러", "night_light": "있음",
         "microclimate": "서늘한 골짜기", "area_m2": "1200", "seed_source": "자가 채종",
         "cert_legal": "제0000호 · 어느 기관", "drainage": "나쁨"}


def _judge(tmp_path, monkeypatch, field: str, value: str | None, T: date) -> dict[str, str]:
    doc = json.loads((ROOT / "data" / "parcels_seed.json").read_text(encoding="utf-8"))
    rows = doc["parcels"] if isinstance(doc, dict) and "parcels" in doc else doc
    if value is None:
        rows[0].pop(field, None)
    else:
        rows[0][field] = value
    p = tmp_path / f"p_{field}_{value}_{T}.json"
    p.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setenv("AGRODSS_PARCELS_PATH", str(p))
    monkeypatch.setenv("AGRODSS_PARCELS_LOCAL_PATH", str(p))
    monkeypatch.setenv("AGRODSS_PARCELS_LEGACY_PATH", str(tmp_path / "none.json"))
    out = {}
    for _s, envs, _i in judge_run.all_judgments(T):
        for e in envs:
            ed = e.to_dict()
            out[ed["decision_id"]] = json.dumps({"k": ed["kind"], "r": ed.get("result"), "n": ed.get("notes")},
                                                ensure_ascii=False, sort_keys=True)
    return out


def _consumers(tmp_path, monkeypatch, field: str) -> set[str]:
    seen: set[str] = set()
    for T in DAYS:
        a, b = _judge(tmp_path, monkeypatch, field, None, T), _judge(tmp_path, monkeypatch, field, PROBE[field], T)
        seen |= {k for k in set(a) | set(b) if a.get(k) != b.get(k)}
    assert a and len(a) >= 10, f"판정이 거의 안 돌았다 — 측정이 닿지 않은 것이다(값 {field} 의 0 을 사실로 읽으면 안 된다): {sorted(a)}"
    return seen


def test_the_zero_consumer_fields_are_re_measured_with_a_control(tmp_path, monkeypatch):
    """[①] 보름 전 측정을 다시 잰다 — 대조군(배수 2)이 함께 떠야 「0」 을 믿을 수 있다."""
    control = _consumers(tmp_path, monkeypatch, "drainage")
    assert control == set(parcels.FIELD_CONSUMERS["drainage"]), control      # 도구가 살아있다
    for field in parcels.FIELDS_STORED_ONLY:
        assert _consumers(tmp_path, monkeypatch, field) == set(), field      # 생기는 날 여기가 깨지고 표지도 함께 고쳐진다


def test_the_other_consumer_is_proved_by_behaviour_not_by_a_comment(tmp_path, monkeypatch):
    """[② 양방향] 판정은 안 바뀌고(봉투 0) **몰 표기는 바뀐다** — 주석이 아니라 동작이 증거다."""
    assert _consumers(tmp_path, monkeypatch, "cert_legal") == set()          # 판정 쪽은 0 이 맞다(그래서 「판정이 읽는 값」 이 아니다)
    subject = {"id": SID, "cert": "무농약"}
    off = product.cert_label({"cert_legal": None}, subject)
    on = product.cert_label({"cert_legal": True}, subject)
    assert off == product.NO_CERT_LABEL and on != off and "무농약" in on, (off, on)
    assert product.cert_label(None, subject) == product.NO_CERT_LABEL        # 필지가 없으면 표기도 없다
    assert "cert_legal" in parcels.FIELD_OTHER_CONSUMERS and "cert_legal" not in parcels.FIELDS_STORED_ONLY


def test_the_screen_label_splits_three_ways():
    """[③] 그 값에 「읽는 판정 없음」 이 붙으면 농가가 적을 이유가 사라진다."""
    note = chat_pages._parcel_note("cert_legal")
    who, cond = parcels.FIELD_OTHER_CONSUMERS["cert_legal"]
    assert who in note and cond in note and chat_pages.STORED_ONLY_LABEL not in note, note
    assert chat_pages.READS_LABEL in chat_pages._parcel_note("drainage")
    assert chat_pages.STORED_ONLY_LABEL in chat_pages._parcel_note("slope")   # 반대편 — 정말 아무도 안 읽는 값은 그대로 말한다
    form = chat_pages.parcel_form(parcels.by_id("p001") or {"id": "p001"})
    assert who in form, "밭 정보 폼에서 그 표지가 보인다(표지를 만들고 화면에 안 실으면 아무것도 안 고친 것이다)"


def test_the_line_after_saving_is_not_empty_for_such_a_field():
    """[④⑤] 빈 문장은 「아무 일도 안 생긴다」 로 읽힌다 — 무엇이 읽는지와 **조건**을 함께 말한다."""
    said = words.opened("cert_legal", "제0000호 · 어느 기관")
    who, cond = parcels.FIELD_OTHER_CONSUMERS["cert_legal"]
    # [주입 C] 「cond in said」 만 보면 **빈 조건이 통과한다**(빈 문자열은 어디에나 있다 — 값 대조가 공허한 것과 같은 축) → 조건이 있는지부터 본다
    assert cond.strip() and who.strip(), (who, cond)
    assert said and who in said and cond in said and "판정은 이 값을 읽지 않습니다" in said, said
    assert re.search(r"\([^)]{6,}\)\.$", said), said                          # 조건이 괄호로 실려 있다(빈 괄호가 아니다)
    assert words.plain(said) == said and not [w for w in JARGON if w in said]
    assert words.opened("cert_legal", "제0000호", pending=True).startswith("넣으면")
    assert words.opened("slope", "경사 15도") == ""                           # 반대편 — 아무도 안 읽는 값엔 아무 말도 하지 않는다(§5-1)
    assert "'제0000호 · 어느 기관' 을" in said                                 # 조사도 정본에서(호 → 을)


def test_the_second_gate_is_recorded_as_still_closed():
    """[⑥] 폼은 **문자열**을 받고 소비자는 `cert_legal is True` 를 본다 — 둘이 안 맞아 표기가 영구히 안 선다.
    세션이 열 게이트가 아니라(법정 요건 — 발행자) **닫혀 있다는 사실을 적어 둔다**. 열리는 날 이 검사가 그것을 말한다."""
    subject = {"id": SID, "cert": "무농약"}
    for typed in ("제0000호 · 어느 기관", "true", "확인", "1"):
        assert product.cert_label({"cert_legal": typed}, subject) == product.NO_CERT_LABEL, typed
    src = (ROOT / "ingest" / "parcels.py").read_text(encoding="utf-8")
    assert "직렬 게이트" in src and "발행자 몫" in src                           # 사유가 소스에 적혀 있다(다음 사람이 읽는다)
    assert "cert_legal" not in parcels.FIELD_CHOICES, "어휘가 생기면(예 참/거짓) 그때 뒤 게이트가 열린 것이다 — 이 검사를 고친다"


@pytest.mark.parametrize("field", sorted(parcels.FIELD_OTHER_CONSUMERS))
def test_such_a_field_is_not_asked_for_as_if_it_opened_a_judgment(field):
    """물음 문장도 같은 축이다 — 「채우면 판정이 열립니다」 로 묻지 않는다(§5-1: 여는 것이 없으면 그 물음은 하지 말아야 한다)."""
    from ingest import questions
    asked = [q for q in getattr(questions, "PARCEL_ASKS", ()) if getattr(q, "field", None) == field]
    assert not asked, f"{field} 를 묻는 문장이 있다 — 판정이 안 읽는 값을 판정 때문에 묻지 않는다: {asked}"
