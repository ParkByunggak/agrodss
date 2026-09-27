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

import pytest

from frontend import words
from grid import schema as grid_schema
from ingest import chat, events as ev, media
from judge import boundary, registry, run as judge_run, stage_decisions as SD
from schema import records as sch
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


def _synthetic_grid(tmp_path, monkeypatch, rules=RULES):
    unit = copy.deepcopy(grid_schema.load(grid_schema.GRID_DIR / "jjokpa_autumn.json"))
    for s in unit["stages"]:
        if s["order"] == 3:
            s[SD.SYMPTOM_RULES_KEY] = rules
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


# ── [D-18 직렬 게이트 2026-09-27] 규칙(게이트 1) 뒤에 관찰(게이트 2)이 줄지어 있었다 ──────────────────────────────────────
# 자리를 세운 회차의 배선은 저장된 관찰만 읽었다. 발행자가 규칙을 채우는 순간 "잎 끝이 노랗다" 는 물음에 **"관찰이 없다"** 가 나갈
# 형태 — 증상을 말한 그 물음에. 한쪽(규칙)을 열어도 뒤(관찰)가 막으면 증상이 그대로다(CLAUDE.md 직렬 게이트 축). 물으신 말을
# 관찰 레코드로 만들어 같은 경계 게이트를 지나 증상 결정에만 넘긴다. 거부·통과 둘 다: 저장 경로(/judge)는 그대로 저장된 관찰만 본다.
Q = "잎 끝이 노란 형상을 어떻게 대처해야 하는가?"


def test_the_question_itself_opens_the_answer_when_the_rules_exist(tmp_path, monkeypatch):
    """규칙이 있고 **저장된 관찰은 없다** — 채팅의 답은 물으신 말 자체를 관찰로 읽어 후보를 낸다. 저장 경로는 여전히 관찰을 기다린다."""
    _synthetic_grid(tmp_path, monkeypatch)
    s = _subject()
    stored = next(x for x in judge_run.judgments_for(s["id"], today=TODAY) if x.decision_id == "symptom_triage")
    assert stored.kind == "판단 불가(데이터)" and stored.missing[0]["axis"] == "observation"      # 원장에 관찰이 없다 — 저장 경로는 그대로
    a = chat.answer(s, Q, TODAY)
    assert a.startswith(f"[{words.said('판단함')}]") and "과습" in a and "먼저" in a and "진단이 아니" in a, a
    assert "관찰이 없다" not in a and "다음 예정" not in a
    e = next(x for x in judge_run.judgments_for(s["id"], today=TODAY, said=[ev.said_observation(s["id"], Q, TODAY.isoformat())])
             if x.decision_id == "symptom_triage")
    assert e.kind == "판단함" and e.result["observations"] == [ev.SAID_ID]                          # 인용된 관찰은 '물으신 말' 하나
    assert not ev.list_records(s["id"], "observation.note")                                        # 답하느라 원장에 쓰지 않았다


def test_the_said_record_goes_through_the_same_boundary_gate():
    """관문의 입력 — 원장에 없는 입력이라고 게이트를 비켜 가지 않는다. 스키마 밖 레코드를 said 로 넣으면 경계가 거부한다."""
    s = _subject()
    with pytest.raises(boundary.BoundaryError):
        judge_run.judgments_for(s["id"], today=TODAY, said=[{"kind": "settlement", "amount": 1}])
    rec = ev.said_observation(s["id"], Q, TODAY.isoformat())
    assert rec["kind"] == "observation.note" and rec["id"] == ev.SAID_ID and sch.validate(rec)     # 정상 형태는 스키마를 그대로 통과


def test_judge_page_shows_each_candidate_with_its_check(tmp_path, monkeypatch, srv):
    """표현 층 — 판단함 봉투의 후보에는 **가르는 확인**이 붙어 있다. 한 줄 요약만 내면 그 조건이 떨어진다(G1 반대형). /judge 는 표로 낸다."""
    _synthetic_grid(tmp_path, monkeypatch)
    monkeypatch.setenv("AGRODSS_TODAY", TODAY.isoformat())
    s = _subject()
    ev.add_observation(s["id"], "잎 끝이 노랗게 변했어요", TODAY.isoformat())
    c = http.client.HTTPConnection("127.0.0.1", srv, timeout=10)
    c.request("GET", "/judge")
    body = c.getresponse().read().decode("utf-8", "replace")
    assert "가르는 확인" in body and "먼저 할 확인" in body
    for cause in RULES[0]["causes"]:      # 화면은 사람 말 층을 지난다(미이행 → 아직 안 함) — 정본 함수로 옮겨 비교(안 재고 박으면 맞는 고침이 관문을 붉힌다)
        assert words.plain(cause["name"]) in body and words.plain(cause["check"]) in body, cause
    assert body.index("과습 · 뿌리 상함") < body.index("양분 부족")                                    # 회복 불가가 앞
    assert "{'name'" not in body and "candidates" not in body                                       # 안쪽 이름·dict 표기가 새지 않는다


# ── [어휘 한 벌 2026-09-27] 라우팅 목록(chat.SYMPTOM_WORDS)과 격자 규칙 어휘가 두 벌이었다 ────────────────────────────────────────
# 직렬 게이트의 **앞 문**: 발행자가 규칙에 라우팅 목록 밖의 말을 쓰면 규칙은 맞는데 채팅이 증상 물음으로 안 봐서 결정에 닿지 않는다.
# 그리고 관찰에 증상은 있는데 규칙 어휘와 안 맞으면 "관찰이 없다" 로 나갔다 — 농가가 본 것을 부정하는 문면(조건 탈락과 같은 급).
RULES_SYNTH = [{"symptoms": ["하얗", "하얘"], "causes": [{"name": "합성 원인 A", "check": "합성 확인 A", "recoverable": True}], "first_check": "합성 확인 A"}]
Q_SYNTH = "잎 끝이 하얗게 되는데 왜 이런가"


def test_a_rule_word_outside_the_routing_list_still_opens_the_door(tmp_path, monkeypatch):
    assert not any(w in Q_SYNTH for w in chat.SYMPTOM_WORDS)                    # 전제 — 라우팅 목록은 이 말을 모른다(알게 되면 이 검사가 무의미해진다)
    s = _subject()
    assert SD.symptom_words_for(s) == () and chat.grid_symptom_words(s) == () and chat.grid_symptom_words(None) == ()   # 실제 격자: 규칙 없음
    assert [d["kind"] for d in chat.classify(Q_SYNTH, TODAY, subject=s)] == ["question"]                  # 규칙 없으면 정본 목록만 — 관찰 초안 없음
    _synthetic_grid(tmp_path, monkeypatch, RULES_SYNTH)
    assert SD.symptom_words_for(s) == ("하얗", "하얘") and chat.grid_symptom_words(s) == ("하얗", "하얘")
    assert [d["kind"] for d in chat.classify(Q_SYNTH, TODAY, subject=s)] == ["question", "observation.note"]   # 규칙이 아는 말 → 관찰로도
    assert [d["kind"] for d in chat.classify(Q_SYNTH, TODAY)] == ["question"]                             # 재배 단위 없이는 정본 목록만
    a = chat.answer(s, Q_SYNTH, TODAY)
    assert a.startswith(f"[{words.said('판단함')}]") and "합성 원인 A" in a and "다음 예정" not in a, a


def test_a_symptom_the_rules_do_not_know_is_a_knowledge_gap_not_a_missing_observation(tmp_path, monkeypatch):
    _synthetic_grid(tmp_path, monkeypatch)                                       # 규칙은 노랗 계열만 안다
    s = _subject()
    e = SD.judge_symptom_triage(s, TODAY, observations=[{"id": "o", "text": "잎에 반점이 생겼다", "observed_at": TODAY.isoformat()}])
    assert e.kind == "판단 불가(지식)" and not e.missing
    assert "노랗" in e.result["why"] and ".json" in e.result["why"] and "D-18" in e.result["why"]
    assert "기준이 아는 말" in e.result["summary"] and "노랗" in e.result["summary"]
    e2 = SD.judge_symptom_triage(s, TODAY, observations=[{"id": "o", "text": "오늘 물 줬다", "observed_at": TODAY.isoformat()}])
    assert e2.kind == "판단 불가(데이터)" and e2.missing[0]["axis"] == "observation"   # 증상이 아예 없으면 그대로 데이터 미비
    a = chat.answer(s, "잎에 반점이 생겼는데 어떻게 하나", TODAY)
    assert a.startswith(f"[{words.said('판단 불가(지식)')}]") and "기준이 아는 말" in a and "관찰이 없" not in a


def test_the_symptom_judgement_has_one_vocabulary_canon():
    """3층이 '증상인가' 를 자기 목록으로 판정하지 않는다 — 1층 정본 함수(chat.symptom_in)를 부른다. 두 벌이면 한쪽이 자란 만큼 어긋난다."""
    src = (grid_schema.ROOT / "judge" / "stage_decisions.py").read_text(encoding="utf-8")
    body = src[src.index("def judge_symptom_triage"):]
    body = body[:body.index("\ndef ", 10)]
    assert "from ingest.chat import symptom_in" in body and "symptom_in(o.get" in body
    assert "SYMPTOM_WORDS = " not in src and "chat.SYMPTOM_WORDS" not in src and "import SYMPTOM_WORDS" not in src   # 목록을 복사하지도, 직접 읽지도 않는다(함수만 부른다)
    csrc = (grid_schema.ROOT / "ingest" / "chat.py").read_text(encoding="utf-8")
    ans = csrc[csrc.index("def answer("):]
    ans = ans[:ans.index("\ndef ", 10)]
    assert "symptom_in(text, grid_symptom_words(subject))" in ans                # 라우팅이 격자 말을 덧붙여 쓴다
    assert "classify(text, today, subject=s)" in csrc                            # send 도 재배 단위를 넘긴다
