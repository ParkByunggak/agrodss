# -*- coding: utf-8 -*-
# [사유 문면 전수 2026-09-29 — 발행자 "'칸이 기간이 아닙니다' 는 농가에게 하는 말이 아니다"(SURF-1 내부 표현 노출)] 처방 직후 같은 형태를 세니 3층 요약 아홉 곳이
# 더 있었다 — "창 밖" · "창 지남" · "미채움" · "칸 2 retry" · "(D-8)" · "(M-15)" · "격자 칸 1" · "정본 대기". 요약(summary)은 채팅 카드가 그대로 읽는 줄이라
# 사람 말이어야 하고, 정확한 사유는 why 에 남긴다. 여기서 ① 소스의 요약 리터럴에 안쪽 말이 없는지(범위를 "summary": 줄로 자른다 — why 는 대상 밖) ② 실제
# 격자에서 나오는 요약 몇 개가 사람이 읽을 문장인지 본다.
from __future__ import annotations

import re
from datetime import date
from pathlib import Path

from frontend import words
from ingest import chat, media
from judge import material_citation, stage_decisions as SD

ROOT = Path(__file__).resolve().parent.parent
INSIDER = ("창 밖", "창 지남", "미채움", "retry", "D-8", "M-15", "정본", "격자", "horizon", "칸이 ", "기준점", "미도착", "갈래", "**")


def _summary_literals(path: Path) -> list[tuple[int, str]]:
    """`"summary":` 뒤의 **값 식만** — 괄호 깊이를 세어 그 항목이 끝나는 자리(깊이 0 의 `,` 뒤에 다음 키 · `notes=` · 닫는 괄호)까지.
    한 줄만 보면 `+` 로 이어지는 요약(웃거름)의 뒤 조각을 놓치고(실측: '양은 정본 대기' 가 둘째 줄), 네 줄을 보면 옆의 why 가 걸린다(§7.1 4번).
    주석은 건너뛴다(처방 주석에 원 결함 문면이 남아 있다 — 검사 문자열 겹침)."""
    src = path.read_text(encoding="utf-8")
    out, i, key = [], 0, '"summary":'
    while True:
        i = src.find(key, i)
        if i < 0:
            return out
        j, depth, buf = i + len(key), 0, []
        while j < len(src):
            c = src[j]
            if c == "#":                                                   # 주석 — 줄 끝까지 대상 밖
                e = src.find("\n", j)
                j = len(src) if e < 0 else e
                continue
            if c in "([{":
                depth += 1
            elif c in ")]}":
                if depth == 0:
                    break
                depth -= 1
            elif c == "," and depth == 0:
                k = j + 1
                while k < len(src) and src[k] in " \t\n":
                    k += 1
                if k < len(src) and (src[k] == '"' or src.startswith("notes=", k)):
                    break
            buf.append(c)
            j += 1
        out.append((src[:i].count("\n") + 1, "".join(buf).strip()))
        i = j


def test_no_summary_literal_in_layer_three_speaks_judge_words():
    found = []
    for py in sorted((ROOT / "judge").glob("*.py")):
        for i, lit in _summary_literals(py):
            for w in INSIDER:
                if w in lit:
                    found.append(f"{py.name}:{i} {w!r} in {lit}")
    assert found == [], "\n".join(found)
    assert sum(len(_summary_literals(p)) for p in (ROOT / "judge").glob("*.py")) >= 25            # 범위가 살아 있다(리터럴을 못 찾으면 검사가 공허하다)


def _subject():
    return media.load_subjects()[0]


def test_real_grid_summaries_read_as_sentences_for_the_farmer():
    s = _subject()
    day35 = date(2026, 9, 29)                                                                     # 기준점 08-25 + 35
    envs = {e.decision_id: e for e in SD.judge_all(s, day35)}
    rp = envs["replant"]
    assert rp.kind == "해당 없음" and rp.result["summary"] == "보식할 때가 아닙니다 — 보식은 파종 뒤 1~14일, 오늘은 35일째", rp.result
    sw = envs["sowing_window"]
    assert sw.kind == "해당 없음" and sw.result["summary"].startswith("이미 심었습니다 — 심은 날 2026-08-25, 오늘 35일째")
    bf = envs["base_fertilization"]
    assert bf.kind == "해당 없음" and bf.result["summary"].startswith("밑거름 때(파종 뒤 ") and "웃거름으로 봅니다" in bf.result["summary"]
    so = envs["ship_or_store"]
    assert so.kind == "판단 불가(데이터)" and so.result["summary"].startswith("납품 계획일이 없습니다")            # 실제 등록부는 납품 계획일이 없다
    so2 = SD.judge_ship_or_store(dict(s, use="자가 소비"), day35, targets=[], harvest=None)
    assert so2.kind == "해당 없음" and so2.result["summary"] == "이번 작기는 자가 소비 용도라 출하·저장 판단이 없습니다"
    for e in envs.values():                                                                       # 카드 줄에 안쪽 말이 없다 — 낱말 표를 거친 뒤 뜻 없는 말("기간이 아닙니다")도 없다
        line = chat.summarize_envelope(e)
        for bad in ("기간이 아닙니다", "기간이 지났습니다 —", "미채움", "retry", "D-8", "M-15", "정본", "horizon"):
            assert bad not in line, (e.decision_id, bad, line)


def test_the_no_outlook_reason_says_the_forecast_exists_but_has_no_api():
    """[발행자 2026-09-29 "기상청에 장기예보가 없다는 것인가?"] 아니다 — 1·3개월 전망은 발표되지만 자동으로 받는 길(오픈 API)이 없다(VELA 실측 2026-08-05 인용).
    옛 문장("등재된 장기 전망 없음 — … 넣는다")은 기상청에 없다는 뜻으로 읽혔다."""
    from judge import run as judge_run
    recs, why = judge_run.gather_outlook(date(2026, 9, 29))                                       # 격리 환경 — 등재 0
    assert recs is None and why.startswith("등재된 장기 전망 없음") and "발표되지만" in why and "오픈 API" in why and "설정 → 장기 전망 등재" in why


def test_the_missing_cert_rule_summary_is_plain():
    e = material_citation.judge(dict(_subject(), cert="무농약"), today=date(2026, 9, 29))
    assert e.kind == "판단 불가(지식)" and e.result["summary"] == "무농약 의 자재 기준이 아직 없습니다 — 지금은 유기 · 관행만 있습니다"
    assert "정본" in e.result["why"] or "규칙" in e.result["why"]                                   # 정확한 사유는 why 에 그대로
    assert "정본" not in words.plain(e.result["summary"])
