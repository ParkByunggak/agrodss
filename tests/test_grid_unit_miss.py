# -*- coding: utf-8 -*-
# [U-23 2026-09-21] 격자를 못 읽었을 때 판정 카드가 **"할 일이 아니었다"** 고 말하지 않는다.
#
# 옛 형태: `_load_unit` 이 세 상태를 같은 `None` 으로 뭉갰고 소비자 일곱이 전부 `해당 없음` 을 냈다.
# 해당 없음은 I-1 §2-6 에서 *"아무리 채워도 안 바뀐다"* 는 뜻이다 — 그런데 셋 다 **격자가 오면 바뀐다**.
# 그래서 격자 파일 이름 한 글자가 어긋나면 카드 여덟 장이 **조용히** "할 일 없음" 이 됐다.
#
# 여기서 재는 것은 넷이다.
#
#   ① 종류      다섯 진입점 × 세 상태 — 어디서도 해당 없음이 나오지 않는다
#   ② missing   'unreadable'(있는데 못 읽음) 에서만 채운다 — 고칠 대상이 이미 있는 파일이라서
#   ③ 문면      셋이 서로 다른 말을 한다(종류만 고치고 문장을 안 고치면 표현 층에서 도로 갈린다 — G1 셋째)
#   ④ 반대편    격자는 멀쩡한데 그 결정을 선언한 칸이 없으면 **여전히 해당 없음**(과잉 적용 금지 · §7.5 급)
from __future__ import annotations

import json
from datetime import date

import pytest

from grid import schema as grid_schema
from ingest import dropped
from judge import harvest_timing as H
from judge import material_citation as MC
from judge import plan_vs_actual as PVA
from judge import risk_alert as A
from judge import stage_decisions as SD
from judge import units

TODAY = date(2026, 9, 19)
BASE = {"id": "t-unit", "anchor": "2026-08-25", "cert": "유기"}

# 봉투를 내는 다섯 진입점. 하나가 늘면 여기 한 줄 — 그때 그 결정도 같은 약속을 지키는지 함께 재진다.
CALLS = [
    ("harvest_timing", lambda s: H.judge(s, today=TODAY)),
    ("risk_alert", lambda s: A.judge(s, today=TODAY)),
    ("plan_vs_actual", lambda s: PVA.judge(s, today=TODAY)),
    ("material_citation", lambda s: MC.judge(s, today=TODAY)),
    ("stage_decisions", lambda s: SD.judge_replant(s, TODAY, observations=[])),
]


@pytest.fixture
def grid_dir(tmp_path, monkeypatch):
    """격자 폴더를 tmp 로 — 운영 `data/grid/` 에 깨진 파일을 쓰지 않는다(R-4: 쓰기 통로가 생기는 순간이 격리를 넣을 순간)."""
    monkeypatch.setattr(grid_schema, "GRID_DIR", tmp_path)
    dropped.clear()
    return tmp_path


def _subject(grid_dir, state: str) -> dict:
    if state == "unlinked":
        return dict(BASE)                                        # grid_unit 자체가 없다
    if state == "no_file":
        return {**BASE, "grid_unit": "ghost-unit"}               # 가리키는데 파일이 없다
    (grid_dir / "broken_unit.json").write_text("{ 이건 JSON 이 아니다", encoding="utf-8")
    return {**BASE, "grid_unit": "broken-unit"}                  # 있는데 못 읽는다


@pytest.mark.parametrize("state", ["unlinked", "no_file", "unreadable"])
@pytest.mark.parametrize("name, call", CALLS, ids=[c[0] for c in CALLS])
def test_a_grid_we_could_not_read_is_never_not_applicable(name, call, state, grid_dir):
    """① — 다섯 진입점 어디서도 '해당 없음' 이 나오지 않는다. 종류는 정본 표가 정한다."""
    env = call(_subject(grid_dir, state))
    assert env.kind != "해당 없음", f"{name}/{state}: 화면이 '할 일이 아니었다' 고 단정한다"
    assert env.kind == units.MISS_KIND[state]
    assert env.result["grid_unit_miss"] == state


@pytest.mark.parametrize("state, fillable", [("unlinked", False), ("no_file", False), ("unreadable", True)])
def test_only_the_file_that_exists_can_be_pointed_at_for_filling(state, fillable, grid_dir):
    """② — `missing` 은 판단 불가(데이터)에서만 채운다(봉투가 강제한다). 무엇을 고치면 되는지도 함께 말한다."""
    env = H.judge(_subject(grid_dir, state), today=TODAY)
    assert bool(env.missing) is fillable
    if fillable:
        assert env.missing[0]["axis"] == "격자 정본"
        assert "broken_unit.json" in env.missing[0]["who_can_fill"], "고칠 파일을 안 짚어 주면 고치러 갈 데가 없다"


def test_the_three_reasons_do_not_say_the_same_thing(grid_dir):
    """③ — 종류만 가르고 **사람이 보는 문장**을 안 가르면 표현 층에서 도로 뭉개진다(G1 세 번째 형태)."""
    said = {s: H.judge(_subject(grid_dir, s), today=TODAY).result["summary"] for s in ("unlinked", "no_file", "unreadable")}
    assert len(set(said.values())) == 3, said
    assert "ghost-unit" in said["no_file"] and "broken-unit" in said["unreadable"], "어느 격자인지 안 말한다"
    assert "없" in said["unlinked"]


def test_a_grid_we_could_not_read_is_recorded_as_dropped(grid_dir):
    """읽다 버린 것은 `/changes` 가 말한다 — 조용한 실패는 R-6 이 가르쳐 준 가장 나쁜 형태다."""
    H.judge(_subject(grid_dir, "unreadable"), today=TODAY)
    H.judge(_subject(grid_dir, "no_file"), today=TODAY)
    where = [d["where"] for d in dropped.all_drops()]
    assert where.count("격자 단위") == 2, dropped.all_drops()


def test_a_grid_that_simply_does_not_declare_this_decision_is_still_not_applicable(grid_dir):
    """④ 반대편 — 격자가 **멀쩡히** 그 결정을 선언하지 않은 것은 정본의 정직한 산출이다. 여기까지 판단 불가로
    바꾸면 과잉 적용이고, 여덟이 다 '즉시' 가 되어 우선순위가 흐려진다(§7.5 같은 형태 ≠ 같은 급)."""
    (grid_dir / "bare_unit.json").write_text(json.dumps(
        {"unit": {"id": "bare-unit", "crop": "쪽파", "kind": "season"},
         "stages": [{"order": 1, "name": "파종", "decisions": []}]}, ensure_ascii=False), encoding="utf-8")
    env = H.judge({**BASE, "grid_unit": "bare-unit"}, today=TODAY)
    assert env.kind == "해당 없음" and "grid_unit_miss" not in env.result


# ── 배선 ───────────────────────────────────────────────────────────────────────────
def test_the_subject_grid_is_opened_in_exactly_one_place():
    """[§7.5 관문의 입력] 정본을 세워도 **다른 경로가 제 손으로 열면** 같은 결함이 다른 옷을 입고 돌아온다.
    계약은 *"재배 단위의 격자를 열려면 정본을 지난다"* — 파일을 여는 것(`unit_path`)과 그 id 를 읽는 것을
    한 파일에서 함께 하는 곳은 `grid/schema.py` 뿐이다(화면이 id 를 **보여 주기만** 하는 것은 여는 것이 아니다).
    """
    from pathlib import Path
    root = Path(__file__).resolve().parent.parent
    offenders = []
    for p in sorted(root.glob("*/*.py")):
        if p.parts[-2] in ("tests", "venv") or p.as_posix().endswith("grid/schema.py"):
            continue
        src = p.read_text(encoding="utf-8")
        if "grid_unit" in src and "unit_path(" in src:
            offenders.append(p.relative_to(root).as_posix())
    assert offenders == [], f"격자를 제 손으로 여는 자리가 생겼다: {offenders}"


@pytest.mark.parametrize("mod", [H, A, PVA, MC, SD])
def test_every_judge_routes_the_miss_through_the_one_mapper(mod):
    """배선 래칫 — 호출형까지만 본다(인자 표현식·줄 위치는 고정하지 않는다)."""
    src = __import__("pathlib").Path(mod.__file__).read_text(encoding="utf-8")
    assert "load_unit(" in src, f"{mod.__name__} 이 격자를 정본으로 읽지 않는다"
    assert "units.envelope_for(" in src, f"{mod.__name__} 이 사유를 제 손으로 봉투로 만든다 — 문장이 갈린다"


def test_a_new_reason_cannot_quietly_borrow_an_old_kind():
    """사유 갈래가 늘면 종류 표에서 깨진다 — 기본값으로 메우면 새 갈래가 옛 종류를 입는다(대리값 금지)."""
    assert set(units.MISS_KIND) == set(grid_schema.REASONS)
    with pytest.raises(KeyError):
        units.envelope_for(grid_schema.UnitMiss("brand_new", "u", "w", "s"), "d", "s", "now")
