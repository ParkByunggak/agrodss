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
    ("진딧물 방제 뭘로 하나요", "question", "risk_alert"),       # [2026-09-29] 병·벌레 물음은 칸 비특정 → 위험 경보(pest_alert 는 칸 3 카드)
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
    # 작기 종료 선언(시점 걷기 2026-09-20: 시즌 뒤에도 '놓침 — 사유를 묻는다'가 계속 났다 — 상태를 바꾸는 길이 없었다)
    ("작기 종료", "subject.end", None),
    ("올해 농사 끝났다", "subject.end", None),
    ("11월 5일 쪽파 재배 종료", "subject.end", None),
    ("잔사 정리했다", "event", None),                                                # 정리 사건은 종료가 아니다 — 종료는 명시 문구만
    # [칸 3 재측정 2026-09-20 · C15 와 그 처방 직후 전수] 갈래 어휘가 **밭일 서술 안에** 들어 있으면 그 갈래가 사건보다 먼저
    # 가로챘다. 가르는 표지: 시스템 지시어가 있으면 그 갈래가 맞고, 없으면서 작업 어휘 + 한 일의 어미면 밭일 서술이다.
    ("잘못 심어서 다시 심었다", "event", None),                                       # 교정 어휘가 밭일에 — 개선 요구가 아니다
    ("종구를 잘못 심어서 다시 심었다", "event", None),
    ("웃거름을 잘못 줘서 다시 줬다", "event", None),
    ("예찰 기록이 잘못됐다", "feedback.request", None),                                # 시스템 지시어('기록') — 교정 요구가 맞다
    ("9월 25일 웃거름 일정이 안 맞아요", "feedback.request", None),                     # 날짜가 있어도 **한 일의 어미**가 없으면 밭일 서술이 아니다
    ("계획대로 웃거름을 줬다", "event", None),                                         # 계획 어휘가 부사로 — 한 일은 사건이다
    ("예정대로 파종했다", "event", None),
    ("작기 끝나기 전에 웃거름을 줬다", "event", None),                                  # 종료 문구가 종속절 — 선언이 아니다
    # "다음 주에 트랩 확인하겠습니다" 는 이미 위에 있다 — **그 문장이 이번 회귀를 잡았다**('겠'의 받침 ㅆ 를 과거로 읽던 것).
    ("9월 8일에 트랩 확인했습니다", "event", None),
    # [발행자 2026-09-21 지시의 다음 층] 종류를 **정하기는 하는데 틀리게** 정하던 자리 — 물음표 없는 농가 물음 15 중 8이
    # 관찰 메모로 떨어졌다(물음이 원장에 관찰로 쌓이고 답은 안 나온다). 간접 의문 어미(-는지 · -은지 · -ㄴ지 · -을지)를 본다.
    ("웃거름 지금 줘도 되는지", "question", "top_dressing_1"),
    ("지금 웃거름 시기 맞는지", "question", "top_dressing_1"),
    ("벌레 약 쳐야 하는지", "question", "risk_alert"),          # [2026-09-29] 같은 이유
    ("고랑 물 빠짐 괜찮은지", "question", "drainage_alert"),
    ("지금 상태 어떤지", "question", None),
    ("수확하고 나서 뭐 심을지", "question", None),
    ("비 오면 어떡하지", "question", None),
    ("오늘 할 일", "question", "plan_vs_actual"),
    # 경계 — **과거 서술의 '지'** 는 물음이 아니다(받침 ㅆ·ㅎ 로 끝나 조건에 안 든다)
    ("물 줬지", "event", None),
    ("비료 남았지", "event", None),
    ("그렇지", "observation.note", None),
    ("잎이 노랗지", "observation.note", None),
    # [발행자 실사용 2026-09-29 06:18] "오전에 스프링쿨러 가동 1시간한다" → 관찰 메모로 제안 → 손으로 할 일로. 장치+돌리는 말 · 문장 끝 현재·앞날 서술
    ("오전에 스프링쿨러 가동 1시간한다", "plan.farmer", None),
    ("스프링쿨러가 고장났다", "observation.note", None),               # 장치 이름 홀로는 여전히 관수가 아니다(2026-09-21 규율 그대로)
    ("오늘 급수 1시간 한다", "plan.farmer", None),                     # '오늘' 이 한 일 표지로 읽혀 사건이 되던 것 — 문장 끝 '한다' 는 앞날
    ("오전에 스프링쿨러 돌렸다", "event", None),                       # 장치 + 돌리는 말 + 받침 ㅆ = 한 일
    ("내일 파종", "plan.farmer", None),                                 # 처방 직후 전수 — 내일 날짜의 '한 일' 이 되던 것(날짜 표지 = 한 일 표지의 구멍)
    ("내일 물 준다", "plan.farmer", None),
    ("어제 오전에 물 줬다", "event", None),                             # 받침 ㅆ 과거가 있으면 한 일 그대로
    ("잎이 마른다", "observation.note", None),                          # 작업 어휘 없는 '…ㄴ다' 는 계획이 아니다
    ("잎이 노랗게 변한다", "observation.note", None),                    # '…한다' 로 끝나도 작업 어휘가 없으면 관찰(주입 C 가 이 문장 없이는 안 잡혔다)
    # [WO-LLM-01 첫 측정 2026-09-29 08:21 KST · 발행자 PC] 농가 발화 70 · 종류 고침 4 — 기대 종류는 발행자가 붙였다(고친 종류 그대로)
    ("가을 가뭄이 심하다. 아침에 포장을 보니 특별한 징후는 없다", "event", None),   # 발행자 '한 일' — 포장을 본 것이 예찰
    ("오늘 물주었다", "event", None),                                    # 발행자 '한 일' — 띄어쓰기 없는 '물주었'
    # [발행자 실사용 2026-09-29 아침 · 화면 9903974] "오늘 날씨 어떄"(오타) · "오늘 날씨는" 이 본 것으로 — "한 의미로 질문한 것을 서로 다르게 답을 한다"
    ("오늘 날씨 어떄", "question", "forecast_citation"),
    ("오늘 날씨는", "question", "forecast_citation"),
    ("오늘 날씨가 좋다", "observation.note", None),                       # 서술어가 있으면 본 것 그대로
    # [U-40 발행자 실사용 2026-10-03] 조회 — 판단이 아니라 기록 보여 주기. 명사(관수)가 가뭄 판정으로 끌고 갔다 → 동사·시제로 조회가 먼저
    ("이전에 관수를 일지에서 날짜별로 알려줘요", "question", chat.LOOKUP_ID),   # 발행자 라이브 2026-10-03 — 가뭄 판정으로 갔던 문장
    ("관수 언제 했나", "question", chat.LOOKUP_ID),                           # 발행자가 든 꼴 「언제 … 했나」
    ("방제 기록 보여줘", "question", chat.LOOKUP_ID),                         # 보여줘 — 요청형(전에는 본 것으로 분류됐다)
    ("일지에서 관수 날짜 알려줘", "question", chat.LOOKUP_ID),
    ("가뭄이 심한데 물 줘야 하나요", "question", "drought_alert"),             # 반대편 — 판단을 묻는 관수 물음은 그대로 가뭄 판정
    ("관수했다", "event", None),                                               # 반대편 — 한 일은 사건 그대로
    # [발행자 실사용 2026-10-04] 용도 선언은 관찰이 아니라 밭 정보 값(속성 선언 갈래) · 시스템을 향한 항의는 교정 요구
    ("이 쪽파는 종구생산을 위한 목적이다", "parcel.field", None),                 # 발행자 라이브 2026-10-04 — 본 것으로 떨어졌던 문장
    ("자가 소비용이다", "parcel.field", None),
    ("이번 작기는 팔 것이다", "parcel.field", None),
    ("이 밭은 몰 납품 목적이다", "parcel.field", None),
    ("이 밭은 몰 납품용으로 쓸 생각", "plan.target_date", None),                       # 반대편 — 납품 + 계획 어휘는 납품 계획 그대로(앞 갈래가 이긴다)
    ("고르신 종류(처음 제안과 다릅니다) · obs_93e9b4b67856 이미 있는데 왜 되묻는가?", "feedback.request", None),   # 발행자 라이브 2026-10-04 — 항의가 본 것/물음으로
    ("왜 또 묻나요", "feedback.request", None),
    ("이번 작기는 몰 납품용으로 심었다", "event", None),                           # 반대편 — 한 일의 표지가 있으면 사건이 이긴다
    ("종구가 썩은 것 같다", "observation.note", None),                           # 반대편 — 용도 말이 있어도 선언 표지 없는 상태 서술은 본 것
    ("잎이 왜 노랗나요", "question", None),                                        # 반대편 — 밭을 향한 「왜」 는 물음 그대로(증상 물음은 answer 가 증상 결정으로)
    # [거꾸로 세는 검사 전수 2026-10-04] 인증 선언 — 농가 몫 요구 축 가운데 길이 없던 하나(용도와 같은 형태)
    ("이 밭은 유기 인증을 받았다", "subject.field", None),
    ("인증은 무농약이다", "subject.field", None),
    ("관행 재배다", "subject.field", None),
    ("유기질 비료를 줬다", "event", None),                                         # 반대편 — 자재 말은 선언이 아니다(한 일)
    # [대파 걷기 2026-10-04] 종결 의문 어미(-나 · -냐 · -ㅂ니까) — 쪽파 · 대파 둘 다 '본 것' 으로 적혔던 물음(물음표 없는 물음의 남은 갈래)
    ("물 줘야 하나", "question", "drought_alert"),
    ("병충해 뭐 봐야 하나", "question", "risk_alert"),
    ("비료 뭐 주나", "question", "material_citation"),
    ("서리 오나", "question", "risk_alert"),
    ("약 쳐야 하냐", "question", "material_citation"),
    ("물을 줘야 합니까", "question", "drought_alert"),
    ("비가 오면 뭐 하나", "question", "risk_alert"),                                 # 의문사 뒤 「하나」 는 셈말이 아니다
    ("언제 수확하나", "question", "harvest_timing"),
    # 반대편 — 끝이 같아도 물음이 아닌 것: 셈말 「하나」 · 감탄 「-구나」 · 이유 「-니까」(ㅂ 받침 없음) · 셈 「-이나」
    ("노란 포기가 하나", "observation.note", None),
    ("잎이 노랗구나", "observation.note", None),
    ("비가 왔으니까", "observation.note", None),
    ("마른 포기가 둘이나", "observation.note", None),
    # [문장 형태 2026-10-04] 목적어와 동사 사이의 부사·수량 말 — 두 낱말 짝(물 줬 · 약 쳤 · 풀 뽑)이 깨져 본 것이 되던 한 일(과거 어미는 그대로 있다 — 기존 규칙의 빈칸)
    ("물 한 번 줬네", "event", None),
    ("물을 좀 줬다", "event", None),
    ("물 많이 줬다", "event", None),
    ("약 조금 쳤다", "event", None),
    ("풀 좀 뽑았다", "event", None),
    # 일지 투의 명사형 끝 — 작업 어휘 + 앞날 표지 없음 = 한 일(「방제 완료」 「9/8 트랩 확인」 과 같은 축)
    ("풀 뽑음", "event", None),
    ("물 줌", "event", None),
    ("약 침", "event", None),
    ("웃거름 줌", "event", None),
    # 반대편 — 앞날 표지가 있으면 계획 · 작업 어휘 없는 명사형은 본 것 · 활동 이름(-기)은 한 일이 아니다
    ("내일 물 줌", "plan.farmer", None),
    ("잎이 노람", "observation.note", None),
    ("싹이 올라옴", "observation.note", None),
    ("물 주기", "observation.note", None),
    # [문장 형태 2026-10-04 · 발행자 "「왜 …는가」 → 항의"] 시스템을 향한 항의 — 교정 어휘 없이 오는 두 꼴(왜 + 묻는 동사 · 시스템 명사 + 불평 서술)
    ("왜 자꾸 같은 걸 묻지", "feedback.request", None),
    ("같은 질문을 왜 반복하나", "feedback.request", None),
    ("답이 이상한데", "feedback.request", None),
    ("답이 말이 안 된다", "feedback.request", None),
    ("화면이 안 뜬다", "feedback.request", None),
    ("답이 왜 이래", "feedback.request", None),
    # 반대편 — 밭을 향한 왜는 물음 · 시스템 명사 없는 이상은 본 것 그대로
    ("싹이 왜 안 나오나", "question", None),
    ("비가 왜 안 오나", "question", None),
    ("잎이 이상한데", "observation.note", None),
    # [2026-10-04 심은 날 물음 걷기] 부정이 **동사 바로 앞**에 오는 꼴(안 심었 · 못 심었) — 접기(§)가 동사 앞에 붙어 "안에 § 가 끼는" 검사에 안 걸려 파종 **사건**이 됐다(넣으면 심은 날이 선다)
    ("아직 안 심었어요", "decision.noncompliance", None),
    ("종구 못 심었다", "decision.noncompliance", None),
    ("아직 안 뿌렸어요", "decision.noncompliance", None),                                     # 반대편 「비가 안 와서 물 줬다」 는 위에 이미 있다 — 다른 서술어의 부정은 그대로 한 일
    # [문장 형태 점검 전수 2026-10-05] 종결 어미를 **어휘 조각**으로 세던 자리의 두 얼굴. ① 빠진 쪽 — 「-ㄴ가」 조각이 인가·는가·은가 셋뿐이라 같은 어미가 본 것으로 떨어졌다
    ("관수가 필요한가", "question", "drought_alert"),
    ("흙이 마른가", "question", None),
    ("잎이 노란가", "question", None),                                                        # 증상 경로는 `topic_of` 가 아니라 증상 가름이 정한다(화면에서는 「증상 → 원인 좁히기」)
    ("물이 모자란가", "question", None),
    ("배수가 좋은가", "question", "drainage_alert"),                                          # 조각으로 이미 통과하던 꼴 — 어미 규칙으로 옮긴 뒤에도 그대로
    # ② 새는 쪽 — 조각이 문장 **중간**에 있고 말은 과거 서술로 끝난다(한 일이 원장에 안 들어가고 답만 나간다)
    ("오늘 할 일 다 했다", "observation.note", None),
    ("무슨 일이 있었다", "observation.note", None),
    ("언제인가 모르지만 물 줬다", "event", None),
    ("어떻게 해야 할지 몰라서 그냥 관수했다", "event", None),                                   # C15 전수에서 등재해 둔 꼴 — 과거 서술 끝 가드가 닫는다
    # ③ 경계 — 끝을 보는 판정(물음표 · 어미 규칙)은 그 가드를 안 받는다
    ("물 줬는지 알려줘", "question", None),
    ("뭘 해야 하는지 모르겠다", "question", "plan_vs_actual"),                                  # 「모르겠다」 의 ㅆ 은 과거가 아니다(정본 _NOT_PAST_SSANG)
    ("할 일이 있나", "question", "plan_vs_actual"),                                           # 「있다」 도 같은 정본으로 빠진다
]


@pytest.mark.parametrize("text,kind,topic", CORPUS, ids=[c[0] for c in CORPUS])
def test_corpus_kind_and_topic(text, kind, topic):
    drafts = chat.classify(text, TODAY)
    assert drafts and drafts[0]["kind"] == kind, (text, drafts)
    if kind == "question" and topic:
        assert chat.topic_of(text) == topic, (text, chat.topic_of(text))


CORPUS_MIN = 131   # [발행자 2026-09-20] 말뭉치는 append-only — 문장을 빼지 않고 기대 종류만 고친다. 이 하한은 **위로만** 올린다(줄면 "왜 줄었나"를 못 묻는다)


def test_corpus_is_append_only():
    assert len(CORPUS) >= CORPUS_MIN, (len(CORPUS), CORPUS_MIN)


def test_corpus_covers_every_kind_and_has_no_duplicates():
    kinds = {c[1] for c in CORPUS}
    assert kinds == {"question", "event", "observation.note", "plan.farmer", "plan.target_date", "feedback.request", "decision.noncompliance", "subject.end",
                     "parcel.field", "subject.field"}   # [2026-10-04] 속성 선언 갈래(용도 · 인증) — 아홉째 · 열째
    assert len({c[0] for c in CORPUS}) == len(CORPUS)
