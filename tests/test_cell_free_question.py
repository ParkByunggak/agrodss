# -*- coding: utf-8 -*-
# [발행자 2026-09-29 "답이 틀렸습니다 — 앞서 나온 것과 같은 계열"] "지금 어떤 병충해를 봐야 하나" 가 칸 3 에 묶인 pest_alert 로 가서 「이번엔 할 일이 아닙니다 —
# 칸이 기간이 아닙니다」 가 나갔다(파종 33일째 = 칸 4). 둘이다: ① 안쪽 사유("칸이 창 밖")가 낱말 표를 거쳐 뜻 없는 말이 됐다(SURF-1) ② 칸을 특정하지 않은
# 물음이 칸에 묶인 결정으로 갔다 — 라우팅이 물음의 범위를 못 읽었다(증상 물음이 계획표로 가던 U-32 와 같은 축). 그 자리는 risk_alert(오늘 칸 + 7일 안 시작 칸 전부).
from __future__ import annotations

import re
from datetime import date

from frontend import words
from ingest import chat, media
from judge import run as judge_run
from judge import stage_decisions as SD

DAY35 = date(2026, 9, 29)        # 기준점 2026-08-25 + 35일 — 칸 4(30~50일). 발행자 붙임의 33일째와 같은 칸


def _subject():
    return media.load_subjects()[0]


def test_a_pest_question_names_no_cell_so_it_goes_to_the_risk_alert_not_a_cell_card():
    for q in ("지금 어떤 병충해를 봐야 하나", "벌레 걱정되는데 괜찮나?", "병이 온 것 같은데 약 있나", "진딧물 방제 뭘로 하나요", "나방이 보이는데", "파리가 날아다닌다 괜찮나"):
        assert chat.topic_of(q) == "risk_alert", q
    assert not any(did == "pest_alert" for did, _ in chat.TOPIC)                                # 칸 3 카드는 채팅 어휘를 갖지 않는다
    assert chat.topic_of("고랑이 과습인데") == "drainage_alert" and chat.topic_of("과습이 걱정된다") == "risk_alert"   # 배수 어휘(고랑·물 빠짐)는 칸 4 카드 그대로 — 발행자 ② 는 병·벌레만


def test_with_the_real_grid_on_day_35_the_answer_lists_the_open_cells_risks():
    s = _subject()                                                                                # 격리 환경 — 좌표·키가 없어 원천은 이유만 돌아온다(달력 경보만)
    a = chat.answer(s, "지금 어떤 병충해를 봐야 하나", DAY35)
    assert a.startswith(f"[{words.said('판단함')}]"), a
    assert "주의 과습" in a and "지켜볼 것: 녹병" in a and "4. 생육 중기" in a                    # 오늘 칸(4)의 위험 둘 — 회복 불가는 주의, 회복 가능은 이름만(신호 없음)
    assert "고자리파리" not in a                                                                  # 칸 3 은 닫혔다(35일) — 그 위험은 이 칸의 것이 아니다(등재 후보: 예찰 마감을 넘긴 위험의 잔류)
    assert "칸이 기간이 아닙니다" not in a and "창 밖" not in a and "horizon" not in a


def test_watch_names_only_the_open_cells_recoverable_risks_not_a_cell_that_has_not_opened():
    """주입 J 가 처음엔 통과 — 35일째엔 보는 칸이 4 하나라 '닫힌 칸' 갈래가 안 걸렸다. 45일째는 칸 5(50일~)가 7일 안이라 범위엔 들지만 아직 안 열렸다:
    그 칸의 회복 가능 위험은 지켜볼 것에 안 들어간다(예고는 회복 불가 위험만 달력으로)."""
    from judge import risk_alert as A
    s = _subject()
    r = A.judge(s, today=date(2026, 8, 30)).result                                             # 기준점 08-25 + 5일 — 칸 2 열림 · 칸 3(10일~)은 7일 안이라 범위엔 들지만 안 열렸다
    assert r["stages"] == ["2. 발아 · 출현", "3. 생육 초기 (잎 2~4매)"] and r["days_since_anchor"] == 5
    assert [w["risk"] for w in r["watch"]] == ["결주(출현 불량)"] and all(w["stage"].startswith("2.") for w in r["watch"]), r["watch"]   # 칸 3 의 회복 가능 위험(총채벌레 · 노균병)은 아직 아니다
    assert any(a["stage"].startswith("3.") and a["level"] == "예고" for a in r["alerts"])       # 칸 3 의 회복 불가 위험(고자리파리)은 예고로 — 그건 경보 규칙 그대로
    r45 = A.judge(s, today=date(2026, 10, 9)).result                                           # 45일째(칸 4 열림 · 칸 5 범위) — 칸 5 엔 회복 가능 위험이 없어 지켜볼 것은 칸 4 뿐
    assert r45["stages"] == ["4. 생육 중기 · 비대", "5. 수확"] and all(w["stage"].startswith("4.") for w in r45["watch"])


def test_the_cell_card_out_of_its_window_speaks_to_the_farmer_not_in_judge_words(monkeypatch):
    s = _subject()
    e = SD.judge_pest_alert(s, DAY35) if hasattr(SD, "judge_pest_alert") else next(x for x in SD.judge_all(s, DAY35) if x.decision_id == "pest_alert")
    assert e.kind == "해당 없음"
    summ = words.plain(e.result["summary"])
    assert "3. 생육 초기" in summ and "35일째" in summ and "4. 생육 중기" in summ and "위험 경보" in summ, summ
    for bad in ("창 밖", "horizon", "기간이 아닙니다", "칸이 "):
        assert bad not in summ, (bad, summ)
    assert "horizon 밖" in e.result["why"]                                                     # 정확한 사유는 why 에 남는다
    line = chat.summarize_envelope(e)
    assert line.startswith(f"[{words.said('해당 없음')}]") and "기간이 아닙니다" not in line


def test_day_30_is_a_boundary_day_and_both_cells_are_open_in_the_one_canon():
    """B4 — 30일은 칸 3(10~30)과 칸 4(30~50) 양쪽에 속한다. 판정기마다 창을 따로 비교하지 않고 `grid.capture.is_open` 하나를 쓴다(risk_alert 가 그렇다)."""
    from grid import capture, schema as gs
    unit, miss = gs.load_unit(_subject())
    assert miss is None
    assert [x["order"] for x in capture.stages_open(unit, 30)] == [3, 4] and [x["order"] for x in capture.stages_open(unit, 35)] == [4]
    src = open(SD.__file__, encoding="utf-8").read()
    assert not re.search(r"from_day\"\]\s*<=\s*day", src), "판정기가 창을 따로 비교한다 — 정본은 grid.capture.is_open"
