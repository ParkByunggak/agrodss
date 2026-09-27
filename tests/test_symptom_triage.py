# -*- coding: utf-8 -*-
# [D-18 자리 2026-09-27] 증상 → 원인 좁히기 결정을 **지식 없이** 등록한다.
#
# 발행자 2026-09-26: *"농가가 실제로 묻는 것의 상당수가 '이거 왜 이런가'인데 결정 목록은 전부 '언제 무엇을 하는가'다."*
# 2026-09-27: *"어느 단계에 이르러야 질문에 답을 제대로 할 수 있는가?"* — 결정 하나 + 그 결정이 읽을 지식(격자 symptom_rules · 발행자 몫).
# 계약(합성 격자)과 상태(실제 격자)를 가른다(2026-09-21 미리 걷기 전례): 실제 격자는 비어 있어 판단 불가(지식)가 **어디가 비었는지**를
# 말해야 하고, 합성 격자에 규칙이 있으면 후보 + 확인 하나가 나와야 한다. 거부·통과 둘 다 본다.
from __future__ import annotations

import copy
import http.client
import json
from datetime import date
from urllib.parse import quote

from frontend import words
from grid import schema as grid_schema
from ingest import chat, media
from judge import registry, stage_decisions as SD
from tests.test_brand_home import srv  # noqa: F401

TODAY = date(2026, 9, 24)
RULES = [{"symptoms": ["노랗", "노란", "누렇"],
          "causes": [{"name": "양분 부족(웃거름 미이행)", "check": "아래 잎부터 전체적으로 연한가", "recoverable": True},
                     {"name": "과습 · 뿌리 상함", "check": "뽑아서 인경 밑이 물렁한가", "recoverable": False},
                     {"name": "고자리파리 유충", "check": "인경 밑에 구더기 · 냄새", "recoverable": False}],
          "first_check": "증상 있는 포기를 몇 개 뽑아 인경 밑을 본다"}]


def _subject():
    return media.load_subjects()[0]


def test_the_decision_is_registered_and_judged_with_the_others():
    d = registry.get("symptom_triage")
    assert d and d.required_axes == ("anchor",) and "관찰" in d.rule and d.params["rules_key"] == SD.SYMPTOM_RULES_KEY   # 관찰은 축이 아니라 기록
    assert "symptom_triage" in SD.IDS
    envs = SD.judge_all(_subject(), TODAY)
    assert [e.decision_id for e in envs][-1] == "symptom_triage" and len(envs) == len(SD.IDS)


def test_with_the_real_grid_it_says_which_key_of_which_grid_is_empty():
    """상태 — 지금 격자에는 규칙이 없다. 판단 불가(지식)는 '없다' 가 아니라 **어디가 비었는지** 말한다(U-23 문면 규율)."""
    e = SD.judge_symptom_triage(_subject(), TODAY, observations=[{"id": "obs_x", "text": "잎 끝이 노랗다", "observed_at": TODAY.isoformat()}])
    assert e.kind == "판단 불가(지식)"
    assert "jjokpa" in e.result["why"] and SD.SYMPTOM_RULES_KEY in e.result["why"] and "D-18" in e.result["why"] and ".json" in e.result["why"]
    assert e.result["summary"] and "기준" in e.result["summary"]


def _synthetic_grid(tmp_path, monkeypatch):
    unit = copy.deepcopy(grid_schema.load(grid_schema.GRID_DIR / "jjokpa_autumn.json"))
    for s in unit["stages"]:
        if s["order"] == 3:
            s[SD.SYMPTOM_RULES_KEY] = RULES
    (tmp_path / "jjokpa_autumn.json").write_text(json.dumps(unit, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(grid_schema, "GRID_DIR", tmp_path)


def test_with_rules_it_gives_candidates_unrecoverable_first_and_one_check(tmp_path, monkeypatch):
    """계약(합성 격자) — 후보는 좁히기이지 진단이 아니다: 회복 불가 후보가 앞, 확인 하나, 등급 추정, 관찰 id 를 인용."""
    _synthetic_grid(tmp_path, monkeypatch)
    obs = [{"id": "obs_1", "text": "잎 끝이 노랗게 변했어요", "observed_at": TODAY.isoformat()},
           {"id": "obs_old", "text": "잎이 노랗다", "observed_at": "2026-08-01"}]        # 14일 밖 — 안 센다
    e = SD.judge_symptom_triage(_subject(), TODAY, observations=obs)
    assert e.kind == "판단함" and e.grade == "추정"
    names = [c["name"] for c in e.result["candidates"]]
    assert names[:2] == ["과습 · 뿌리 상함", "고자리파리 유충"] and names[-1].startswith("양분")
    assert e.result["first_check"] == RULES[0]["first_check"] and e.result["observations"] == ["obs_1"]
    assert "진단이 아니다" in e.result["summary"] and any("D-18" in n for n in e.notes)


def test_with_rules_but_no_symptom_observation_it_asks_for_one(tmp_path, monkeypatch):
    """반대편 — 규칙이 있어도 관찰이 없으면 판단 불가(데이터): 최종 심급은 농가 관찰이다."""
    _synthetic_grid(tmp_path, monkeypatch)
    e = SD.judge_symptom_triage(_subject(), TODAY, observations=[{"id": "o", "text": "오늘 물 줬다", "observed_at": TODAY.isoformat()}])
    assert e.kind == "판단 불가(데이터)" and e.missing[0]["axis"] == "observation"


def test_the_chat_answer_comes_from_the_envelope_not_a_fixed_sentence(srv):
    """배선 — 채팅의 증상 답은 3층 봉투를 읽는다. 지금(실제 격자)은 판단 불가(지식) 문면이 봉투의 summary 다."""
    s = _subject()
    a = chat.answer(s, "잎 끝이 노란 형상을 어떻게 대처해야 하는가?", TODAY)
    e = SD.judge_symptom_triage(s, TODAY)
    assert a.startswith(f"[{words.said('판단 불가(지식)')}]") and words.plain(e.result["summary"]) in a and "다음 예정" not in a
    # /judge 에 그 카드가 선다 — 결정 이름은 등록부에서 · 왜 비었는지가 화면에
    c = http.client.HTTPConnection("127.0.0.1", srv, timeout=10)
    c.request("GET", "/judge")
    body = c.getresponse().read().decode("utf-8", "replace")
    assert "증상 → 원인 좁히기" in body and SD.SYMPTOM_RULES_KEY in body and "D-18" in body
