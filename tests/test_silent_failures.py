# -*- coding: utf-8 -*-
# [R-6 후속 전수 2026-09-21] R-6 은 **에러 한 줄 없이 사라지는 실패**였다 — 발행자가 브라우저를 열어야만 알았다.
# 고친 그 자리에서 같은 형태를 전수로 셌다: except 핸들러 83개 중 **조용한 것 24개**.
#
# 급을 갈랐다(§7.5 같은 형태 ≠ 같은 급).
#
#   즉시 — 판독·산출을 오염시킨다(우리가 **제 손으로 쓴 파일**을 못 읽고 없는 것처럼 지나간다)
#     soil_store.latest / prescriptions_for   처방 정본이 있는데 못 읽으면 판정이 "정본 **미도착**" 이라 한다 → 원인이 뒤바뀐다
#     subjects.grid_unit_for                  격자 파일이 깨지면 그 작목은 격자가 없는 것처럼 되고 판정이 통째로 '해당 없음'
#     hook 가드                               입력을 못 읽으면 **통과**시킨다 — 통과가 맞지만 조용하면 가드가 죽은 줄을 모른다
#
#   등재하지 않음 — 다른 급: kma · ncpms · media 의 파싱 실패는 **외부 응답에 값이 없다**는 뜻이고 None 이 그것을
#     정직하게 말한다. 그것까지 실으면 신호가 묻힌다(대장이 붇는 것과 같은 형태).
#
# 처방은 "안 버린다" 가 아니라 **"버린 것을 말한다"** 이다 — 깨진 파일 하나로 화면 전체가 죽는 쪽이 더 나쁘다.
from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path

import pytest

from frontend import serve
from ingest import dropped, soil_store, subjects

ROOT = Path(__file__).resolve().parent.parent


@pytest.fixture(autouse=True)
def _clean_drops():
    dropped.clear()
    yield
    dropped.clear()


def test_a_broken_record_we_wrote_ourselves_is_not_passed_over_in_silence(tmp_path, monkeypatch, capsys):
    """원 결함: 스키마가 안 맞으면 그냥 None — 화면·판정 어디에도 그 사실이 없었다."""
    monkeypatch.setenv("AGRODSS_SOIL_DIR", str(tmp_path))
    bad = tmp_path / soil_store._name("observation.soil_exam", "p001", None)
    bad.write_text(json.dumps({"record": {"kind": "observation.soil_exam", "id": "x"}}), encoding="utf-8")
    assert soil_store.latest("observation.soil_exam", "p001") is None     # 값은 여전히 안 쓴다(깨진 것을 믿지 않는다)
    drops = dropped.all_drops()
    assert len(drops) == 1 and drops[0]["path"] == bad.name               # 그러나 **버린 사실이 남는다**
    assert "SchemaError" in drops[0]["why"] or "Error" in drops[0]["why"]
    assert "읽다 버렸다" in capsys.readouterr().err                        # 콘솔에도 한 번은 닿는다


def test_a_broken_prescription_is_recorded_so_the_cause_is_not_reversed(tmp_path, monkeypatch):
    """처방이 **있는데** 못 읽은 것과 **없는** 것은 다른 사실이다 — 판정은 둘 다 '정본 미도착'으로 보인다."""
    monkeypatch.setenv("AGRODSS_SOIL_DIR", str(tmp_path))
    (tmp_path / "p001_prescription_07027.json").write_text("{ 깨진 json", encoding="utf-8")
    assert soil_store.prescriptions_for("p001") == []
    assert [d["where"] for d in dropped.all_drops()] == ["토양 저장소(처방)"]


def test_a_broken_grid_file_does_not_quietly_become_no_grid_at_all(tmp_path, monkeypatch):
    """격자 파일 하나가 깨지면 그 작목의 판정이 통째로 '해당 없음' 이 된다 — 왜 비는지 알 길이 있어야 한다."""
    monkeypatch.setattr(subjects.grid_schema, "GRID_DIR", tmp_path)
    (tmp_path / "broken.json").write_text("{ 아님", encoding="utf-8")
    assert subjects.grid_unit_for("쪽파", "2026 가을") is None
    assert [d["where"] for d in dropped.all_drops()] == ["격자 파일"]


def test_the_changes_screen_says_what_was_dropped_and_says_so_when_nothing_was(tmp_path, monkeypatch):
    """[소비자를 같은 회차에] 기록만 남기고 읽는 쪽이 없으면 그것이 G1 이다 — 화면이 양쪽 다 말한다."""
    st, body = serve.changes_page()
    assert st == 200 and "읽다 버린 것 없음" in body                       # 없을 때도 말한다(침묵과 구별된다)
    dropped.note("토양 저장소", "p001_prescription_07027.json", "SchemaError: 자리 없는 필드", quiet=True)
    st, body = serve.changes_page()
    assert st == 200 and "읽다 버린 것" in body and "p001_prescription_07027.json" in body and "SchemaError" in body


def test_the_same_drop_is_folded_into_one_line_with_a_count():
    """읽을 때마다 쌓이므로 합치지 않으면 화면이 같은 줄로 덮인다(신호가 묻힌다)."""
    for _ in range(5):
        dropped.note("격자 파일", "broken.json", "JSONDecodeError", quiet=True)
    drops = dropped.all_drops()
    assert len(drops) == 1 and drops[0]["count"] == 5


def test_the_guard_says_when_it_lets_something_through_because_it_could_not_read_it():
    """가드의 fail-open — 통과가 맞지만 조용하면 **가드가 없는 것보다 나쁘다**(있다고 믿기 때문)."""
    r = subprocess.run([sys.executable, "-B", str(ROOT / "scripts" / "hook_block_shell_authoring.py")],
                       input="이건 json 이 아니다", capture_output=True, encoding="utf-8", timeout=30)
    assert r.returncode == 0                                              # 통과시킨다(막으면 어떤 Bash 도 못 돈다)
    assert "가드는 무력하다" in r.stderr, r.stderr                          # 그러나 말한다
