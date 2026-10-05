# -*- coding: utf-8 -*-
# [2026-10-05 재측정] 10/07 에 무슨 경보가 서는지를 재다가(발행자에게 "10/07 부터 둘" 이라고 말해 온 그 줄) **다른 것**이 나왔다.
# 화면은 `parcels.FIELD_CONSUMERS` 로 「넣으면 어느 판단이 읽습니다」 를 말하는데, 그 표가 **선언**이지 사실이 아니었다:
#     용도  적힌 소비자 1(출하·저장)  ← 실제로 바뀌는 판정 3(수확 시기 · 위험 경보 · 출하·저장)
#     배수  적힌 소비자 1(위험 경보)   ← 실제 2(위험 경보 · 배수 경보 — 농가에게는 다른 카드다)
# 그래서 발행자에게 *"용도를 넣으면 출하·저장 판단이 읽습니다"* 라고 말하고 있었다. 실제로 그 값은 **10/07 부터 매일 나가는 잎 기준 경보 둘을 멈추고**
# 수확 시기를 종구 기준으로 돌린다 — 가장 큰 둘을 빼고 가장 작은 하나만 말한 것이다(조건을 덜 말하는 것은 축약이 아니라 다른 사실이다).
#
# 이 검사는 표를 **다시 재서** 대조한다 — 값을 바꿔 판정을 돌리고, 달라진 결정 id 가 표와 같은지 본다. 선언을 믿지 않는다.
#   측정 한계: 노지/시설(environment)은 이 환경에 처방 원천(외부)이 없어 바꿔도 봉투가 안 변한다 — **소비자 0 이 아니라 못 잰 것**이라 재지 않고 사유를 적는다
#   (죽은 원천의 0 을 사실로 읽으면 소비자를 지우게 된다 — 측정 시점·조건 축).
from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest

from frontend import words
from ingest import parcels
from judge import registry, run as judge_run

ROOT = Path(parcels.__file__).resolve().parent.parent
T = date(2026, 10, 7)          # 수확 칸이 7일 뒤 열리는 날 — 용도가 바뀌면 가장 많이 달라지는 날이다(실측으로 고른 날)
# 값을 이렇게 바꿔 가며 잰다. (필드, 전, 후)
FLIPS = (("use", "시험 재배(자가)", "종구 생산"), ("drainage", None, "나쁨"))
UNMEASURABLE = {"environment": "처방 원천(외부)이 이 환경에 없어 노지↔시설이 봉투를 바꾸지 않는다 — 소비자 0 이 아니라 못 잰 것"}


def _judge_with(tmp_path, monkeypatch, field: str, value: str | None) -> dict[str, tuple]:
    """밭 값 하나만 바꿔 그날의 판정 전부를 돌린다 — 운영 data 는 건드리지 않는다(덮개 경로만)."""
    doc = json.loads((ROOT / "data" / "parcels_seed.json").read_text(encoding="utf-8"))
    rows = doc["parcels"] if isinstance(doc, dict) and "parcels" in doc else doc
    if value is None:
        rows[0].pop(field, None)
    else:
        rows[0][field] = value
    p = tmp_path / f"parcels_{field}_{value}.json"
    p.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setenv("AGRODSS_PARCELS_PATH", str(p))
    monkeypatch.setenv("AGRODSS_PARCELS_LOCAL_PATH", str(p))
    monkeypatch.setenv("AGRODSS_PARCELS_LEGACY_PATH", str(tmp_path / "none.json"))
    out = {}
    for _s, envs, _info in judge_run.all_judgments(T):
        for e in envs:
            ed = e.to_dict()
            r = ed.get("result") or {}
            out[ed["decision_id"]] = (ed["kind"], len(r.get("alerts") or []), str(r.get("summary") or r.get("why") or ""), tuple(str(n) for n in (ed.get("notes") or [])))
    return out


@pytest.mark.parametrize("field,before,after", FLIPS)
def test_the_table_says_exactly_the_judgments_that_change(tmp_path, monkeypatch, field, before, after):
    a = _judge_with(tmp_path, monkeypatch, field, before)
    b = _judge_with(tmp_path, monkeypatch, field, after)
    changed = {k for k in set(a) | set(b) if a.get(k) != b.get(k)}
    assert changed, (field, "값을 바꿨는데 아무 판정도 안 달라졌다 — 그러면 소비자 선언이 거짓이거나 측정이 닿지 않은 것이다")
    assert changed == set(parcels.FIELD_CONSUMERS[field]), (field, sorted(changed), sorted(parcels.FIELD_CONSUMERS[field]))


def test_the_unmeasurable_field_is_said_so_not_dropped():
    """**안 하기로 한 것**과 **빠뜨린 것**을 가른다 — 못 잰 필드는 표에서 지우지 않고 이유를 남긴다(죽은 원천의 0)."""
    for field, why in UNMEASURABLE.items():
        assert field in parcels.FIELD_CONSUMERS and parcels.FIELD_CONSUMERS[field], field
        assert field not in dict((f, 1) for f, _, _ in FLIPS), f"{field} 를 재게 됐으면 측정 목록으로 옮긴다: {why}"
        assert "측정 한계" in (ROOT / "ingest" / "parcels.py").read_text(encoding="utf-8")      # 사유가 소스에 적혀 있다(다음 사람이 읽는다)


def test_the_sentence_names_the_big_ones_first():
    """농가·발행자가 읽는 줄 — 용도는 수확 시기와 위험 경보를 **먼저** 말한다(출하·저장만 말하면 넣을 이유가 작아 보인다)."""
    said = words.opened("use", "종구 생산")
    names = [words.decision(d) for d in parcels.FIELD_CONSUMERS["use"]]      # 이름은 정본에서 — 검사에 박으면 재측정마다 거짓 실패다
    assert said.startswith("이것으로 " + " · ".join(names) + " 판단이"), said
    assert names[:2] == [words.decision("harvest_timing"), words.decision("risk_alert")], names      # 큰 것이 먼저다(출하·저장만 들으면 넣을 이유가 작아 보인다)
    assert "종구 기준으로 읽습니다" in said


def test_every_shown_decision_name_is_already_plain_words():
    """[전수 2026-10-05] 이름이 `DECISION_SAID` 에 없으면 등록부 이름으로 떨어지는데 둘이 안쪽 말을 싣고 있었다(「배수 경보(칸 4)」) —
    사람 말 표가 그것을 또 고쳐 같은 문장이 plain() 전후로 달라졌다. 보이는 이름은 그 자체로 사람 말이어야 한다(양방향: id 가 그대로 나가지도 않는다)."""
    import ingest.chat  # noqa: F401 — 등록부 적재
    from judge import stage_decisions  # noqa: F401
    ids = sorted(registry.all_decisions())
    assert len(ids) >= 10, ids
    for d in ids:
        said = words.decision(d)
        assert said != d, d
        assert words.plain(said) == said, (d, said, words.plain(said))
