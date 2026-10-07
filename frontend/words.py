# -*- coding: utf-8 -*-
# FILE: frontend/words.py
# ROLE: [발행자 2026-09-21 "이런 답변을 보여 주는 것을 이해할 사람이 얼마나 될까?"] **4층이 쓰는 사람 말 정본 하나.**
#
# 앞 회차에 채팅 카드 한 곳을 고쳤다. §7.5 대로 화면 전체를 세니 **152곳**이었다(HTTP 로 걸어 보이는 글자만 셈).
#
#   /judge   76    격자 15 · 등급 13 · 축 10 · 기준점 6 · 초안 5 · 정본 5
#   /c/…     34    해당 없음 8 · 등급 5 · 격자 4 · 개선 요구 4 · 기준점 3
#   나머지    42    메뉴·탭 이름이 **모든 페이지**에 같은 말을 싣고 있었다(재배 단위 · 불이행 · 개선 요구 · 대장)
#
# 처방은 앞 회차와 **같은 형태**다 — 안쪽 이름(봉투 8종 · 등급 3분류)은 그대로 두고, 4층에서만 사람 말로 옮긴다.
# I-1 의 어휘는 설계의 정본이라 바꾸지 않는다. 바꾸는 것은 **누구에게 무슨 말로 보여 주는가**다.
#
# 이 층에서만 쓴다 — **농가가 쓴 글에는 대지 않는다**(자기가 쓴 말이 바뀌어 돌아오면 그게 더 나쁘다).
from __future__ import annotations

import re

from schema import records as _records      # 요구 대상 어휘의 정본(안쪽 이름) — 사람 말은 아래 표 하나

# 봉투 8종 → 사람 말. 안쪽 이름은 `judge.envelope.KINDS` 가 정본이고 여기서 배반하지 않는다(검사가 전수를 본다).
KIND_SAID = {
    "판단함": "이렇게 보입니다",
    "선택지+대가": "고르실 것이 있습니다",
    "사실 인용": "찾아본 것입니다",
    "판단 불가(데이터)": "아직 모릅니다 — 채우면 답이 나옵니다",
    "판단 불가(지식)": "아직 모릅니다 — 기준이 없습니다",
    "해당 없음": "이번엔 할 일이 아닙니다",
    "예측 불가": "미리 알 수 없습니다",
    "답하지 않음": "답하지 않습니다",
}

# 신뢰 등급 3분류 → 사람 말. '추정' 은 *"근거가 약하다"* 는 뜻인데 그대로 쓰면 농가에게는 아무 말도 아니다.
GRADE_SAID = {"계산": "계산한 값", "관측": "실제로 잰 값", "추정": "짐작"}

# [발행자 2026-09-23] 사진의 찍은 때가 **어디서 왔는지**. 사다리 마지막 칸(`upload_time`)은 *"언제 찍었는지 모른다"* 는
# 뜻이라, 화면이 그것을 말하지 않으면 라벨 없는 대리값이 된다 — 라벨이 붙어야 사실이다(`ingest.media.observed_ladder`).
SHOT_TIME_SAID = {
    "manual": "적어 주신 날짜",
    "file_meta": "사진에 적힌 촬영 시각",
    "file_name": "파일 이름의 때 — 저장·전송 시각일 수 있습니다",     # 발행자 2026-09-24: 카카오톡 파일명은 받은 시각이다
    "upload_time": "올리신 때 — 찍은 때는 사진에 없었습니다",
}


def shot_time(source: str | None) -> str:
    return SHOT_TIME_SAID.get(source or "", source or "")


# [내부 값 전수 2026-10-04] 화면이 **내부 값을 그대로** 낸 세 자리 — 고쳐 달라는 말의 대상(영문 other · grid …) · 사용자 역할(farmer · publisher) · 재배 단위 id(p001-jjokpa-2026f).
# 사람 말 래칫(JARGON)은 **한글 목록**이라 영문 값과 id 를 한 번도 못 잡았다(/improve · /events · /media · /mall 네 꼴에서 id 가 나가고 있었다). 안쪽 어휘는 각 층의 정본이고
# 사람 말은 여기 하나다 — 화면은 값 그대로를 title 에 남긴다(정확함을 안 버린다).
TARGET_SAID = {"grid": "재배 달력", "decision": "판단", "dictionary": "이름 사전", "screen": "화면", "schema": "기록 양식", "input": "들어온 자료", "other": "그 밖"}
assert set(TARGET_SAID) == set(_records.TARGETS), f"요구 대상 어휘와 사람 말 표가 어긋난다: {_records.TARGETS}"
ROLE_SAID = {"farmer": "농가", "publisher": "발행자"}      # ingest.profile.ROLES — 층 때문에 여기서 import 하지 않고 검사가 전수를 본다


def target(t: str | None) -> str:
    return TARGET_SAID.get(t or "", t or "")


def role(r: str | None) -> str:
    return ROLE_SAID.get(r or "", r or "")


def subject_label(sid: str | None) -> str:
    """재배 단위 id → 그 농사의 이름(「괴산 연풍 텃밭 · 쪽파 · 2026 가을」). 모르는 id 는 그대로 둔다(지어내지 않는다).
    [2026-10-04] 표의 목록 칸이 id 를 그대로 냈다 — 농가도 발행자도 p001-jjokpa-2026f 로는 어느 밭의 무엇인지 모른다."""
    from ingest import subjects            # 4층이 모듈 수준에서 ingest 를 들면 층이 뒤집힌다(opened 와 같은 규율)
    if not sid:
        return ""
    s = subjects.by_id(sid)
    return (s or {}).get("label") or sid

# 닫힌 낱말 표 — **측정으로 고른 것만** 넣는다. 긴 것부터 바꾼다(짧은 것이 먼저 물면 뒤가 어그러진다).
SWAPS: tuple[tuple[str, str], ...] = (
    # [대파 걷기 2026-10-04 실측] 받침이 바뀌는 낱말은 조사까지 함께 — 「격자가 서면」 이 「재배 달력가 서면」 으로 나갔다(원장은→일지는 과 같은 축 · 넷을 전수로 셌다: 격자 · 봉투 · 원장 · 등급)
    ("격자가", "재배 달력이"), ("격자를", "재배 달력을"), ("격자는", "재배 달력은"), ("격자로", "재배 달력으로"), ("격자와", "재배 달력과"),
    ("봉투가", "판단이"), ("봉투를", "판단을"), ("봉투는", "판단은"),
    ("원장이", "일지가"), ("원장을", "일지를"),
    ("등급이", "근거가"), ("등급을", "근거를"), ("등급은", "근거는"),
    ("신뢰 등급", "근거"),
    ("등급 계산", "근거: 계산한 값"), ("등급 관측", "근거: 실제로 잰 값"), ("등급 추정", "근거: 짐작"),
    ("격자 칸", "재배 달력 단계"), ("격자 창", "재배 달력 기간"), ("격자", "재배 달력"),
    ("재배 단위에", "이 밭에"), ("재배 단위", "농사"), ("기준점", "심은 날"),
    ("불이행 사유", "못 한 이유"), ("미이행", "아직 안 함"),
    ("개선 요구", "고쳐 달라는 말"), ("정본 대기", "기준이 아직 없음"), ("정본", "기준"),
    # [순서 2026-10-05 실측] 긴 말이 **먼저**다 — 짧은 말이 앞에 있으면 긴 말은 영원히 안 걸린다(차단 지점이 주입 지점보다 앞이면 무효인 것과 같은 축).
    # 전수 53항목 중 둘이 그랬다: 「추론 초안」 → 「추론 적을 것」 · 「미확인 초안」 → 「아직 모름 적을 것」(/judge 가 그렇게 내고 있었다 — 뒤의 말은 말이 아니다).
    ("추론 초안", "검토 전 추론"), ("미확인 초안", "아직 안 넣은 것"),
    ("원장은", "일지는"), ("원장", "일지"), ("초안", "적을 것"), ("봉투", "판단"),     # 조사까지 함께 — "일지은" 이 나왔다(2026-09-26 실측)
    ("창 지남", "기간이 지났습니다"), ("창 밖", "기간이 아닙니다"), ("수확 창", "수확 기간"), ("재판정", "다시 보는 날"),
    # [U-26 2026-09-26] /judge 가 쓰던 말 — 발행자가 계획 대 실제를 확인하러 가는 화면이다(72곳).
    ("쓴 축", "본 자료"), ("없는 축", "없는 자료"), ("입력 축", "넣은 자료"),
    ("필요 축", "필요한 자료"), ("금지 축", "안 쓰는 자료"), ("축 선언", "자료 선언"), ("상한 제약", "넘을 수 없는 선"),
    ("소비자 노출", "손님에게 보이기"), ("3층 산출", "판단"),      # 「추론 초안」 · 「미확인 초안」 은 위로 올렸다(긴 말이 먼저)
    ("품종 미확인", "품종은 아직 모릅니다"), ("미확인", "아직 모름"),
    # 3층 감사 메모(notes)가 쓰는 말 — "축" 한 글자는 다른 낱말 속에도 있으니(건축 · 축산) 문맥이 붙은 꼴만 바꾼다
    ("선택 축", "골라 쓰는 자료"), ("축이 아니라", "자료가 아니라"), ("축으로", "자료로"), ("등급", "근거"),
)
# 자리를 세는 말(`칸 3`)은 표가 아니라 규칙이다 — 숫자가 바뀌므로.
_STAGE_NO = re.compile(r"칸\s*(\d+)")
_ID_TAG = re.compile(r"\s*\((?:[DUNIRMS]-\d+|D-\d+ [^)]*)\)")     # (D-8) 같은 대장 번호 — 농가에게는 아무 뜻이 없다


# 판단이 쓴 자료(축)의 이름 — 안쪽 id 를 화면에 그대로 냈다(`anchor` · `soil_chem`). 정확한 id 는 title 에 남긴다.
AXIS_SAID = {"anchor": "심은 날", "soil_chem": "토양 검정값", "forecast": "일기 예보", "precip": "강수", "temp": "기온",
             "gdd": "쌓인 온도", "daylength": "낮 길이", "soil_water": "토양 수분", "pest_regional": "지역 예찰",
             "pest_history": "이 밭의 병해충 이력", "microclimate": "밭 미기상", "cert": "인증", "observation": "밭에서 본 것",
             "plan.target_date": "납품 날짜"}


def axis(axis_id: str | None) -> str:
    return AXIS_SAID.get(axis_id or "", axis_id or "")


def said(kind: str) -> str:
    """봉투 종류 → 사람 말. 모르는 종류면 그대로 둔다(지어내지 않는다)."""
    return KIND_SAID.get(kind, kind)


def grade(g: str | None) -> str:
    return GRADE_SAID.get(g or "", g or "")


# [WO-ASK-01 §10 2026-10-03] 추론값의 **누가 고칠 수 있는가**(grid.schema.FIXABLE_BY) → 사람 말. 농가 것만 "고칠 수 있다" 고 말한다 —
# 농가가 알 수 없는 것(임계 · 내한 한계)에 고침 요청이 매번 뜨면 ⑦이 깨진다(§10). 어휘는 격자 정본의 것이고 여기서는 말만 바꾼다.
FIXER_SAID = {"농가": "밭에서 보신 것으로 고칠 수 있습니다", "정본": "기준 자료가 와야 바뀝니다", "실측": "재야 바뀝니다"}


def fixer(fixable_by: str | None, inference: bool = True) -> str:
    if not inference:
        return "—"
    return FIXER_SAID.get(fixable_by or "", "검토 전 추론")


def fix_offer(names: list[str]) -> str:
    """위험 경보 답 끝에 붙는 한 줄 — 농가가 고칠 수 있는 추론값만 이름을 부른다(§10 '쓰이는 그 자리에서'). 고침은 '고쳐 달라는 말' 로 들어간다."""
    said = " · ".join(names)
    return (f"「{said}」 {_records.josa(said, '은')} 검토 전 추론이고 밭에서 보시는 분이 고칠 수 있는 것입니다 — 다르면 채팅에 "
            f"'고쳐 주세요: 무엇이 다른지' 한 줄로 적어 주시면 고쳐 달라는 말로 들어갑니다.")


# [WO-ASK-01 §12 2026-10-03] "답했는데 아무것도 안 바뀌면 더 안 쓴다" — 답을 받은 직후 **그 답이 연 판단**을 말한다. 판단 이름은 사람 말 정본에서.
# [전수 2026-10-05] 여기 없으면 등록부 이름으로 떨어지는데, 그 이름 둘이 **안쪽 말**을 싣고 있었다(「배수 경보(칸 4)」 · 「병해충 경보(칸 3)」) —
# 사람 말 표가 그것을 또 고쳐(「4단계」) 같은 문장이 plain() 전후로 달라졌다. 보이는 이름은 **여기가 정본**이다(검사가 등록 결정 전수를 본다).
DECISION_SAID = {"harvest_timing": "수확 시기", "risk_alert": "위험 경보", "material_citation": "자재 인용", "plan_vs_actual": "계획 대 실제",
                 "drainage_alert": "배수 경보(4단계)", "pest_alert": "병해충 경보(3단계)"}


def decision(decision_id: str) -> str:
    if decision_id in DECISION_SAID:
        return DECISION_SAID[decision_id]
    from judge import registry, stage_decisions  # noqa: F401 — M-10 등록분은 등록부 이름(stage_decisions 가 적재 때 등록한다) — 함수 안에서(모듈 수준이면 4층이 3층을 든다)
    d = registry.all_decisions().get(decision_id)
    return d.name if d is not None else decision_id


def waiting(field: str, value: str, observed_at: str = "") -> str:
    """일지에서 읽혔는데 **아직 안 넣은 값**이 이 답을 바꾼다 — 그 사실 한 줄(행동은 카드가 말한다 · 여기서는 왜 이 답이 그 값 없이 나왔는지만).
    [10/07 걷기 2026-10-06] 카드는 한 번만 서고 답은 날마다 나간다 — 그 사이를 이 줄이 메운다."""
    from ingest import parcels, subjects
    word = parcels.FIELD_WORDS.get(field) or subjects.SUBJECT_FIELD_WORDS.get(field, field)
    when = f"일지 {observed_at} 에서" if observed_at else "일지에서"
    return (f"이 답은 {word} 값 없이 낸 것입니다 — {when} 읽은 '{value}' {_records.josa(value, '이')} "
            f"아직 안 들어갔습니다({_places()} 에서 넣으면 다시 답합니다)")


def waiting_many(items: list[tuple[str, str, str]]) -> str:
    """기다리는 값이 **여러 개**면 한 문장으로 — 꼬리(자리 안내)는 한 번만.

    [길이 측정 2026-10-07] 다섯 회차 동안 처방을 쌓고 **농가가 오늘 읽는 길이**를 쟀다: 위험 물음의 답이 502자였고 그 안에서
    「… 아직 안 들어갔습니다(왼쪽 메뉴 … 에서 넣으면 다시 답합니다)」 가 **두 번** 똑같이 나왔다(용도 · 배수 둘 다 기다리는 값이라서).
    늘어난 것은 **정보가 아니라 꼬리**다 — 값 이름과 읽은 값만 다르고 나머지는 같은 말이다. 그래서 값은 다 말하고 꼬리는 한 번만 말한다.
    """
    if not items:
        return ""
    if len(items) == 1:
        return waiting(*items[0])
    from ingest import parcels, subjects
    words_ = [parcels.FIELD_WORDS.get(f) or subjects.SUBJECT_FIELD_WORDS.get(f, f) for f, _v, _d in items]
    reads = " · ".join(f"'{v}'({d})" if d else f"'{v}'" for _f, v, d in items)      # 읽은 날은 그 값의 출처다 — 합치면서 버리지 않는다
    return (f"이 답은 {' · '.join(words_)} 값 없이 낸 것입니다 — 일지에서 읽은 {reads}"
            f"{_records.josa(reads[-1] if reads[-1] != ')' else '것', '이')} 아직 안 들어갔습니다({_places()} 에서 넣으면 다시 답합니다)")


def season_over(day: int, last: int, say: str) -> str:
    """재배 달력이 **끝난 뒤**의 한 줄 — 달력이 어디까지 말하는지와, 농사를 마쳤으면 그 말을 어디에 적는지.

    [앞날 걷기 2026-10-07] 심은 날 + 107일로 걸으니 「놓침 12 — 사유를 묻는다」 와 「수확 지연」 이 **날마다 영구히** 나갔다. 멎게 하는 길은
    있었고(수확 기록 · 마쳤다는 말) **그 길을 말하는 자리가 없었다**. 닫는 것은 사람 몫 그대로이고, 여기서 하는 일은 그 수를 보이게 하는 것뿐이다.
    농가가 적을 말은 **부르는 쪽 정본**에서 받는다(`chat.END_SAY`) — 여기서 예를 지어내면 적어도 안 읽히는 말이 된다(어휘 두 벌 금지 · `not_in_diary` 와 같은 꼴).

    [직렬 게이트 · 같은 날 라이브] 첫 판은 「그 뒤 계획을 못 한 일로 세지 않고」 로 끝났다. 격리 상태에서 **적고 단추까지 눌러 보니**: 수확 지연 알림은
    그 자리에서 멎었는데 **「놓침 12」 는 그대로**였다(마친 날 전의 계획은 여전히 안 한 일이다 — 2026-09-20 처방의 문면 그대로다). 문장은 거짓이 아니었지만
    농가는 *"이러면 멎는다"* 로 읽는다 — 조건(「그 뒤」)을 작게 적으면 약속이 커진다. 그래서 **멎는 것과 남는 것을 둘 다** 말한다. 마친 날 **전에** 못 한 일을
    닫는 것이 맞는지는 판단의 뜻을 바꾸는 일이라 발행자 몫으로 등재했다(세션이 정하지 않는다).
    """
    if day <= last:
        raise ValueError("달력이 끝나지 않았으면 이 말을 하지 않는다 — 끝났는지는 재배 달력이 정한다(grid.schema.past_calendar)")
    return (f"재배 달력은 심은 날부터 {last}일까지 말합니다 — 오늘은 {day}일째입니다. 농사를 마치셨으면 채팅에 '{say}' 처럼 한 줄 "
            f"적어 주시면 수확이 늦었다는 알림이 멎고 마친 날 뒤로는 계획을 못 한 일로 세지 않습니다"
            f"(마친 날 전에 못 한 일은 그대로 남습니다 — 이유를 적으시면 그 자리에 남습니다)")


WINDOW_SAID = {"창 이전": "아직 그 기간 전입니다", "창 안": "오늘은 그 기간 안입니다", "창 지남": "그 기간은 이미 지났습니다"}


def where_in_window(result: dict) -> str:
    """수확 기간 안에서 **오늘이 어디인가** — 3층이 잰 자리(`position`)와 날수를 사람 말로.

    [앞날 걷기 2026-10-07] 11/10 로 미리 걸으니 답이 「수확 기간 2026-10-14 ~ 2026-11-03」 을 그대로 냈다 — 틀린 말은 아니지만 **이미 지난 기간이
    앞일처럼** 읽힌다(그날 위험 쪽은 「수확 창을 7일 넘겼다」 를 알고 있었다). `position` 은 3층에서 줄곧 계산됐고 **농가 줄이 읽지 않았다**(G1).
    발행자 화면은 그 날말을 그대로 찍고 있었으니 소비자가 0 은 아니었다 — 「소비자 0」 으로 적었던 첫 판독을 전수로 고쳤다.
    상대 날수는 글이 아니라 계산이다 — 절대 날짜가 먼저, 상대 말은 괄호에(대장 페이지의 `when()` 과 같은 규율).
    """
    pos = (result or {}).get("position")
    if pos not in WINDOW_SAID:
        return ""
    said = WINDOW_SAID[pos]
    if pos == "창 이전":
        n = int(result.get("days_to_start") or 0)
        return f"{said}({_short_day(result.get('window_start'))} 에 열립니다" + (f" · {_in_days(n)})" if n else ")")
    if pos == "창 지남":
        n = int(result.get("days_past_end") or 0)
        return f"{said}({_short_day(result.get('window_end'))} 에 끝났습니다" + (f" · {n}일 전)" if n else ")")
    return f"{said}({_short_day(result.get('window_end'))} 까지)"


def _short_day(iso: str | None) -> str:
    s = str(iso or "")
    return f"{int(s[5:7])}/{int(s[8:10])}" if len(s) >= 10 else s


def _in_days(n: int) -> str:
    return {1: "내일", 2: "모레"}.get(n) or f"{n}일 뒤"


def not_in_diary(kind: str, count: int, label: str) -> str:
    """아직 일지에 **안 넣은 사건 초안**이 이 답을 바꾼다 — 그 사실 한 줄. `waiting`(안 넣은 *값*)의 사건 판이다.
    문장이 2층에 박혀 있었다(가뭄 답 한 곳) — 자리가 늘면 사람 말이 갈라지므로 여기 하나로 둔다. 단추 말은 부르는 쪽 정본에서 받는다(`chat.confirm_label`)."""
    return not_in_diary_many([(kind, count)], label)


def not_in_diary_many(counts: list[tuple[str, int]], label: str) -> str:
    """안 넣은 기록이 **여러 종류**면 한 문장으로 — 단추 안내는 한 번만.

    [길이 측정 2026-10-07] 같은 자리의 사건 판이다. 미확인 초안이 셋이면 「'일지에 넣기' 를 누르면 판단이 읽습니다」 가 **세 번** 똑같이 나갔고
    할 일 답이 651자가 됐다. 종류와 건수는 다 말하고(덜 말하면 다른 사실이다) 꼬리는 한 번만 말한다.
    """
    rows = [(k, int(n)) for k, n in counts if int(n) > 0]
    if not rows:
        raise ValueError("안 넣은 기록이 없으면 그 말을 하지 않는다 — 0건을 말하는 자리는 없다")
    said = " · ".join(f"{k} {n}건" for k, n in rows)
    head = (f"아직 일지에 넣지 않은 기록이 있습니다({said})" if len(rows) > 1
            else f"아직 일지에 넣지 않은 {rows[0][0]} 기록 {rows[0][1]}건이 있습니다")      # 한 종류면 전과 **같은 문장**이다(바꿀 이유가 없는 쪽은 안 바꾼다)
    return f"{head} — '{label}' {_records.josa(label, '를')} 누르면 판단이 읽습니다"


def _places() -> str:
    from schema import labels as _labels
    return _labels.PLACES["parcel"]


NAMES_SHOWN = 5      # 이보다 길면 앞 다섯과 **전체 수**로 말한다 — 열한 이름을 한 줄에 늘어놓으면 농가가 읽지 않는다(다섯까지는 그대로 센다 — 용도 다섯이 그 경계다)
# [재측정 2026-10-07] 심은 날 소비자가 3 → **11** 로 늘었다(선언이 아니라 측정). 전부 늘어놓으면 한 줄이 160자가 되고, 줄이면 「조건을 덜 말하는」 그 결함이 된다 —
# 그래서 **수를 함께** 말한다(줄이되 몇인지를 숨기지 않는다). 수는 정본의 길이에서 세므로 표가 늘면 문장도 따라 늘어난다.
def _names_said(ids: tuple[str, ...]) -> str:
    names = [decision(d) for d in ids]
    if len(names) <= NAMES_SHOWN:
        return " · ".join(names)
    shown = names[:NAMES_SHOWN]
    return f"{' · '.join(shown)}{_records.josa(shown[-1], '을')} 비롯해 {len(names)}가지"      # 조사도 정본에서(인용 → 을 · 단계) → 를)


def opened(field: str, value: str, pending: bool = False) -> str:
    """밭 정보 값 하나를 넣은 직후의 한 줄 — 그 값을 읽는 판단의 이름(parcels.FIELD_CONSUMERS). 읽는 판단이 없으면 빈 문자열(열렸다고 말하지 않는다 · §5-1 한 쌍).
    [§7.5 지점 2026-10-03] 답을 넣는 자리가 셋(채팅 초안 줄 · 확인 직후 줄 · 밭 정보 폼)이라 문장은 여기 하나다.
    [2026-10-06] 넷째 자리가 생겼다 — **아직 안 넣은 카드**(일지에서 읽어 올린 초안). 그 자리에서 「이것으로」 는 이미 읽는다는 말이 되므로
    `pending=True` 면 「넣으면」 으로 시작한다(조건 없는 안내는 다른 사실이다 — 같은 문장, 다른 때)."""
    from grid import schema as grid_schema
    from ingest import parcels, subjects
    ids = parcels.FIELD_CONSUMERS.get(field) or subjects.SUBJECT_FIELD_CONSUMERS.get(field) or ()   # 밭 정보 값 · 농사(재배 단위) 값 — 같은 문장
    if not ids:
        # [낡음 대조 2026-10-06] 판정이 아닌 소비자가 있는 값은 **빈 문장이 거짓**이다 — 인증 근거를 넣으면 몰 상품의 인증 표기가 그것을 읽는다(측정 정본).
        # 빈 문자열은 「아무 일도 안 생긴다」 로 읽히고, 그러면 적을 이유가 사라진다. 판정 이름은 못 대지만 **무엇이 읽는지는** 말할 수 있다.
        other = parcels.FIELD_OTHER_CONSUMERS.get(field)
        if other:
            who, cond = other
            word = parcels.FIELD_WORDS.get(field, field)
            head = "넣으면" if pending else "이것으로"
            return (f"{head} {word} 값 '{value}' {_records.josa(value, '을')} {who}{_records.josa(who, '이')} 읽습니다 — "
                    f"판정은 이 값을 읽지 않습니다({cond}).")
        return ""
    names = _names_said(ids)
    word = parcels.FIELD_WORDS.get(field) or subjects.SUBJECT_FIELD_WORDS.get(field, field)
    head, tail = ("넣으면", "지금 답은 그 값 없이 낸 것입니다") if pending else ("이것으로", "다음 답부터 그 근거에 실립니다")
    line = f"{head} {names} 판단이 {word} 값 '{value}' {_records.josa(value, '을')} 읽습니다 — {tail}."      # 값이 들어오는 자리(유기 → 「를」 · 무농약 → 「을」)
    if field == "use" and grid_schema.use_key(value):      # [종구 2026-10-03] 용도에 「종구」 — 재배 달력 자체가 종구 기준으로 읽힌다(grid.schema.use_key → apply_use · use_gap)
        line += " 용도에 「종구」 가 있어 재배 달력도 종구 기준으로 읽습니다 — 수확 단계부터는 종구 값이 올 때까지 잎 기준 경보를 내지 않습니다."
    return line


def plain(text: str) -> str:
    """시스템이 만든 문장을 사람 말로. **농가가 쓴 글에는 쓰지 않는다.**"""
    out = _ID_TAG.sub("", text or "")
    out = _STAGE_NO.sub(r"\1단계", out)
    for a, b in SWAPS:
        out = out.replace(a, b)
    return out


# [사람이 쓴 말 2026-10-05 실측] 이 파일 머리의 마지막 줄은 *"농가가 쓴 글에는 대지 않는다"* 인데, 화면이 페이지를 **통째로** plain() 에 넣으면
# 사람이 쓴 글까지 바뀌어 돌아온다. 결정 화면의 「다르다 → 무엇」 메모 한 줄에서 **여섯 곳**이 바뀌었다(측정 2026-10-05):
#   쓴 말     「격자가 아니라 원장을 본다 · 신뢰 등급 추정 · 기준점 칸 3」
#   돌아온 말 「재배 달력이 아니라 일지를 본다 · 근거 추정 · 심은 날 3단계」
# 더 나쁜 것은 그 글이 **세션이 읽는 답**이라는 점이다(「세션에 보낼 것」 묶음) — 바뀐 말이 그대로 작업 기록에 들어가면 쓰지 않은 말이 기록된다.
# 그래서 사람이 쓴 조각은 mine() 으로 싸고 페이지는 plain_outside() 로 낸다. 표는 싸지 않은 자리에서 그대로 살아 있다(양방향 검사가 고정).
MINE_OPEN, MINE_CLOSE = "\x02", "\x03"      # 글자가 아니라 표시 — 화면에는 남지 않는다(plain_outside 가 쪼개며 먹는다)


def mine(text: str) -> str:
    """사람이 쓴 글 — 낱말 표를 대지 않는다. 글 안의 표시 문자는 지운다(쓴 글이 싸는 자리를 속일 수 없게)."""
    return MINE_OPEN + str(text or "").replace(MINE_OPEN, "").replace(MINE_CLOSE, "") + MINE_CLOSE


def plain_outside(text: str) -> str:
    """사람이 쓴 조각(mine)은 그대로 두고 나머지만 사람 말로. 사람이 쓴 글이 실리는 화면은 plain() 이 아니라 이것으로 낸다."""
    parts = re.split(f"[{MINE_OPEN}{MINE_CLOSE}]", text or "")
    return "".join(p if i % 2 else plain(p) for i, p in enumerate(parts))
