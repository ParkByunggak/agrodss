# -*- coding: utf-8 -*-
# [M-4 · M-9] 격자 스키마 — 거부(I-4 밖 축 · 축 겹침 · 회복 불가인데 경보 약함 · 촬영 칸 없음 · 순서)와
# 통과(쪽파 가을 격자가 검증을 지난다 · 문서 동기 · 회복 불가 칸이 먼저 채워졌다).
from __future__ import annotations

import copy
import sys
from pathlib import Path

import pytest

from grid import schema

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import build_grid_doc as bg  # noqa: E402

JJ = schema.GRID_DIR / "jjokpa_autumn.json"


@pytest.fixture
def unit():
    return schema.load(JJ)


# ── 통과 ──────────────────────────────────────────────────────────────────────
def test_jjokpa_autumn_validates(unit):
    rep = schema.validate(unit)
    assert rep.ok, rep.errors


def test_every_grid_file_is_in_the_one_canonical_form_the_writers_use():
    """[2026-09-30 실측] 한 명령(apply_grid_value)이 값 하나를 넣자 격자 파일 전체가 다른 배치로 다시 써져 수백 줄 diff 가 됐다 — 값이 어디 바뀌었는지가 안 보인다.
    정규 형식은 하나(`schema.dump_text`)이고 파일은 늘 그 형식이어야 한다(손으로 고쳐도 · 스크립트가 써도). 쓰는 스크립트 둘 다 그 함수를 부른다(호출형 래칫)."""
    for p in sorted(schema.GRID_DIR.glob("*.json")):
        text = p.read_text(encoding="utf-8")
        assert text == schema.dump_text(schema.load(p)), f"{p.name}: 정규 형식이 아니다 — python -m scripts.build_grid_doc 전에 schema.dump_text 로 다시 쓴다"
    for rel in ("scripts/apply_grid_value.py", "scripts/prewalk_grid.py"):
        src = (ROOT / rel).read_text(encoding="utf-8")
        assert "schema.dump_text(" in src and "json.dumps(unit" not in src, f"{rel}: 격자를 제 형식으로 쓴다 — 정규 형식 하나를 부른다"
    assert schema.dump_text({"a": [1, 2]}).endswith("\n") and "ensure_ascii" not in schema.dump_text({"k": "한글"})


def test_axes_constant_matches_i4():
    assert len(schema.AXES) == 12 and "humidity_air" not in schema.AXES


def test_unrecoverable_risks_filled_first(unit):
    # M-7 원칙: 회복 불가 위험은 전부 트리거·축·출처가 채워져 있다
    for s in unit["stages"]:
        for r in (s.get("risks") or []) if s.get("risks") != schema.NA else []:
            if r["recoverable"] is False:
                assert r.get("trigger") and r.get("axes") and r.get("source"), r["name"]
                assert r["alert"] == "oversignal_ok"


def test_first_capture_scene_is_current_stage(unit):
    # 오늘(T+24)이 속한 칸은 촬영 칸이다 — I-7 첫 촬영이 격자와 맞물린다
    s = [s for s in unit["stages"] if s["window"]["from_day"] <= 24 <= s["window"]["to_day"]]
    assert s and s[0]["capture"]["shoot"] is True


def test_harvest_stage_answers_harvest_timing_with_range(unit):
    h = [s for s in unit["stages"] if "harvest_timing" in s.get("decisions", [])]
    assert len(h) == 1 and h[0]["judge_without_variety"] == "range"


def test_materials_split_by_cert(unit):
    for s in unit["stages"]:
        for t in (s.get("tasks") or []) if s.get("tasks") != schema.NA else []:
            m = t["materials"]
            assert m == schema.NA or set(m) == {"관행", "유기"}, t["name"]


def test_completeness_counts_three_kinds(unit):
    rep = schema.validate(unit)
    assert rep.filled > 0 and rep.na > 0          # '해당없음' 이 실제로 쓰였다(6단계)
    assert rep.unfilled == 0                        # 칸 필드 수준 미채움은 0 — 미채움은 값 안에 '미채움' 으로 표기됨


def test_doc_in_sync(unit):
    assert bg.build(unit) == (ROOT / "docs" / "grid_jjokpa_autumn.md").read_text(encoding="utf-8")


def test_capture_hint_for_first_subject():
    from datetime import date
    from grid import capture
    from ingest import media
    subj = [s for s in media.load_subjects() if s["id"] == "p001-jjokpa-2026f"][0]
    h = capture.hint_for(subj, date(2026, 9, 18))
    assert h["day"] == 24 and h["stage"].startswith("3.") and h["shoot"] is True and "잎" in h["scene"]
    assert capture.hint_for(subj, date(2027, 1, 1))["stage"] is None      # 창 밖 — 단정하지 않는다
    assert capture.hint_for({"id": "x"}, date(2026, 9, 18)) is None        # 격자·기준점 없음


# ── 거부 ──────────────────────────────────────────────────────────────────────
def _mut(unit, fn):
    u = copy.deepcopy(unit)
    fn(u)
    return schema.validate(u)


def test_reject_axis_outside_i4(unit):
    rep = _mut(unit, lambda u: u["stages"][0]["required_axes"].append("moon_phase"))
    assert any("I-4 밖" in e for e in rep.errors)


def test_reject_forbidden_only_axis_as_required(unit):
    rep = _mut(unit, lambda u: u["stages"][0]["required_axes"].append("humidity_air"))
    assert not rep.ok


def test_reject_required_forbidden_overlap(unit):
    rep = _mut(unit, lambda u: u["stages"][0]["forbidden_axes"].append("temp"))
    assert any("겹친다" in e for e in rep.errors)


def test_reject_unrecoverable_with_weak_alert(unit):
    def f(u):
        u["stages"][0]["risks"][0]["alert"] = "confident_only"
    rep = _mut(unit, f)
    assert any("경보 비대칭" in e for e in rep.errors)


def test_reject_no_capture_cell(unit):
    def f(u):
        for s in u["stages"]:
            s["capture"] = {"shoot": False, "scene": ""}
    rep = _mut(unit, f)
    assert any("촬영 시점 칸" in e for e in rep.errors)


def test_reject_bad_order(unit):
    rep = _mut(unit, lambda u: u["stages"][1].__setitem__("order", 5))
    assert any("order" in e for e in rep.errors)


def test_reject_non_canonical_crop(unit):
    rep = _mut(unit, lambda u: u["unit"].__setitem__("crop", "취나물"))   # 이명 — 정본은 참취
    assert any("정본명" in e for e in rep.errors)


def test_reject_no_judgment_without_traits(unit):
    def f(u):
        u["stages"][4]["judge_without_variety"] = "no"   # variety_dependence 는 time_only
    rep = _mut(unit, f)
    assert any("traits" in e for e in rep.errors)


def test_reject_parcel_correction_without_pest_axis(unit):
    def f(u):
        u["stages"][0]["risks"][0]["parcel_correction"] = True   # axes: anchor/temp/forecast
    rep = _mut(unit, f)
    assert any("parcel_correction" in e for e in rep.errors)


# ── [D-18 미리 걷기 2026-09-27] symptom_rules — 발행자가 넣을 키의 형태를 검증기가 보고, 문서 생성기가 싣는다 ──────────────────────
# 규칙을 넣은 워크트리에서 재니: 검증기는 형태를 안 봤고(문자열 symptoms 가 글자 단위로 매칭될 형태), 생성 문서는 그 표를 안 실었다(G1).
def _rules():
    from tests.test_symptom_triage import RULES     # 발행자 감별 넷의 형식 예 — 한 벌만 둔다
    return copy.deepcopy(RULES)


def test_symptom_rules_pass_validation_and_render_in_the_doc(unit):
    u = copy.deepcopy(unit)
    u["stages"][2][schema.SYMPTOM_RULES_KEY] = _rules()
    rep = schema.validate(u)
    assert rep.ok, rep.errors
    doc = bg.build(u)
    assert "| 증상 말 | 원인 후보 | 가르는 확인 | 회복 | 먼저 할 확인 |" in doc
    for c in _rules()[0]["causes"]:
        assert c["name"] in doc and c["check"] in doc
    assert _rules()[0]["first_check"] in doc and "**불가**" in doc and "노랗 · 노란 · 누렇" in doc
    assert schema.SYMPTOM_RULES_KEY == "symptom_rules"                              # 판정기 등록부가 같은 이름을 쓴다(정본 하나)
    # `is` 비교는 리터럴 인터닝 때문에 두 벌이어도 통과한다(주입 실측 2026-09-27 — 미적발) → 소스로 본다: 판정기는 스키마의 이름을 **가져온다**
    sd_src = (ROOT / "judge" / "stage_decisions.py").read_text(encoding="utf-8")
    assert "SYMPTOM_RULES_KEY = grid_schema.SYMPTOM_RULES_KEY" in sd_src and '"symptom_rules"' not in sd_src


@pytest.mark.parametrize("mutate, word", [
    (lambda r: r[0].__setitem__("symptoms", "노랗"), "목록"),                                  # 문자열 하나 — 글자 단위 매칭
    (lambda r: r[0].__setitem__("symptoms", []), "목록"),
    (lambda r: r[0]["causes"][0].__setitem__("recoverable", "false"), "recoverable"),        # A5 형태
    (lambda r: r[0].__setitem__("causes", []), "causes"),
    (lambda r: r[0]["causes"].append({"check": "이름 없음"}), "name"),
    (lambda r: r[0].__setitem__("first_check", 3), "first_check"),
    (lambda r: r.append("문자열 규칙"), "dict"),
    (lambda r: r.clear(), "목록"),
])
def test_reject_malformed_symptom_rules(unit, mutate, word):
    u = copy.deepcopy(unit)
    rules = _rules()
    mutate(rules)
    u["stages"][2][schema.SYMPTOM_RULES_KEY] = rules
    rep = schema.validate(u)
    assert not rep.ok and any(word in e and "symptom_rules" in e for e in rep.errors), rep.errors
