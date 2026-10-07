# -*- coding: utf-8 -*-
# [10/07 측정 2026-10-06] 발행자 PC 상태(용도 미기재 + 일지 10-04 「종구생산을 위한 목적이다」)로 **내일** 농가가 볼 것을 재다가 나왔다.
# 수확 물음의 답은 잎 기준(10/14~11/3)으로 나가고 그 밑에 용도 카드가 서는데, **그 카드 줄이 둘을 빠뜨리고 있었다**:
#   ① 넣는 자리를 틀리게 말했다 — 밭 정보 카드인데 「영농일지에 들어갑니다」(단추 말은 「밭 정보에 넣기」 다 · 같은 결함을 고쳐 달라는 말 갈래에서 이미 고쳤는데 이 분기에 안 닿았다)
#   ② 「넣으면 어느 판단이 읽는지」 가 없었다 — 그 값이 **내일부터 나갈 잎 기준 경보 둘을 멎게 한다**(가장 값이 큰 한 줄인데 비어 있었다)
# 원인은 하나다: 카드 문장이 **분기마다 따로** 쓰여 있었다(물음+카드 · 카드만 · 그 밖). 그래서 문장을 `chat.card_line` 한 자리로 모았다.
#
# 이 검사가 고정하는 것 넷:
#   ① 한 문장 — 같은 초안이면 **어느 분기로 와도** 같은 카드 줄(사본이 없다)
#   ② 자리 — 밭 정보·농사 정보 카드는 「영농일지」 라고 말하지 않고, 일지로 가는 종류는 그대로 영농일지라고 말한다(양방향)
#   ③ 때 — 안 넣은 카드는 「넣으면 …」, 넣은 뒤는 「이것으로 …」(조건 없는 안내는 다른 사실이다)
#   ④ 10/07 실물 — 용도 카드 줄이 **수확 시기와 위험 경보**를 이름으로 말한다(그 둘이 그 값으로 달라지는 판단이다)
from __future__ import annotations

import json
import shutil
from datetime import date, datetime, timezone
from pathlib import Path

import pytest

from frontend import words
from ingest import chat, events as ev, parcels, subjects

ROOT = Path(chat.__file__).resolve().parent.parent
SID = "p001-jjokpa-2026f"
T = date(2026, 10, 7)          # 잎 기준 경보가 서는 첫날 — 발행자가 그 줄을 읽을 날
NOW = datetime(2026, 10, 7, 9, 0, tzinfo=timezone.utc)


def test_one_sentence_for_the_card_whatever_branch_it_came_from():
    """같은 초안이면 같은 줄 — 분기(물음+카드 · 카드만 · 그 밖)가 제 문장을 쓰면 한쪽이 또 빠진다."""
    draft = {"kind": "parcel.field", "field": "use", "value": "종구 생산", "why_key": "from_diary"}
    said = chat.card_line(draft)
    import ast
    src = (ROOT / "ingest" / "chat.py").read_text(encoding="utf-8")
    fn = next(n for n in ast.walk(ast.parse(src)) if isinstance(n, ast.FunctionDef) and n.name == "send")
    calls = [n for n in ast.walk(fn) if isinstance(n, ast.Call) and getattr(n.func, "id", "") == "card_line"]
    assert len(calls) >= 3, len(calls)                                  # 세 분기가 같은 함수를 부른다
    # [§7.1 4번 — 이 검사가 한 번 헛돌았다] 처음엔 소스 글자로 찾아 **주석**에 적힌 그 말(앞선 고침의 기록)을 잡았다. 문자열 상수만 본다(주석은 AST 에 없다)
    literals = [s.value for s in ast.walk(fn) if isinstance(s, ast.Constant) and isinstance(s.value, str)]
    assert not [s for s in literals if "영농일지에 들어갑니다" in s], "분기가 자기 문장을 다시 쓰고 있다"
    assert said == chat.card_line(dict(draft)), "같은 초안에 두 문장이 나온다"


def test_the_card_says_the_right_place():
    place = {"parcel.field": "밭 정보에 들어갑니다", "subject.field": "이 농사의 정보에 들어갑니다"}
    for kind, want in place.items():
        said = chat.card_line({"kind": kind, "field": "use" if kind == "parcel.field" else "cert",
                               "value": "종구 생산" if kind == "parcel.field" else "무농약", "why_key": "from_diary"})
        assert want in said and "영농일지" not in said, said
        assert f"'{chat.confirm_label(kind)}'" in said                   # 단추 말과 문장이 같은 자리에서 나온다
    # 반대편 — 일지로 가는 종류는 그대로 일지라고 말한다(과잉 처방이 아니다)
    # [축 이동 2026-10-07] 전에는 「영농일지에 들어갑니다」 를 **글자 그대로** 박아 두었는데, 자리 표(chat.PLACE_SAID)가 서면서 할 일·못 한 이유는
    # 「영농일지의 할 일로 들어갑니다」 처럼 **더 자세히** 말한다 — 계약은 그대로다(일지라고 말한다 · 밭 정보라고 하지 않는다). 그래서 문면이 아니라
    # **자리 정본에서 온 말인가**를 본다(약화가 아니라 형태 독립 — 꼴을 박으면 다음 처방이 또 이 검사를 깨뜨린다).
    for kind in ("event", "observation.note", "plan.farmer", "decision.noncompliance"):
        said = chat.card_line({"kind": kind, "text": "물 줬다", "type": "관수", "reason": "비가 와서", "task": "관수"})
        assert "영농일지" in said and "밭 정보에 들어갑니다" not in said, said
        assert chat.PLACE_SAID[kind] in said, (kind, said)                # 문면은 자리 표 하나에서 온다(분기가 제 문장을 다시 쓰지 않는다)
    # [주입 E 2026-10-06 — 아무 검사도 안 닿던 줄] 날짜가 비어 있는 초안은 **날짜를 넣고** 누르라고 말한다(그 말을 지워도 아무것도 안 터졌다)
    need = chat.card_line({"kind": "event", "type": "방제", "needs": ["observed_at"]})
    assert "날짜를 넣고" in need, need
    assert "날짜를 넣고" not in chat.card_line({"kind": "event", "type": "방제", "needs": []})


def test_before_and_after_are_different_sentences():
    pend, done = words.opened("use", "종구 생산", pending=True), words.opened("use", "종구 생산")
    assert pend.startswith("넣으면 ") and "지금 답은 그 값 없이 낸 것입니다" in pend
    assert done.startswith("이것으로 ") and "다음 답부터 그 근거에 실립니다" in done
    assert pend.split("판단이", 1)[1] == done.split("판단이", 1)[1].replace("다음 답부터 그 근거에 실립니다", "지금 답은 그 값 없이 낸 것입니다")
    assert words.opened("soil_texture", "양토", pending=True) == ""      # 읽는 판단이 없으면 열린다고도, 열릴 거라고도 말하지 않는다
    assert "넣으면" in chat.card_line({"kind": "parcel.field", "field": "use", "value": "종구 생산", "why_key": "from_diary"})


@pytest.fixture()
def publisher_state(tmp_path, monkeypatch):
    """발행자 PC 상태 — 용도 미기재 + 일지에 종구 선언(운영 data 는 안 건드린다)."""
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


def test_on_the_day_the_alerts_start_the_card_names_what_changes(publisher_state):
    """내일(10/07) 농가가 보는 줄 — 잎 기준 수확 답 **옆에** 그 값이 무엇을 바꾸는지가 있어야 한다."""
    _m, r = chat.send(SID, "수확 언제 해요", today=T, now=NOW)
    said = r["text"]
    assert "용도: 종구 생산" in said and "밭 정보에 들어갑니다" in said, said[-300:]
    for name in (words.decision("harvest_timing"), words.decision("risk_alert")):
        assert name in said.split("넣으면", 1)[-1], (name, said[-300:])
    assert "종구 기준으로 읽습니다" in said
    assert "영농일지에 들어갑니다" not in said.split("용도: 종구 생산", 1)[-1], said[-300:]
