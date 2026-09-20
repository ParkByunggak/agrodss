# -*- coding: utf-8 -*-
# [칸 3 재측정 · 2026-09-20 / 코드 평가 B14] 평가문은 "격자 위험명→병해충 대응표 **세 벌**"이라고 적었다.
# 재보니 **세 벌이 아니라 서로 다른 셋**이었다(근거란 시점 규율 — 재료로 쓰기 전에 다시 잰다):
#   · `evolve.risk_family`   농가가 말한 **피해 어휘** → 갈래(경보↔피해 대조용)
#   · `psis.pest_terms`      격자 **위험 이름** → 등록약제 검색어(병해충이 아닌 위험은 빈 목록)
#   · `risk_alert` pest_name_keys   격자 위험 ↔ **예찰 레코드의 병해충명**(결정 등록부의 데이터)
# 실측(2026-09-20 · 쪽파 가을 격자 10위험): 셋이 어긋나는 이름 0. `match_risk` 의 이름 겹침 대체도
# `bool(x and y)` 로 막혀 있어 "둘 다 미분류면 아무거나 적중"이 나지 않는다 — **오늘 결함 없음**.
#
# 그래서 처방이 아니라 **래칫**이다. 두 벌의 어휘는 손으로 유지되고 서로 다르다(psis 에 선충·달팽이, evolve 에 해충·구더기).
# 둘째 작목 격자(M-8)가 들어오는 순간이 어긋나는 자리다 — 그때 조용히 어긋나면 되먹임이 피해를 경보에 못 붙인다.
from __future__ import annotations

import json
from pathlib import Path

import pytest

from ingest import psis
from judge import evolve, registry
from judge import risk_alert as _risk_alert    # noqa: F401 — 결정 등록부는 결정 모듈을 읽어야 채워진다(안 부르면 get() 이 None)


ROOT = Path(__file__).resolve().parent.parent
GRIDS = sorted((ROOT / "data" / "grid").glob("*.json"))


def _risk_names() -> list[str]:
    out = []
    for f in GRIDS:
        unit = json.loads(f.read_text(encoding="utf-8"))
        for s in unit.get("stages", []):
            rs = s.get("risks")
            if isinstance(rs, list):
                out += [r["name"] for r in rs if r.get("name")]
    return out


def test_there_are_grids_to_measure():
    assert _risk_names(), "격자 위험 이름이 없다 — 래칫이 빈 채로 초록이 된다"


@pytest.mark.parametrize("name", _risk_names())
def test_a_pest_risk_is_a_pest_in_every_mapping(name):
    """병해충 위험이면 셋 다 그렇게 읽어야 한다 — 한 곳만 모르면 그쪽 통로가 조용히 끊긴다."""
    keys = registry.get("risk_alert").params["pest_name_keys"]
    is_pest_for_psis = bool(psis.pest_terms(name))
    has_scouting_keys = any(rn in name or name in rn for rn in keys)
    fam = evolve.risk_family(name)
    if is_pest_for_psis:
        assert fam in ("해충", "병"), f"{name}: PSIS 는 병해충으로 보는데 대조 갈래가 {fam!r} — 피해가 경보에 안 붙는다"
        assert has_scouting_keys, f"{name}: PSIS 는 병해충으로 보는데 예찰 키가 없다 — 신호가 안 닿는다"
    else:
        assert not has_scouting_keys, f"{name}: 예찰 키가 있는데 PSIS 는 병해충이 아니라고 읽는다"


def test_unclassified_names_do_not_match_everything():
    # 이름 겹침 대체가 빈 문자열에서 참이 되면 아무 피해나 아무 경보에 붙는다(거짓 적중) — 그 경계를 고정한다
    assert not evolve.match_risk(None, "첫 서리 · 한파로 잎 손상")
    assert not evolve.match_risk("", "노균병")
    assert not evolve.match_risk("파종 적기 초과", "결주(출현 불량)")
    assert evolve.match_risk("서리에 얼었다", "첫 서리 · 한파로 잎 손상")        # 통과편 — 갈래가 같으면 붙는다
