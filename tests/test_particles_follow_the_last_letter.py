# -*- coding: utf-8 -*-
# [전수 2026-10-06] 사람에게 보이는 문장이 조사를 **손으로** 적어 어긋난 자리들 — 값이 들어오는 자리라 **고정 조사는 반드시 언젠가 틀린다**:
#     「칸 '수확' 가 7일 뒤 열린다」(받침 ㄱ → 이)  「배수 나쁨 는 …」(은)  「인증 유형 '유기' 은 …」(는)
#     「오늘이 2026-10-06 로 고정돼 있다」(육 → 으로)  「'수확 시기' 은 검토 전 추론」(는)  「어휘 '무농약' 를 읽었다」(을)
# 안쪽 낱말 표가 「재배 달력가」 를 고친 그 축의 **템플릿 판**이다. 처방은 받침으로 고르는 정본 하나(`schema.records.josa`).
#
# 이 검사가 고정하는 것 넷:
#   ① 정본이 받침으로 고른다 — 한글 · 숫자(읽는 소리) · 따옴표로 끝나는 말 · ㄹ 받침의 「로」 · 모르는 짝은 거부(양방향)
#   ② **배선** — 고친 자리들이 실제로 그 말을 낸다(함수가 아니라 산출을 본다: 판정 메모 · 요구 줄 · 화면 꼬리말)
#   ③ **전수** — 고친 파일에서 **값이 들어오는 자리**(소문자 식·첨자·호출) 뒤에 손으로 적은 조사가 남아 있지 않다
#   ④ 그 전수가 통과시키는 **고정 낱말 자리**(ALL_CAPS 상수)는 그 상수의 받침으로도 맞다 — 통과 사유가 사실인지 되묻는다
from __future__ import annotations

import ast
import importlib
import re
from pathlib import Path

import pytest

from schema import records as sch

ROOT = Path(sch.__file__).resolve().parent.parent
FIXED = ("judge/risk_alert.py", "judge/stage_decisions.py", "judge/material_citation.py", "judge/plan_vs_actual.py",
         "frontend/serve.py", "frontend/words.py", "ingest/chat.py")
PARTICLES = ("으로", "이", "가", "은", "는", "을", "를", "와", "과", "로")      # 「으로」 가 먼저(긴 것부터)
AFTER = " ,.·」』)!?\n"                                                        # 조사 뒤에 올 수 있는 것 — 「은행」 같은 낱말을 조사로 읽지 않게


def test_the_canon_picks_by_the_last_letter():
    for word, want in (("수확", "이"), ("비대", "가"), ("나쁨", "은"), ("유기", "는"), ("무농약", "을"), ("관행", "은")):
        pair = {"이": "가", "가": "이", "은": "는", "는": "은", "을": "를", "를": "을"}[want]
        assert sch.josa(word, want) == want and sch.josa(word, pair) == want, (word, want)
    assert sch.josa("'유기'", "은") == "는" and sch.josa("칸 '수확'", "가") == "이"      # 따옴표로 끝나도 **마지막 한글**을 본다
    assert sch.josa("2026-10-06", "로") == "으로" and sch.josa("2026-10-05", "로") == "로"      # 영 ㅇ · 오 없음
    assert sch.josa("2026-10-07", "로") == "로" and sch.josa("종구", "로") == "로"                # ㄹ 받침은 「로」
    assert sch.josa("10일", "로") == "로" and sch.josa("3", "이") == "이"                        # 숫자는 읽는 소리(일 ㄹ · 삼 ㅁ)
    assert sch.josa("ABC", "가") == "가" and sch.josa("", "은") == "는" and sch.josa(None, "을") == "를"      # 한글·숫자가 없으면 받침 없음 쪽(적어 둔 한계)
    with pytest.raises(ValueError):
        sch.josa("수확", "에서")


def test_the_screens_and_judgments_actually_say_it(tmp_path, monkeypatch):
    """배선 — 함수가 아니라 **산출**을 본다."""
    from frontend import words
    assert "값 '유기' 를 읽습니다" in words.opened("cert", "유기")
    assert "값 '무농약' 을 읽습니다" in words.opened("cert", "무농약")
    assert words.fix_offer(["수확 시기"]).startswith("「수확 시기」 는")
    assert words.fix_offer(["저장 한계일"]).startswith("「저장 한계일」 은")

    import json
    import shutil
    doc = json.loads((ROOT / "data" / "parcels_seed.json").read_text(encoding="utf-8"))
    rows = doc["parcels"] if isinstance(doc, dict) and "parcels" in doc else doc
    rows[0]["drainage"] = "나쁨"
    p = tmp_path / "parcels.json"
    p.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
    shutil.copy(ROOT / "data" / "subjects.json", tmp_path / "subjects.json")
    for k, v in (("AGRODSS_PARCELS_PATH", p), ("AGRODSS_PARCELS_LOCAL_PATH", p), ("AGRODSS_PARCELS_LEGACY_PATH", tmp_path / "none.json"),
                 ("AGRODSS_SUBJECTS_PATH", tmp_path / "subjects.json"), ("AGRODSS_SUBJECTS_LOCAL_PATH", tmp_path / "subjects_local.json")):
        monkeypatch.setenv(k, str(v))
    from datetime import date
    from judge import run as judge_run
    env = next(e for e in judge_run.judgments_for("p001-jjokpa-2026f", today=date(2026, 10, 7)) if e.decision_id == "risk_alert")
    notes = " ".join(str(n) for n in (env.notes or []))
    assert "배수 나쁨 은" in notes, notes[:200]                                   # 「나쁨 는」 이던 자리
    basis = " ".join(str(a.get("basis") or "") for a in (env.result or {}).get("alerts") or [])
    assert "칸 '수확' 이" in basis, basis[:200]                                   # 「'수확' 가」 이던 자리


def _particle_after(const: str) -> str | None:
    s = const.lstrip("'\"」』) ")
    for p in PARTICLES:
        if s.startswith(p) and (len(s) == len(p) or s[len(p)] in AFTER):
            return p
    return None


def _is_fixed_word(node: ast.AST) -> str | None:
    """값이 아니라 **고정 낱말**인가 — 모듈 상수(ALL_CAPS)면 그 이름을 돌려준다."""
    if isinstance(node, ast.Name) and node.id.isupper():
        return node.id
    if isinstance(node, ast.Attribute) and node.attr.isupper():
        return node.attr
    if isinstance(node, ast.Subscript) and isinstance(node.value, (ast.Name, ast.Attribute)):
        base = node.value.id if isinstance(node.value, ast.Name) else node.value.attr
        return base if base.isupper() else None
    if isinstance(node, ast.Call):                                   # confirm_label(d["kind"]) 처럼 **고정 낱말 표**를 부르는 꼴
        f = node.func
        name = f.id if isinstance(f, ast.Name) else (f.attr if isinstance(f, ast.Attribute) else "")
        return name if name in ("confirm_label", "label") else None
    return None


def _sites() -> tuple[list[tuple[str, int, str]], list[tuple[str, int, str, str]]]:
    """(값 자리에 손으로 적은 조사, 고정 낱말 자리) — f-string 의 placeholder 바로 뒤를 본다."""
    variable, fixed = [], []
    for rel in FIXED:
        tree = ast.parse((ROOT / rel).read_text(encoding="utf-8"))
        for js in [n for n in ast.walk(tree) if isinstance(n, ast.JoinedStr)]:
            for i, part in enumerate(js.values[:-1]):
                nxt = js.values[i + 1]
                if not (isinstance(part, ast.FormattedValue) and isinstance(nxt, ast.Constant) and isinstance(nxt.value, str)):
                    continue
                p = _particle_after(nxt.value)
                if not p:
                    continue
                const = _is_fixed_word(part.value)
                (fixed if const else variable).append((rel, part.lineno, const or ast.unparse(part.value), p) if const else (rel, part.lineno, ast.unparse(part.value)))
    return variable, fixed


def test_no_value_site_still_types_its_own_particle():
    variable, _ = _sites()
    assert variable == [], variable


def test_the_fixed_word_sites_are_right_too():
    """전수가 통과시키는 사유(「그 자리는 고정 낱말이다」)가 **사실인지** 되묻는다 — 고정 낱말에 틀린 조사가 붙어 있으면 여기서 터진다."""
    _, fixed = _sites()
    assert fixed, "고정 낱말 자리가 하나도 없다 — 탐지 축이 좁아졌다(이 트랙에서 세 번 났다)"
    seen = 0
    for rel, line, const, particle in fixed:
        mod = importlib.import_module(rel[:-3].replace("/", "."))
        value = getattr(mod, const, None)
        if isinstance(value, dict):                                  # 표라면 값 전부가 같은 조사를 받아야 한다
            for v in value.values():
                assert sch.josa(v, particle) == particle, (rel, line, const, v, particle, sch.josa(v, particle))
            seen += 1
        elif isinstance(value, str):
            assert sch.josa(value, particle) == particle, (rel, line, const, value, particle, sch.josa(value, particle))
            seen += 1
    assert seen, [f[:3] for f in fixed]                              # 상수를 하나도 못 읽었으면 이 검사는 눈을 감고 있다
