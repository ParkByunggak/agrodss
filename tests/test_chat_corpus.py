# -*- coding: utf-8 -*-
# [M-13 · 발행자 2026-09-19 "질문을 분석하고 그 성격을 분류해서 내부 로직으로"] 분류기 전수 래칫 — 농가 발화 형태별 기대 종류.
#   라이브 두 문장이 각각 한 건씩 새는 것을 보고, 같은 형태를 전수로 쟀다(§7.5 지점 축): 40문장 중 9건이 틀렸고 전부 어휘·어미 형태였다.
#   여기 문장을 늘리는 것이 어휘 확장의 정본 경로다 — 발행자 화면에서 틀린 종류로 제안된 문장은 기대 종류와 함께 이 표에 넣는다.
from __future__ import annotations

from datetime import date

import pytest

from ingest import chat

TODAY = date(2026, 9, 19)
# (발화, 기대 종류, 기대 결정 — 질문일 때만)
CORPUS = [
    # 질문 — 물음표 없음
    ("지금 뭘 해야 하죠", "question", "plan_vs_actual"),
    ("웃거름 언제 줘야 하는지 알려주세요", "question", "top_dressing_1"),
    ("수확은 언제쯤인가요", "question", "harvest_timing"),
    ("서리 오면 어떻게 하죠", "question", "risk_alert"),
    ("이번 주 할 일 알려줘", "question", "plan_vs_actual"),
    ("지금 쓸 수 있는 약 있나요", "question", "material_citation"),
    ("보식해도 되나", "question", "replant"),
    ("고랑에 물이 고이는데 괜찮을까요", "question", "drainage_alert"),
    ("파종 시기가 지났나요", "question", "sowing_window"),
    ("오늘 상태 어때", "question", None),
    ("뭐부터 챙겨야 해", "question", "plan_vs_actual"),
    ("출하는 언제가 좋을까", "question", "ship_or_store"),
    ("진딧물 방제 뭘로 하나요", "question", "pest_alert"),
    ("쪽파를 현재 관리해야 할 항목들을 알려줘요", "question", "plan_vs_actual"),     # 발행자 라이브 2026-09-19
    # 사건(과거)
    ("오늘 웃거름 줬다", "event", None),
    ("어제 트랩 확인했어요", "event", None),
    ("9월 10일에 풀 뽑았어요", "event", None),
    ("물 줬어요", "event", None),
    ("아침에 약 쳤습니다", "event", None),
    ("종구 심었습니다", "event", None),
    ("고랑 정비했다", "event", None),
    ("오늘 뽑아서 다듬었어요", "event", None),
    # 관찰
    ("잎 끝이 노랗게 변했어요", "observation.note", None),
    ("싹이 고르게 올라왔다", "observation.note", None),
    ("밭이 너무 말랐어요", "observation.note", None),
    ("잎이 이상해요", "observation.note", None),                                   # 작물 서술 — 교정 요구가 아니다
    ("오늘 상황은 줄기가 매우 왕성한 모습이다", "observation.note", None),           # 발행자 라이브 2026-09-19
    ("오늘은 특별한 일 없음", "observation.note", None),                             # 서술문 → 관찰 메모 제안
    ("비가 많이 왔어요", "observation.note", None),
    # 피해 → 사건(피해)
    ("벌레 먹은 잎이 몇 개 보여요", "event", None),                                  # '몇 ' 이 질문으로 새던 것
    ("서리 맞아서 잎이 얼었어요", "event", None),
    ("일부 썩었어요", "event", None),
    # 계획
    ("내일 웃거름 주려고요", "plan.farmer", None),
    ("주말에 제초할 예정입니다", "plan.farmer", None),
    ("10월 말 납품 예정", "plan.target_date", None),
    ("다음 주에 트랩 확인하겠습니다", "plan.farmer", None),
    ("이번 주 안에 배수로 손볼 생각", "plan.farmer", None),
    ("9월 25일에 웃거름 해야 할 것 같다", "plan.farmer", None),                     # 요청형 확장이 계획을 삼키지 않는다
    # 개선 요구
    ("수확 창이 너무 넓어요 고쳐주세요", "feedback.request", None),
    ("답이 틀린 것 같아요", "feedback.request", None),
    ("경보가 너무 자주 와서 불편해요", "feedback.request", None),
    ("예정일이 안 맞아요", "feedback.request", None),
    # 불이행 사유 — 사건 어휘 + 부정(발행자 2026-09-20 "웃거름 주지 않고 …"). 쪽파는 사례 — 작업 종류는 작목 공통 어휘로 잡는다
    ("쪽파 포장에는 웃거름 주지 않고 수분공급만 표면이 마르지 않게 해 줌. 그 근거는 토양검증 상태를 기준으로 함", "decision.noncompliance", None),
    ("방제는 하지 않았다, 벌레가 없어서", "decision.noncompliance", None),
    ("약 안 쳤다", "decision.noncompliance", None),                                   # 어휘 사이에 낀 부정
    ("제초 생략했다", "decision.noncompliance", None),
    ("웃거름 못 줬어요", "decision.noncompliance", None),
    # 부정이 사건 어휘 **앞** 이면 사건이다 · 계획 · 질문은 여전히 먼저다
    ("비가 안 와서 물 줬다", "event", None),
    ("잎이 마르지 않게 물 줬다", "event", None),
    ("벌레가 안 보인다", "observation.note", None),
    ("내일 웃거름 주지 않을 예정", "plan.farmer", None),
    ("웃거름 안 줘도 되나요", "question", "top_dressing_1"),
    # 피해 어휘 + 부정 = 피해 없음 관찰 — §7.5 처방 직후 전수(2026-09-20): 사건 부정을 고친 직후 같은 형태를 세니 13문장 중 7건이 피해 사건이었다
    ("서리에 안 얼었다", "observation.note", None),
    ("서리 피해 없었다", "observation.note", None),
    ("벌레가 먹지 않았다", "observation.note", None),
    ("피해 없음", "observation.note", None),
    ("병 걸린 건 없다", "observation.note", None),
    ("진딧물이 안 보인다", "observation.note", None),
    ("얼어 죽은 게 없다", "observation.note", None),
    ("서리 맞았는데 피해는 없다", "observation.note", None),
    ("피해가 컸다", "event", None),                                                   # 긍정은 그대로 피해(갈래 미상 → 확인이 묻는다)
    # 검토(2026-09-20) 실측 — 부정이 **다른 서술어**의 것이면 사건이 남는다 · '할 수 없다'는 부재가 아니다 · 갈래 하나 부정 + 다른 갈래 긍정은 긍정
    ("물 줬는데 충분하지 않다", "event", None),
    ("물 줬는데 많지 않다", "event", None),                                            # 과거 동사 어휘(줬) 뒤의 짧은 부정 — 이 문장만 _PAST_WORD 가드가 막는다(가드 둘 = 검사 둘)
    ("수확했는데 많지 않다", "event", None),
    ("서리에 얼어서 상품성이 없다", "event", None),
    ("얼어붙어서 걷을 수 없었다", "event", None),
    ("벌레 먹은 잎은 없고 곰팡이가 폈다", "event", None),
    ("9월 16일에 웃거름 안 줬다. 토양검정 기준", "decision.noncompliance", None),          # 날짜가 있어도 불이행 사유(계획표 잇기는 send 에서)
    # 명사 어휘만으로는 사건이 아니다(검토 잔여 2026-09-20) — 한 일의 표지(과거 어미 · 날짜 · 완료)가 있어야 사건
    ("비료 상태가 안 좋다", "observation.note", None),
    ("웃거름 시기다", "observation.note", None),
    ("거름 냄새가 난다", "observation.note", None),
    ("관수 시설 점검", "observation.note", None),
    ("오늘 파종", "event", None),
    ("방제 완료", "event", None),
    ("9월 10일 방제", "event", None),
    # 발행자 다음 행위(9/8 예찰 한 줄)를 걷다 잡힌 것(2026-09-20): 조사가 붙은 부정 · 빗금 날짜
    ("9월 8일에 트랩 확인했다", "event", None),
    ("9/8 트랩 확인", "event", None),                                                 # 빗금 월/일도 날짜(한 일의 표지)
    ("트랩 확인은 안 했다", "decision.noncompliance", None),                          # '확인은' — 조사가 붙어도 부정
    ("트랩 확인을 못 했다", "decision.noncompliance", None),
]


@pytest.mark.parametrize("text,kind,topic", CORPUS, ids=[c[0] for c in CORPUS])
def test_corpus_kind_and_topic(text, kind, topic):
    drafts = chat.classify(text, TODAY)
    assert drafts and drafts[0]["kind"] == kind, (text, drafts)
    if kind == "question" and topic:
        assert chat.topic_of(text) == topic, (text, chat.topic_of(text))


CORPUS_MIN = 75   # [발행자 2026-09-20] 말뭉치는 append-only — 문장을 빼지 않고 기대 종류만 고친다. 이 하한은 **위로만** 올린다(줄면 "왜 줄었나"를 못 묻는다)


def test_corpus_is_append_only():
    assert len(CORPUS) >= CORPUS_MIN, (len(CORPUS), CORPUS_MIN)


def test_corpus_covers_every_kind_and_has_no_duplicates():
    kinds = {c[1] for c in CORPUS}
    assert kinds == {"question", "event", "observation.note", "plan.farmer", "plan.target_date", "feedback.request", "decision.noncompliance"}
    assert len({c[0] for c in CORPUS}) == len(CORPUS)
