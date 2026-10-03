# -*- coding: utf-8 -*-
"""WO-PB-01 발행자 응답 병목 — 측정과 갈래 판정 (2026-09-29 착수 · 규칙 변경 아님).

*"세션이 값을 지어내지 않는다"* 와 *"모든 값을 발행자가 직접 준다"* 는 다른 규칙인데 지금 하나로 붙어 있다 — 이 도구는 그 둘을
가르는 **근거를 측정으로** 만든다. 대기 항목 전수(대장 대기·진행·등재 + 핸드오버 발행자 몫 + 검토지 미회신 문항)에 갈래(P1~P4)와
근거를 붙이고, 비율로 H1/H2/H3 를 판정하고, P2 로 판정된 원천이 **실제로 닿는지**를 잰다.

하지 않는 것(지시서 §7): 격자 값을 채우지 않는다 · 임계를 제안하지 않는다 · 대기 항목을 닫지 않는다 · 규칙을 바꾸지 않는다.
쓰는 곳은 **보고서 경로 하나**뿐이다(격자 · 원장 · 대장은 읽기만 — 검사가 바이트를 전후로 대조한다).

판정 규칙(지시서 §3 — 자기에게 유리하게 기울지 않도록, 기계로 강제한다):
  P2 는 원천과 접근 경로를 함께 적어야 성립한다 → 없으면 P4 로 떨어진다("어딘가 있을 것"은 P2 가 아니다)
  P3 는 그 자리에서 고칠 수 있어야 성립한다     → 고칠 자리(파일)가 없으면 P1 로 떨어진다(갈리면 사람 쪽이 안전한 실패)
도달성(§4): 원천에 닿지 못한 것은 **미확인**이지 "없음"이 아니다 — 컨테이너에서 차단된 것을 "원천에 없다"로 적은 전례가 있다.

쓰는 법:
  python -m scripts.measure_publisher_bottleneck --today 2026-09-29 docs/wo_pb01_publisher_bottleneck.md   # 보고서(기준일 고정)
  python -m scripts.measure_publisher_bottleneck --probe                                                    # 발행자 PC 에서 도달성 재측정(쓰지 않는다)
"""
from __future__ import annotations

import argparse
import re
import sys
import urllib.error
import urllib.request
from dataclasses import dataclass, field, replace
from datetime import date, datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
BACKLOG = ROOT / "docs" / "agrodss_backlog.md"
REVIEW = ROOT / "docs" / "review_jjokpa_20260918.md"
DOC_PATH = ROOT / "docs" / "wo_pb01_publisher_bottleneck.md"

BRANCHES = ("P1", "P2", "P3", "P4")
BRANCH_SAID = {"P1": "발행자만", "P2": "외부 정본", "P3": "내부 논리", "P4": "어디에도 없음"}
OPEN_STATES = ("대기", "진행", "등재")          # 대장 상태 셀의 머리 — 이 셋이 "열린" 항목이다(보류는 지시서 §2 의 대상이 아니다)
LONG_OPEN_DAYS = 30                             # §2 "30일 넘게 열려 있는 항목은 밀린 것이 아니라 안 닫히는 것이다"
REACHED, UNREACHED = "도달", "미확인"           # §4 — "없음" 이라는 상태는 이 도구에 없다
GROUPS = ("대장", "핸드오버", "검토지")
PROBE_TIMEOUT = 15
NEXT_MOVE_BUILT = "5b8d9e3"      # §5 의 한 수(일괄 결정 화면)가 선 커밋 — 비면 아직 안 선 것(문서가 "별도 묶음" 까지만 말한다)


@dataclass(frozen=True)
class Item:
    id: str
    ask: str                      # 무엇을 묻는가
    since: date                   # 등재일
    blocker: str                  # 막고 있는 것
    branch: str                   # P1~P4 (세션 판정 · 표 전체를 발행자가 한 번에 본다)
    why: str                      # 판정 근거
    group: str = "대장"
    source: str = ""              # P2 — 원천 이름
    path: str = ""                # P2 — 접근 경로 · P3 — 고칠 자리
    n: int = 1                    # 문항 수(검토지 장은 문항 여럿을 한 행으로)
    fell: str = ""                # 규칙이 갈래를 떨어뜨렸으면 그 사유(classify 가 채운다)


# ── 세션 판정 (2026-09-29) ── 등재일은 대장 행에서 다시 읽어 대조한다(대장 그룹). 갈래·근거는 세션의 판정이고 발행자가 표 전체를 본 뒤 뒤집을 수 있다.
JUDGMENTS: tuple[Item, ...] = (
    # 대장 D-
    Item("D-2", "DSS 판정을 소비자에게 보일 것인가", date(2026, 9, 18), "이 결정에 D-3 · D-7 · D-19 · M-11 이 매달린다(뿌리)", "P1",
         "사업의 방향 결정 — 원천에도 코드에도 답이 없다"),
    Item("D-3", "예약 판매를 도입할 것인가", date(2026, 9, 18), "D-2 · U-7 수량 예측 · U-8 환불 규칙(둘 다 보류)", "P1",
         "판매 방식 결정"),
    Item("D-4", "몰 외부 계약(PG · 택배 · CDN · 본인확인)", date(2026, 9, 18), "계약 상대 — 시스템 밖 · 첫 작기가 자가(D-8)라 지금 필요 없음", "P1",
         "계약은 사람이 맺는다"),
    Item("D-7", "몰 화면의 프론트 스택", date(2026, 9, 18), "D-2 · D-3 · 판매 작기 없음", "P1",
         "기술 방향 결정 — 앞 결정 둘이 서야 뜻이 있고 지금은 목업(M-11)으로 충분"),
    Item("D-16", "휴대폰 동기화(같은 Wi-Fi 옵트인)를 켤 것인가", date(2026, 9, 19), "D-6 외부 배포 금지 문면과 부딪힘", "P1",
         "보안 경계를 여는 결정 — 코드는 옵트인으로 준비됨(값이 아니라 허가)"),
    Item("D-17", "찍은 때 사다리의 '파일 이름' 칸을 둘 것인가", date(2026, 9, 24), "없음 — 권고(①)가 있어 「맞다」 한 번이면 닫힌다", "P1",
         "세 선택지 중 하나를 고르는 설계 결정"),
    Item("D-19", "검색엔진 노출 — 어느 화면을 언제 · 호스팅", date(2026, 9, 26), "D-2 · D-7 · 호스팅", "P1",
         "공개 대상 · 시점 · 호스팅 셋 다 방향 결정"),
    Item("D-20", "가뭄 임계 — 무강수 며칠이면 관수 검토(dry_days) · 출처", date(2026, 9, 28), "값 하나(오면 한 명령 apply_grid_value)", "P2",
         "관수 기준은 재배 기술 문헌에 있는 종류의 값 — 발행자 문면도 \"농진청 쪽파 재배 지침(또는 내 경험)\". 도달 뒤 '무강수 N일' 형태인지 확인 — 월 단위 달력이면 P4(§4)",
         source="농사로 농업기술길잡이 「쪽파」 재배기술(관수) · 흙토람 작물별 관수 기준",
         path="www.nongsaro.go.kr 농업기술 → 작목기술정보 → 쪽파(열람) · api.nongsaro.go.kr cropEbook(키 필요)"),
    # D-22(수확 칸 가뭄 임계)는 2026-10-03 발행자 맞다로 닫혔다 — 대장 행이 완료라 여기서 빠진다(열린 행 전수 래칫) · 화면 카드는 남는다(decisions.DECIDED)
    Item("D-23", "배수 「나쁨」 이면 과습을 경보로 올릴 것인가 — 어떤 조건에서(발행자 의견: 배수 나쁨 + 연속 강우 예보면 경보)", date(2026, 10, 3), "맞다 한 번(결정 화면) — 오면 risk_alert 등급 규칙 한 줄", "P1",
         "임계·등급 규칙은 지식이지만 **이 밭의 경보를 얼마나 민감하게 둘 것인가**는 발행자 결정 — 발행자 스스로 \"결정 화면에서 답할 수 있는 형태\" 라 했고 의견(전자)을 추론 표시로 올렸다"),
    Item("D-24", "종구 생산 — 수확 · 수확 후 두 칸의 종구 기준(창 · 위험 · 할 일) by_use", date(2026, 10, 3), "두 칸 값 한 줄씩 — 오면 한 명령(apply_grid_value --key by_use)", "P2",
         "종구 재배 기술은 재배 기술 문헌에 있는 종류의 값(창 · 위험 · 작업) — 이장 경험이 보조. 결정(용도 = 종구)은 이미 섰고 자리와 문도 섰다(2026-10-03) · 남은 것은 값",
         source="농사로 농업기술길잡이 「쪽파」 재배기술(종구 생산 · 수확) · 이장 경험(이 밭)",
         path="www.nongsaro.go.kr 농업기술 → 작목기술정보 → 쪽파(열람) · 밭 정보 화면 용도 칸 「종구 생산」(발행자 PC)"),
    Item("U-40", "조회 질문이 판정으로 간다 — 명사 라우팅(「관수를 일지에서 날짜별로 알려줘」 → 가뭄 판정)", date(2026, 10, 3), "말뭉치 두 문장 + 일지 조회 갈래", "P3",
         "코드 안에서 닫힌다 — 조회(알려줘 · 보여줘 · 언제 … 했나)를 사실 인용 축으로 보내고 말뭉치로 고정(발행자가 재료 두 문장을 주었다)",
         path="ingest/chat.py topic_of · answer_with_asks(일지 조회 갈래) · tests/test_chat_corpus.py"),
    Item("D-21", "1개월 전망 값 — 주 단위 기온·강수 3분위(매주)", date(2026, 9, 28), "매주 한 번 값 — /me/outlook 폼", "P2",
         "기상청 발표문에 값이 있다. 오픈 API 가 없어(VELA 2026-08-05 측정) '확인' 이 아니라 '옮겨 적기' — §6 비용 측정 후보",
         source="기상청 날씨누리 기후예측 「1개월 전망」 발표문(목요일)",
         path="www.weather.go.kr → 기후예측 → 1개월 전망(HTML · API 없음) → /me/outlook"),
    # 대장 I- · M- · U-
    Item("I-6", "첫 필지 입력 — 토성 · 경사 · 배수 · 관수 · 야간조명 · 미기상 · 종구 출처 · 인증서", date(2026, 9, 18), "농가 답(/me/parcel) — 읽는 쪽은 U-20", "P1",
         "이 밭의 물리 특성 — 검정값·좌표만 흙토람 API(ingest.soil_exam · PC 키)로 오고 나머지는 발행자만 안다(갈리면 P1)"),
    Item("I-7", "첫 촬영 · 등록", date(2026, 9, 18), "농가 행위(촬영)", "P1",
         "촬영은 사람의 행위 — 지식도 결정도 아니고 밭에 있는 사람만"),
    Item("M-8", "유형별 대표 작목 얕게 한 바퀴(종이)", date(2026, 9, 18), "없음 — 세션 큐(첫 시즌 우선) · 발행자 대기 아님", "P3",
         "격자 형태가 다른 유형에도 서는지 보는 종이 작업 — 값이 아니라 축 출현 확인 · 세션이 연다",
         path="docs/m4_grid_schema.md · grid/schema.py"),
    Item("M-11", "몰 MVP — 영상 저장 · 정산 · 입점", date(2026, 9, 18), "D-2 · D-3 · 판매 작기", "P1",
         "남은 코드(영상 스트리밍)는 세션 몫이나 D-2 · D-3 전에는 나갈 곳이 없다 — 막는 것은 결정"),
    Item("M-12", "첫 시즌 운영 — 되먹임 1바퀴", date(2026, 9, 18), "시즌 경과(첫 수확 창 10/14~)", "P4",
         "첫 시즌 실측 자체가 재료 — 표준에도 이 밭에도 아직 없다"),
    Item("M-13", "내부 화면(채팅 · 일지) — 실사용 관찰의 처방", date(2026, 9, 18), "없음 — 관찰이 오면 그때 · 발행자 대기 아님", "P3",
         "화면은 서 있고 남은 것은 관찰의 처방 — 코드 안에서 닫힌다",
         path="frontend/ · ingest/chat.py"),
    Item("M-15", "외부 원천 인용 — NCPMS 쪽파 코드 · 응답 필드명 확정 · 시세", date(2026, 9, 18), "라이브 응답(키는 PC .env)", "P2",
         "원천·경로가 코드에 있다(ingest/ncpms.py SVC51 · '파' 대리 코드) — 응답 형태만 라이브에서 확정",
         source="NCPMS 병해충 예찰 API SVC51(작물 코드 · 발생 정보)",
         path="ncpms.rda.go.kr/npmsAPI/service?serviceCode=SVC51 · 키 NCPMS_API_KEY(.env · PC)"),
    Item("U-18", "저장소 비공개 전환(1분) · 이력 force-push 결정", date(2026, 9, 20), "발행자 GitHub 설정 · 되돌릴 수 없는 결정", "P1",
         "저장소 설정은 소유자만 · 이력 삭제는 파괴적이라 세션이 하지 않는다"),
    Item("U-20", "필지 축 소비자 0 — 예찰 보정 임계", date(2026, 9, 21), "NCPMS 임계 정본(M-15 ③)", "P2",
         "발생 예찰 기준은 공공 예찰 체계의 값 — 쪽파 · 고자리파리 임계가 '값' 형태로 있는지는 도달 뒤 확인(없으면 P4)",
         source="NCPMS 예찰 기준(발생 예찰 · 방제 기준)",
         path="ncpms.rda.go.kr → 병해충 예찰 정보 · SVC51"),
    Item("U-22", "훅 배선 — 세션 루트 저장소의 .claude/settings.json", date(2026, 9, 21), "인용 전용 저장소(D-9)라 세션이 못 넣음", "P1",
         "발행자 PC · 세션 설정 — 세션이 손댈 수 없는 자리"),
    # 핸드오버 · 대장 페이지 「발행자 몫」 — 대장 행이 없는 것
    Item("H-①", "자기 점검 화면 라이브 1회 — 「자기 점검」 열어 5/5 인지", date(2026, 9, 29), "새 커밋이 선 뒤 사람의 눈", "P1",
         "실사용 관찰 — 발행자 PC 화면만 볼 수 있다(컨테이너에서 못 잰다)", group="핸드오버"),
    Item("H-⑦", "§5 ⑦ 등재 후보(예보 호출 상한 · 메모) 등재 여부", date(2026, 9, 28), "다리 B 결정", "P1",
         "등재는 발행자 판단(다리 B) — 등재 뒤 처방은 P3", group="핸드오버"),
    Item("H-후보", "등재 후보 넷 — 닫힌 칸 회복 불가 위험 잔류 · 배수 물음의 칸 묶임 · 평년값 인용 · 손상 덮개에 씨앗으로 내되 말하기(09-30)", date(2026, 9, 29), "다리 B 결정", "P1",
         "같음 — 각각 규칙·로더 한 줄이라 등재 뒤는 P3 · 넷째는 09-30 산출물 검토에서(발행자 측 의견 있음 · 결정은 발행자)", group="핸드오버", n=4),
    Item("H-키", "KMA_API_HUB_KEY 유무 · 승인(PC .env) — 관측 원천", date(2026, 9, 29), "PC 상태", "P1",
         "발행자 PC 의 상태 — 자기 점검 ⑤b 줄이 답의 괄호로 대신 본다", group="핸드오버"),
    Item("H-채팅", "9/8 예찰 한 줄 · 9/16 웃거름 문장을 채팅에(상태 미확인 · 예찰 9/24 마감 지남)", date(2026, 9, 20), "발행자 PC 원장 — 여기서 못 본다", "P1",
         "원장은 화면에서 확인한 것만 — 세션에 말한 문장은 안 들어간다", group="핸드오버", n=2),
    # 검토지 review_jjokpa_20260918 — 미회신 문항(답 칸 전부 빈 채 · ⓓ 는 09-20)
    Item("R-ⓒ1~4", "회복 불가 위험 트리거 문면 4(파종 적기 · 고자리파리 · 과습 · 첫 서리)가 맞는가", date(2026, 9, 18), "답 4", "P2",
         "트리거는 재배 기술 문헌의 조건(초안이 '추론') — 문헌 대조로 확정 가능 · 이 밭 특이성은 그 뒤", group="검토지", n=4,
         source="농사로 농업기술길잡이 쪽파 · NCPMS 병해충 정보(고자리파리)",
         path="nongsaro.go.kr 작목기술정보 → 쪽파 · ncpms.rda.go.kr 병해충 도감"),
    Item("R-ⓐ", "작목 축 9(생애주기 · 수확형태 · 번식 · 저장성 …)", date(2026, 9, 18), "답 9", "P2",
         "작목의 표준 속성 — 문헌 값 · 발행자는 확인만", group="검토지", n=9,
         source="농사로 작목기술정보 「쪽파」 · 농진청 농업기술길잡이",
         path="www.nongsaro.go.kr 농업기술 → 작목기술정보 → 쪽파"),
    Item("R-ⓑ", "충북 · 괴산에서 실제 듣는 이름 9", date(2026, 9, 18), "답 9", "P1",
         "'실제 듣는' 것은 그 자리 사람만 안다 — 방언 사전은 후보일 뿐(초안이 이미 그것)", group="검토지", n=9),
    Item("R-ⓓB4", "칸 경계일이 두 칸에 걸친다 — 앞 칸 마지막인가 뒤 칸 첫날인가", date(2026, 9, 20), "답 1", "P3",
         "격자 안의 정의 — 코드는 정본 하나(grid.capture.is_open · 경계일은 두 칸 열림)로 이미 닫혀 있고 답은 그 정의를 바꿀지 여부 · 값 불필요", group="검토지",
         path="grid/capture.py is_open · data/grid/jjokpa_autumn.json stages"),
    Item("R-ⓓB6", "출하 마감 63일 < 수확 창 끝 70일", date(2026, 9, 20), "답 1", "P3",
         "격자 자체 모순 — 두 수 중 하나를 맞추면 닫힌다(지시서 §3 의 P3 예 그대로)", group="검토지",
         path="data/grid/jjokpa_autumn.json decisions.ship_or_store · 수확 창"),
    Item("R-W", "수확 창 50~70일이 이 밭 경험과 맞는가(ⓒ 수확창 · ⓓ W — 같은 물음)", date(2026, 9, 18), "답 1", "P1",
         "이 밭의 경험(지난 가을 며칠에 뽑았나) — 원천에 없다", group="검토지"),
    Item("R-W2", "창을 넘기면 실제로 잎끝 마름 · 도복이 오는가 — 회복 불가인가(ⓒ5 · ⓓ W2 — 같은 물음)", date(2026, 9, 20), "답 1", "P4",
         "회복 가능성 — 표준에도 없고 이 밭 실측도 없다(지시서 §3 의 P4 예 그대로) · 첫 수확 창 뒤에야 잰다", group="검토지"),
)

# ── 도달성 실측 스냅샷(§4) — 측정 시점을 잃으면 사실이 인상이 된다. 컨테이너 망은 정부 원천을 막는다(전례) — 그래서 "미확인" 이다.
REACH_MEASURED_AT = "2026-09-29 23:20 UTC (KST 09-30 08:20) · 세션 컨테이너(에이전트 프록시)"
REACH_TARGETS: tuple[tuple[str, str, str], ...] = (
    # (원천, URL, 이 원천이 닿으면 확정되는 항목)
    ("농사로 열람(재배기술 쪽파)", "https://www.nongsaro.go.kr/portal/ps/psb/psbk/kidofcomdtyDtl.ps?menuId=PS00067", "D-20 · R-ⓒ1~4 · R-ⓐ"),
    ("농사로 API cropEbook", "http://api.nongsaro.go.kr/service/cropEbook/cropEbookLst", "D-20 · R-ⓐ"),
    ("NCPMS SVC51 (http)", "http://ncpms.rda.go.kr/npmsAPI/service?serviceCode=SVC51", "M-15 · U-20 · R-ⓒ1~4"),
    ("NCPMS (https)", "https://ncpms.rda.go.kr/npmsAPI/service", "M-15 · U-20"),
    ("흙토람", "https://soil.rda.go.kr/", "D-20(관수 기준)"),
    ("공공데이터 SoilExam", "https://apis.data.go.kr/1390802/SoilEnviron/SoilExam/V2/getSoilExam", "I-6(검정값 — 참고)"),
    ("기상청 API 허브 kma_sfcdd", "https://apihub.kma.go.kr/api/typ01/url/kma_sfcdd.php", "D-20 관측(참고 — 이미 코드가 쓴다)"),
    ("기상청 날씨누리 1개월 전망", "https://www.weather.go.kr/w/climate/prediction/1month.do", "D-21"),
)
# (URL, HTTP 코드 또는 None, 오류 문면) — 2026-09-29 23:20 UTC 실측. 000 = 연결 자체가 안 됨(프록시) · 403 = 프록시 거부.
REACH_SNAPSHOT: tuple[tuple[str, int | None, str], ...] = (
    (REACH_TARGETS[0][1], None, "연결 안 됨(HTTP 000 · 0.3초)"),
    (REACH_TARGETS[1][1], 403, "프록시 거부"),
    (REACH_TARGETS[2][1], 403, "프록시 거부"),
    (REACH_TARGETS[3][1], None, "연결 안 됨(HTTP 000)"),
    (REACH_TARGETS[4][1], None, "연결 안 됨(HTTP 000)"),
    (REACH_TARGETS[5][1], None, "연결 안 됨(HTTP 000)"),
    (REACH_TARGETS[6][1], None, "연결 안 됨(HTTP 000)"),
    (REACH_TARGETS[7][1], None, "같은 망 — 미시도(www.weather.go.kr 도 정부 원천)"),
)


# ── 판정 규칙(§3) ──
def classify(item: Item) -> Item:
    """P2 는 원천·경로가 둘 다 있어야 · P3 는 고칠 자리가 있어야. 없으면 각각 P4 · P1 로 떨어뜨리고 사유를 남긴다."""
    if item.branch not in BRANCHES:
        raise ValueError(f"{item.id}: 갈래가 P1~P4 가 아니다 — {item.branch!r}")
    if item.branch == "P2" and not (item.source.strip() and item.path.strip()):
        return replace(item, branch="P4", fell="P2 였으나 원천·경로가 없다 → P4(\"어딘가 있을 것\"은 P2 가 아니다)")
    if item.branch == "P3" and not item.path.strip():
        return replace(item, branch="P1", fell="P3 였으나 고칠 자리가 없다 → P1(갈리면 사람 쪽)")
    return item


def reach_status(code: int | None, err: str = "") -> str:
    """§4 — 2xx/3xx 만 도달. 그 밖은 전부 미확인(키 · 차단 · 없음 을 여기서 가르지 않는다 — '없다' 로 쓰지 않는다)."""
    if code is not None and 200 <= code < 400:
        return f"{REACHED}(HTTP {code})"
    detail = err or (f"HTTP {code}" if code is not None else "응답 못 받음")   # '없음' 이라는 낱말을 사유에도 안 쓴다(검사 문자열 겹침 §7.1 4번)
    return f"{UNREACHED}({detail})"


def probe(urls, timeout: int = PROBE_TIMEOUT) -> list[tuple[str, int | None, str]]:
    """발행자 PC 에서 도달성을 다시 잰다 — GET 한 번씩, 본문은 버린다(값을 가져오는 도구가 아니다). 아무것도 쓰지 않는다."""
    out = []
    for u in urls:
        try:
            with urllib.request.urlopen(urllib.request.Request(u, headers={"User-Agent": "agrodss-wo-pb01"}), timeout=timeout) as r:
                out.append((u, int(r.status), ""))
        except urllib.error.HTTPError as e:
            out.append((u, int(e.code), f"HTTP {e.code}"))
        except Exception as e:  # noqa: BLE001 — 오류 종류를 그대로 적는다(미확인 사유)
            out.append((u, None, type(e).__name__))
    return out


# ── 대장 읽기(전수 대조) ──
_DATE = re.compile(r"^(\d{2})-(\d{2})$")


def open_backlog_rows(text: str, year: int = 2026) -> dict[str, tuple[str, str, date | None]]:
    """대장 표에서 상태가 대기·진행·등재 인 행 → {id: (항목, 상태 머리, 등재일)}. 상태 열 위치는 표마다 달라 셀을 훑는다."""
    rows: dict[str, tuple[str, str, date | None]] = {}
    for line in text.splitlines():
        m = re.match(r"^\| ([A-Z]-\d+) \|", line)
        if not m:
            continue
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        state = next((c.strip("*").split("(")[0].strip() for c in cells[1:] if c.strip("*").split("(")[0].strip() in OPEN_STATES), None)
        if state is None:
            continue
        since = None
        for c in cells:
            d = _DATE.match(c)
            if d:
                since = date(year, int(d.group(1)), int(d.group(2)))
                break
        rows[m.group(1)] = (cells[1].strip("*"), state, since)
    return rows


def judged(today: date, backlog_text: str | None = None) -> list[Item]:
    """판정 전수 — 대장의 열린 행 전부가 판정에 있고, 대장 그룹 판정 전부가 열린 행이어야 한다(대장이 바뀌면 판정을 다시 한다)."""
    text = backlog_text if backlog_text is not None else BACKLOG.read_text(encoding="utf-8")
    open_rows = open_backlog_rows(text, today.year)
    mine = {i.id for i in JUDGMENTS if i.group == "대장"}
    missing = sorted(set(open_rows) - mine)
    stale = sorted(mine - set(open_rows))
    if missing or stale:
        raise SystemExit(f"대장과 판정이 어긋난다 — 판정 없는 열린 행 {missing} · 열려 있지 않은 판정 {stale}. 판정을 다시 한 뒤 생성한다(전수 래칫)")
    out = []
    for it in JUDGMENTS:
        if it.group == "대장":
            _, _, since = open_rows[it.id]
            if since and since != it.since:
                raise SystemExit(f"{it.id}: 등재일이 대장({since})과 판정({it.since})에서 다르다")
        out.append(classify(it))
    return out


def counts(items: list[Item]) -> dict[str, tuple[int, int]]:
    """갈래별 (행 수, 문항 수)."""
    c = {b: [0, 0] for b in BRANCHES}
    for it in items:
        c[it.branch][0] += 1
        c[it.branch][1] += it.n
    return {b: (v[0], v[1]) for b, v in c.items()}


def verdict(c: dict[str, tuple[int, int]], weighted: bool = True) -> tuple[str, str]:
    """§5 — P2+P3 ≥ 60% → H1 · P1 과반 → H2 · P4 과반 → H3. 겹치면 P2+P3 우선. 어느 것도 아니면 '판정 조건 미충족'."""
    k = 1 if weighted else 0
    total = sum(v[k] for v in c.values()) or 1
    p23, p1, p4 = (c["P2"][k] + c["P3"][k]) / total, c["P1"][k] / total, c["P4"][k] / total
    if p23 >= 0.6:
        return "H1", f"P2+P3 {p23:.0%} ≥ 60%"
    if p1 > 0.5:
        return "H2", f"P1 {p1:.0%} 과반"
    if p4 > 0.5:
        return "H3", f"P4 {p4:.0%} 과반"
    return "판정 조건 미충족", f"P2+P3 {p23:.0%} · P1 {p1:.0%} · P4 {p4:.0%} — §5 의 세 조건 어느 것도 아니다"


def long_open(items: list[Item], today: date) -> list[Item]:
    return [i for i in items if (today - i.since).days > LONG_OPEN_DAYS]


# ── 보고서 ──
def _pct(a: int, t: int) -> str:
    return f"{a}/{t} ({a / t:.0%})" if t else "0/0"


def render(today: date, backlog_text: str | None = None) -> str:
    items = judged(today, backlog_text)
    c = counts(items)
    rows_total = sum(v[0] for v in c.values())
    n_total = sum(v[1] for v in c.values())
    h_w, why_w = verdict(c, weighted=True)
    h_r, why_r = verdict(c, weighted=False)
    # 보수 판정 — 미도달 P2 를 전부 P4 로 내려도 결론이 같은가(§4: 미도달은 P2 보류 · 확정이 아니다)
    c_cons = {b: list(v) for b, v in c.items()}
    c_cons["P4"] = [c_cons["P4"][0] + c_cons["P2"][0], c_cons["P4"][1] + c_cons["P2"][1]]
    c_cons["P2"] = [0, 0]
    h_c, why_c = verdict({b: (v[0], v[1]) for b, v in c_cons.items()}, weighted=True)
    p2 = [i for i in items if i.branch == "P2"]
    reach = {u: reach_status(code, err) for u, code, err in REACH_SNAPSHOT}
    reached_any = any(s.startswith(REACHED) for s in reach.values())
    longs = long_open(items, today)
    oldest = max((today - i.since).days for i in items)
    # 대장 페이지 「발행자 몫 — 지금」 4건(회차마다 붙는 목록)의 갈래 — 되풀이 목록만 따로 본다
    recurring = ("H-①", "D-20", "D-17", "D-19", "D-21")

    L: list[str] = []
    L.append("# WO-PB-01 — 발행자 응답 병목: 대기 항목 전수 · 갈래 비율 · 외부 정본 도달성 (측정 · 규칙 변경 아님)")
    L.append("")
    L.append(f"기준일 **{today.isoformat()}** · 생성 `python -m scripts.measure_publisher_bottleneck --today {today.isoformat()} docs/wo_pb01_publisher_bottleneck.md` "
             "(검사가 같은 기준일로 다시 그려 대조한다 — 이 파일은 손으로 고치지 않는다 · 판정을 바꾸려면 스크립트의 JUDGMENTS 를 고친다)")
    L.append("")
    L.append("이 문서가 하지 않는 것(지시서 §7): 격자 값을 채우지 않는다 · 임계를 제안하지 않는다 · 대기 항목을 닫지 않는다(P3 도 여기서는 안 고친다) · 규칙을 바꾸지 않는다.")
    L.append("판정은 세션이 했고 **표 전체를 발행자가 한 번에 본다** — 뒤집으실 행은 id 와 갈래만 주시면 된다.")
    L.append("")
    L.append("## 0. 요약")
    L.append("")
    L.append(f"- 열린 항목 **{rows_total}행 · {n_total}문항**(대장 대기·진행·등재 {sum(1 for i in items if i.group == '대장')} · 핸드오버 발행자 몫 "
             f"{sum(1 for i in items if i.group == '핸드오버')} · 검토지 미회신 {sum(1 for i in items if i.group == '검토지')}행/{sum(i.n for i in items if i.group == '검토지')}문항)")
    L.append("- 갈래(문항 단위): " + " · ".join(f"**{b}** {BRANCH_SAID[b]} {_pct(c[b][1], n_total)}" for b in BRANCHES))
    L.append(f"- 판정: **{h_w}** ({why_w}) — 행 단위로도 {h_r}({why_r}) · 미도달 P2 를 전부 P4 로 내려도 {h_c}({why_c}). **세 셈이 같은 쪽을 가리킨다.**")
    L.append(f"- P2 도달성: 원천 {len(REACH_TARGETS)}곳 전부 **{UNREACHED}**(컨테이너 망 차단 · {REACH_MEASURED_AT}) — P2 는 확정이 아니라 **보류** 다. 발행자 PC 에서 `--probe` 한 번이면 확정된다.")
    L.append(f"- 30일 초과: **{len(longs)}건** — 가장 오래된 항목이 {oldest}일(프로젝트가 09-18 에 시작했다 · 이 축은 아직 아무것도 가르지 못한다).")
    L.append("- 다음 한 수: §5.")
    L.append("")
    L.append("## 1. 대기 항목 전수표")
    L.append("")
    L.append("경과일은 기준일 − 등재일. 문항 수는 검토지 장을 한 행으로 묶은 것(비율은 문항 단위와 행 단위 둘 다 낸다). "
             "P2 행은 원천과 접근 경로가 있어야 성립하고(없으면 도구가 P4 로 내린다), P3 행은 고칠 자리가 있어야 성립한다(없으면 P1).")
    L.append("")
    L.append("| id | 무엇을 묻는가 | 등재일 | 경과일 | 막고 있는 것 | 문항 | 갈래 | 근거 | 원천 · 경로(P2) / 자리(P3) |")
    L.append("|---|---|---|---|---|---|---|---|---|")
    for it in items:
        sp = (f"{it.source} — {it.path}" if it.branch == "P2" else (it.path if it.branch == "P3" else ""))
        fell = f" **{it.fell}**" if it.fell else ""
        L.append(f"| {it.id} | {it.ask} | {it.since.strftime('%m-%d')} | {(today - it.since).days} | {it.blocker} | {it.n} | **{it.branch}** {BRANCH_SAID[it.branch]}{fell} | {it.why} | {sp} |")
    L.append("")
    L.append("## 2. 갈래 비율 · H1/H2/H3 판정")
    L.append("")
    L.append("| 갈래 | 행 | 문항 | 문항 비율 |")
    L.append("|---|---|---|---|")
    for b in BRANCHES:
        L.append(f"| {b} {BRANCH_SAID[b]} | {c[b][0]} | {c[b][1]} | {c[b][1] / n_total:.0%} |")
    L.append(f"| 합 | {rows_total} | {n_total} | |")
    L.append("")
    L.append(f"§5 기준 — P2+P3 ≥ 60% → H1 · P1 과반 → H2 · P4 과반 → H3(겹치면 P2+P3 우선). 결과: **{h_w}** — {why_w}. "
             f"행 단위 {h_r}({why_r}). 보수 셈(미도달 P2 → P4) {h_c}({why_c}).")
    L.append("")
    L.append("읽는 법 — H2 라도 P1 이 한 덩어리는 아니다. 넷으로 갈린다:")
    L.append("")
    L.append("- **방향 결정 사슬** D-2 → D-3 · D-7 · D-19 · M-11 (5건이 뿌리 하나에 매달린다 — D-2 하나가 서면 넷이 함께 움직인다)")
    L.append("- **권고가 있는 단독 결정** D-16 · D-17 (「맞다」 한 번이면 닫힌다)")
    L.append("- **발행자 PC 의 상태 · 행위** U-18 · U-22 · I-6 · I-7 · H-① · H-키 · H-채팅 (결정이 아니라 사람의 손 — 세션이 못 잰다)")
    L.append("- **이 밭의 경험 · 다리 B 등재** R-W · R-ⓑ · H-⑦ · H-후보")
    L.append("")
    rec = [i for i in items if i.id in recurring]
    L.append(f"되풀이 목록만 따로 — 대장 페이지 「발행자 몫 — 지금」의 {len(rec)}건: " + " · ".join(f"{i.id} {i.branch}" for i in rec)
             + f" → P2 {sum(1 for i in rec if i.branch == 'P2')}/{len(rec)}. 매 회차 붙어 나오는 목록은 다섯 중 둘이 외부 정본 쪽이다 — 전체 비율(H2)과 되풀이 목록의 인상(H1 에 가까워 보인다)이 다른 이유가 이것이다.")
    L.append("")
    L.append("## 3. P2 도달성 실측 (§4)")
    L.append("")
    L.append(f"측정 시점 **{REACH_MEASURED_AT}**. 원천 호출 → 응답 형태 확인 → 격자 칸 대응 의 세 단계 중 **첫 단계에서 전부 멈췄다**(컨테이너의 에이전트 프록시가 정부 원천을 막는다 — 전례와 같다). "
             "그래서 아래는 전부 미확인이고, \"없음\" 은 한 줄도 없다. 이 표의 상태는 발행자 PC 에서 다시 재야 바뀐다.")
    L.append("")
    L.append("| 원천 | URL | 상태 | 닿으면 확정되는 항목 |")
    L.append("|---|---|---|---|")
    for name, url, for_ids in REACH_TARGETS:
        L.append(f"| {name} | `{url}` | **{reach[url]}** | {for_ids} |")
    L.append("")
    L.append(f"P2 로 판정된 {len(p2)}행({sum(i.n for i in p2)}문항)의 상태: 전부 **P2 보류(미확인)** — 도달이 확인되면 그 다음이 형태 확인이다(§4 둘째 줄: 월 단위 달력 같은 단위 불일치면 P4 로 내린다). "
             f"도달이 하나라도 있었는가: {'예' if reached_any else '아니오'}.")
    L.append("")
    L.append("발행자 PC 에서 재는 법(값을 가져오지 않는다 · 아무것도 쓰지 않는다 · 15초씩):")
    L.append("")
    L.append("```")
    L.append("python -m scripts.measure_publisher_bottleneck --probe")
    L.append("```")
    L.append("")
    L.append("나온 표를 세션에 붙이시면 이 문서의 §3 을 그 측정으로 다시 그린다(측정 시점과 함께).")
    L.append("")
    L.append(f"## 4. {LONG_OPEN_DAYS}일 초과 항목 — 안 닫히는 것")
    L.append("")
    if longs:
        for i in longs:
            L.append(f"- {i.id} {i.ask} — {(today - i.since).days}일")
    else:
        L.append(f"없음. 가장 오래 열린 것이 {oldest}일(09-18 등재 — 프로젝트 첫날). §2 의 '밀린 것 / 안 닫히는 것' 구분은 10-18 이후에야 뜻이 있다 — 그때 이 문서를 다시 생성한다(`--today`).")
    L.append("")
    L.append("## 5. 다음 한 수 하나")
    L.append("")
    L.append("**일괄 결정 화면 하나 — P1 을 권고 기본값과 함께 한 화면에 놓고 줄마다 「맞다 / 다르다(→ 무엇)」 만 찍게 한다. 맨 위는 D-2.**")
    L.append("")
    L.append("이유 한 줄: P1 이 과반(H2)이고 그중 5건이 D-2 하나에 매달려 있는데, 지금 있는 일괄 자리(검토지 파일 · 09-18)는 11일째 답 칸이 비어 있다 — "
             "자리가 없는 것이 아니라 자리가 **파일**이라 화면에서 안 보였다(⑤b 장기 전망 폼이 파일 편집을 화면으로 옮긴 것과 같은 형태).")
    L.append("")
    L.append("이것은 이 문서의 범위 밖(§7 — 대기 항목을 닫지 않는다)이라 **별도 묶음**이다. P2 보류 {0}행은 그 화면과 무관하게 발행자 PC 의 `--probe` 한 번으로 확정/P4 가 갈린다 — 그것은 한 수가 아니라 측정의 나머지다.".format(len(p2)))
    if NEXT_MOVE_BUILT:
        L.append("")
        L.append(f"**[그 뒤]** 이 한 수는 발행자 승인(2026-09-29 · 「모르겠다」 1급 · 출처 표시 · 맨 위 D-2)으로 **세워졌다** — `/me/decisions`({NEXT_MOVE_BUILT}). "
                 "이제 이 측정의 다음은 그 화면의 답이 오는 것이고, 「모르겠다」 가 쌓인 행은 이 표의 갈래를 P1 → P4 로 고친다(사후 교정 경로).")
    L.append("")
    L.append("§6 확인 비용 측정은 H1 일 때만 한다(지시서) — 이번 판정이 H2 라 하지 않는다. 단 되풀이 목록의 P2 둘(D-20 · D-21)은 §6 의 후보로 남는다.")
    L.append("")
    L.append("## 6. 격자 · 원장 바이트 불변")
    L.append("")
    L.append("이 도구는 보고서 경로 하나에만 쓴다. 검사 `tests/test_publisher_bottleneck.py` 가 생성 전후로 `data/` 전체(격자 · 등록부 · 원장)와 대장 파일의 해시를 대조하고, "
             "대장의 열린 항목 수가 생성으로 줄지 않는 것을 본다(§8 3 · 4).")
    L.append("")
    L.append("## 7. 미해결 (지시서 §10 그대로)")
    L.append("")
    L.append("- P2 가 열려도 **P1 은 안 줄어든다** — 이 밭의 특이성은 발행자만 안다. 이 측정의 상한.")
    L.append("- 도달성은 이 컨테이너에서 잴 수 없다(전부 미확인) — 발행자 PC 측정이 오기 전까지 P2 는 보류.")
    L.append("- 두 번째 농장이 들어오면 P1 의 성격이 바뀐다 — 지금 범위 밖.")
    L.append("")
    return "\n".join(L)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="WO-PB-01 발행자 응답 병목 — 측정과 갈래 판정")
    ap.add_argument("out", nargs="?", help="보고서 경로(.md) — 이 경로 하나에만 쓴다")
    ap.add_argument("--today", help="기준일 YYYY-MM-DD(기본 오늘) — 검사는 문서 머리의 기준일로 다시 그린다")
    ap.add_argument("--probe", action="store_true", help="도달성 재측정(발행자 PC) — 표만 찍고 아무것도 쓰지 않는다")
    a = ap.parse_args(argv)
    if a.probe:
        stamp = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
        print(f"도달성 재측정 {stamp}")
        print("| 원천 | 상태 |")
        print("|---|---|")
        for (name, url, _), (_, code, err) in zip(REACH_TARGETS, probe([u for _, u, _ in REACH_TARGETS])):
            print(f"| {name} | {reach_status(code, err)} |")
        return 0
    if not a.out:
        ap.error("보고서 경로가 필요하다(또는 --probe)")
    today = date.fromisoformat(a.today) if a.today else date.today()
    text = render(today)
    Path(a.out).write_text(text, encoding="utf-8")
    print(f"written {a.out} {len(text.encode('utf-8'))}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
