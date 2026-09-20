# -*- coding: utf-8 -*-
# [칸 3 재측정 · 2026-09-20 / 코드 평가 A13 · D13] 중복 진실 — 같은 사실이 두 곳에 적혀 있다.
#   넷을 쟀다: 피해 종류 · 수확 허용 오차 키 · 격자 파일명 규칙 · 결정 라벨 사전.
#   셋은 글자가 같았고(아직 안 어긋남 — 칸 2), **하나는 이미 어긋나 있었다**: `/judge` 의 인라인 사전이 정본을
#   가리면서 "자재 인용(유기 공시)" 를 내고 있었는데, PSIS(관행 등록약제)가 붙은 뒤로 그 이름은 틀린 말이다.
#   중복은 어긋나기 전까지 조용하다 — 그래서 래칫이 처방이다(어긋나는 날을 검사가 잡는다).
from __future__ import annotations

import re
from pathlib import Path

from grid import capture, schema as grid_schema
from ingest import events as ev
from judge import evolve, harvest_timing

ROOT = Path(__file__).resolve().parent.parent


def _code(path: Path) -> str:
    src = re.sub(r'\"{3}.*?\"{3}', "", path.read_text(encoding="utf-8"), flags=re.S)   # 독스트링이 옛 꼴을 설명한다(§7.1 4번)
    return "\n".join(ln.split("#", 1)[0] for ln in src.splitlines())


# ── 값이 한 벌인가(같은 것을 가리키는가) ──────────────────────────────────────────
def test_damage_type_and_tolerance_key_come_from_one_place():
    assert evolve.DAMAGE_TYPE == ev.DAMAGE_TYPE
    assert evolve.HARVEST_TOLERANCE_DAYS_KEY == harvest_timing.TOLERANCE_DAYS_KEY


def test_no_module_redefines_those_values_as_a_literal():
    for rel, name, lit in (("judge/evolve.py", "DAMAGE_TYPE", '"피해"'),
                           ("judge/evolve.py", "HARVEST_TOLERANCE_DAYS_KEY", '"error_days"')):
        code = _code(ROOT / rel)
        assert not re.search(rf"^{name}\s*=\s*{re.escape(lit)}", code, re.M), f"{rel}: {name} 를 다시 적었다 — 가져온다"


def test_harvest_payload_uses_the_key_constant_not_a_literal():
    body = _code(ROOT / "judge" / "harvest_timing.py")
    body = body[body.index("def judge("):]
    assert '"error_days"' not in body, "수확 봉투가 키를 리터럴로 싣는다 — 상수로"
    assert "TOLERANCE_DAYS_KEY" in body


# ── 격자 파일명 규칙은 한 곳 ──────────────────────────────────────────────────────
def test_grid_filename_rule_lives_in_one_function():
    assert grid_schema.unit_path("p001-jjokpa-2026f").name == "p001_jjokpa_2026f.json"
    for py in list((ROOT / "judge").glob("*.py")) + list((ROOT / "grid").glob("*.py")) + list((ROOT / "scripts").glob("*.py")):
        code = _code(py)
        hit = re.search(r"replace\(\s*['\"]-['\"]\s*,\s*['\"]_['\"]\s*\)", code)
        if py.name == "schema.py":
            assert hit, "정본 자리에 규칙이 없다"
        else:
            assert not hit, f"{py.name}: 격자 파일명 규칙을 따로 적었다 — schema.unit_path() 로"


def test_the_real_grid_resolves_through_the_canon():
    # 통과편 — 규칙을 모았다고 격자를 못 찾으면 안 된다(막는 것을 검사하면 통과하는 것도 검사한다)
    assert grid_schema.unit_path("jjokpa-autumn").exists() or grid_schema.unit_path("jjokpa_autumn").exists()
    got = capture.stages_open(grid_schema.load(grid_schema.GRID_DIR / "jjokpa_autumn.json"), 20)
    assert got, "격자를 읽어 오늘 칸이 나와야 한다"


# ── 결정 라벨은 정본 하나 ─────────────────────────────────────────────────────────
def test_judge_screen_uses_the_shared_label_dictionary():
    code = _code(ROOT / "frontend" / "serve.py")
    blk = code[code.index("def judge_page"):]
    blk = blk[:blk.index("\ndef ", 10)]
    assert "chat_pages.DECISION_LABEL" in blk
    assert '"harvest_timing":' not in blk, "인라인 라벨 사전이 정본을 가린다(정본 역전)"


def test_mic_tooltip_reads_the_setting_not_a_baked_in_number(monkeypatch):
    """[D15] 설정값이 화면 문구에 **두 벌**이면 설정을 바꿨을 때 화면이 거짓말을 한다 — 같은 계열(중복 진실)."""
    from datetime import date
    from frontend import chat_pages, config
    from ingest import media
    subj = [s for s in media.load_subjects() if s["id"] == "p001-jjokpa-2026f"][0]
    monkeypatch.setattr(config, "VOICE_SILENCE_MS", 3000)
    html = chat_pages.thread_main(subj, date(2026, 9, 19))
    mic = html[html.index('id="mic"'):html.index('id="mic"') + 200]
    assert "3초" in mic and "5초" not in mic, mic


def test_material_citation_label_is_not_the_pre_psis_name():
    from frontend import chat_pages
    label = chat_pages.DECISION_LABEL["material_citation"]
    assert "유기 공시" not in label, "PSIS(관행 등록약제) 뒤로 '유기 공시'는 틀린 이름이다"
