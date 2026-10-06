# -*- coding: utf-8 -*-
# [10/07~10/16 걷기 2026-10-06] 열흘 × 물음 여섯 = **예순 답**을 발행자 PC 상태(용도 미기재 + 일지 10-04 종구 선언)로 걸었다.
# 예외 0 · 내부 말 0 이었는데, **용도 카드가 실린 답은 하나**였다 — 같은 초안을 다시 올리지 않기 때문이다(그 자체는 옳다).
# 그래서 나머지 **쉰아홉**은 잎 기준 사실(수확 기간 10/14~11/3 · 잎 노화 · 도복 · 잎 손상)을 **그 값과 잇지 않고** 말했다.
# 처방: 답이 그 사실을 한 줄로 말한다 — 「이 답은 용도 값 없이 낸 것입니다 — 일지 2026-10-04 에서 읽은 '종구 생산' 이 아직 안 들어갔습니다(…에서 넣으면 다시 답합니다)」.
# 이미 있던 같은 꼴의 일반형이다(`drought_alert` 의 「아직 안 넣은 관수 기록 N건」 — 그쪽은 미확인 **사건**, 이쪽은 미확인 **값**).
#
# 이 검사가 고정하는 것 다섯:
#   ① 그 값을 **읽는 판정**의 답에만 붙는다(`parcels.FIELD_CONSUMERS` 측정 정본 · 안 읽는 판정엔 안 붙는다 — 양방향)
#   ② 일지에서 **읽혔고 아직 안 들어간** 때만(속성에 이미 있으면 안 붙는다 · 일지에 말이 없으면 안 붙는다)
#   ③ 카드가 **같은 답에 함께** 서 있으면 같은 말을 두 번 하지 않는다(card_line 이 「넣으면 …」 을 말한다)
#   ④ 사람 말 · 자리 이름은 계약에서(JARGON 0 · plain 안정)
#   ⑤ 날을 넘겨도 유지된다 — 사흘 × 물음 셋에서 **잎 기준 답은 전부** 카드 줄이나 이 줄 중 하나를 갖는다
from __future__ import annotations

import json
import shutil
from datetime import date, datetime, timezone
from pathlib import Path

import pytest

from frontend import words
from ingest import chat, events as ev, parcels
from tests.test_screen_speaks_plainly import JARGON

ROOT = Path(chat.__file__).resolve().parent.parent
SID = "p001-jjokpa-2026f"
LEAF = ("잎 노화", "도복", "잎 손상", "잎 길이")
CARD_SAID = "일지에 이미 적힌 말에서 읽었습니다"
WAIT_SAID = "이 답은 용도 값 없이 낸 것입니다"


@pytest.fixture()
def publisher_state(tmp_path, monkeypatch):
    """용도 미기재 + 일지에 종구 선언 — 발행자 PC 상태(운영 data 는 안 건드린다)."""
    doc = json.loads((ROOT / "data" / "parcels_seed.json").read_text(encoding="utf-8"))
    rows = doc["parcels"] if isinstance(doc, dict) and "parcels" in doc else doc
    rows[0].pop("use", None)
    p = tmp_path / "parcels.json"
    p.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
    shutil.copy(ROOT / "data" / "subjects.json", tmp_path / "subjects.json")
    for k, v in (("AGRODSS_PARCELS_PATH", p), ("AGRODSS_PARCELS_LOCAL_PATH", p), ("AGRODSS_PARCELS_LEGACY_PATH", tmp_path / "none.json"),
                 ("AGRODSS_SUBJECTS_PATH", tmp_path / "subjects.json"), ("AGRODSS_SUBJECTS_LOCAL_PATH", tmp_path / "subjects_local.json")):
        monkeypatch.setenv(k, str(v))
    ev.add_observation(SID, "종구생산을 위한 목적이다", "2026-10-04")
    return tmp_path


def _send(q: str, day: int = 8):
    d = date(2026, 10, day)
    return chat.send(SID, q, today=d, now=datetime(d.year, d.month, d.day, 9, tzinfo=timezone.utc))


def test_only_the_judgments_that_read_the_value_say_it(publisher_state):
    """양방향 — 용도를 읽는 판정(수확 시기)의 답에는 붙고, 안 읽는 판정(가뭄)의 답에는 안 붙는다."""
    from ingest import subjects
    s = subjects.by_id(SID)
    for did in parcels.FIELD_CONSUMERS["use"]:
        assert WAIT_SAID in chat.pending_value_line(s, did), did
    for did in ("drought_alert", "symptom_triage", "forecast_citation"):
        assert did not in parcels.FIELD_CONSUMERS["use"]                      # 전제부터 — 소비자 표에 없다
        assert chat.pending_value_line(s, did) == "", did


def test_it_appears_only_while_the_value_is_waiting(publisher_state, monkeypatch):
    from ingest import subjects
    s = subjects.by_id(SID)
    assert WAIT_SAID in chat.pending_value_line(s, "harvest_timing")
    parcels.set_fields("p001", use="종구 생산", overwrite=True)                 # 넣은 뒤 — 더 말하지 않는다
    assert chat.pending_value_line(subjects.by_id(SID), "harvest_timing") == ""
    # [주입 B 2026-10-06] 「일지에서 읽혔을 때만」 가드는 **속성에 이미 있는 값**에서만 드러난다(용도는 정본이 알아서 None 을 돌려줘 가드가 가려졌다) —
    # 배수로 잰다: 일지에 말이 있고 속성에도 값이 있으면 기다리는 값이 아니다
    ev.add_observation(SID, "고랑 물 빠짐이 잘 되고 있다", "2026-10-03")
    s2 = subjects.by_id(SID)
    assert "배수 값 없이" in chat.pending_value_line(s2, "risk_alert"), chat.pending_value_line(s2, "risk_alert")
    parcels.set_fields("p001", drainage="좋음", overwrite=True)
    assert chat.pending_value_line(subjects.by_id(SID), "risk_alert") == ""


def test_the_answer_does_not_say_it_twice(publisher_state):
    """카드가 함께 선 답(첫 물음)은 카드 줄이 「넣으면 …」 을 말한다 — 같은 말을 두 번 하지 않는다."""
    _m, first = _send("수확 언제 해요")
    assert CARD_SAID in first["text"] and WAIT_SAID not in first["text"], first["text"][:200]
    _m2, second = _send("서리 오나")                                            # 카드는 이미 섰으니 다시 안 오고 — 답이 그 사실을 말한다
    assert CARD_SAID not in second["text"] and WAIT_SAID in second["text"], second["text"][:200]


def test_the_line_speaks_plainly_and_names_the_place():
    said = words.waiting("use", "종구 생산", "2026-10-04")
    assert not [w for w in JARGON if w in said], said
    assert words.plain(said) == said
    from schema import labels
    assert labels.PLACES["parcel"] in said and "2026-10-04" in said and "'종구 생산' 이" in said      # 조사도 정본에서(산 → 이)


def test_every_leaf_answer_is_linked_to_the_value(publisher_state):
    """[걷기 축] 사흘 × 물음 셋 — 잎 기준 말을 하는 답은 **전부** 카드 줄이나 기다리는 값 줄 중 하나를 갖는다(둘 다 없으면 조건 없는 사실이다)."""
    seen = 0
    for day in (7, 8, 9):
        for q in ("수확 언제 해요", "서리 오나", "병충해 뭐 봐야 하나"):
            _m, r = _send(q, day)
            said = r["text"]
            if not any(w in said for w in LEAF):
                continue
            seen += 1
            assert (CARD_SAID in said) or (WAIT_SAID in said), (day, q, said[:200])
    assert seen >= 6, seen
