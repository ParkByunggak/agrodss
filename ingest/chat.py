# -*- coding: utf-8 -*-
# FILE: ingest/chat.py
# ROLE: [M-13 · I-3 §3 "질의 자체가 관찰"] 채팅 원장 + 분류 + 확인 + 영농일지.
#
#   · 채팅 한 줄은 1층 사실(chat.message)로 원장에 남는다 — 농가 발화는 최종 심급의 재료다.
#   · 분류(classify)는 2층 파생이다. 규칙 기반(사전·어휘·날짜)이고 **제안(drafts)만** 만든다.
#     확인(confirm)해야 사건·관찰·계획·개선 요구 원장에 들어간다 — 시스템이 대신 적지 않는다(대리값 금지).
#   · 날짜가 없는 사건·관찰·계획은 확인 화면이 날짜를 묻는다. 없으면 안 들어간다.
#   · 질문은 3층 봉투로 답한다(judge.run). 등록된 결정이 없으면 '판단 불가(지식)' — 지어내지 않는다.
#   · 영농일지(diary)는 새 원장이 아니다 — 원장들을 날짜로 펼친 것.
#   · 원장 격리: AGRODSS_CHAT_DIR (테스트는 tmp — conftest).
from __future__ import annotations

import json
import os
import re
import uuid
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from ingest import events as ev
from ingest import feedback as fb
from ingest import media, subjects
from schema import records as sch

ROOT = Path(__file__).resolve().parent.parent
RESOLUTION = "cultivation_unit"

EVENT_SYNONYMS: dict[str, tuple[str, ...]] = {
    "파종": ("파종", "심었", "심음", "씨 뿌", "씨뿌", "종구를"), "정식": ("정식", "옮겨 심", "옮겨심"),
    "방제": ("방제", "약 쳤", "약을 쳤", "약쳤", "살포", "뿌렸"), "시비": ("시비", "비료", "거름", "웃거름", "밑거름"),
    "관수": ("관수", "물 줬", "물을 줬", "물줬", "물 주었"), "제초": ("제초", "풀 뽑", "풀뽑", "김매", "풀을 뽑"),
    "예찰": ("예찰", "트랩", "살펴봤", "둘러봤", "살펴보았"), "보식": ("보식", "다시 심", "다시심"),
    "배수": ("배수", "물 빼", "물빼", "도랑", "고랑 정비", "고랑정비"), "수확": ("수확", "캤", "캐서", "캐냈", "뽑았", "뽑아서", "다듬었", "거뒀", "거두었"),
    "납품": ("납품", "보냈", "출하했", "출하 했"), "저장": ("저장", "창고에"), "소독": ("소독",), "정리": ("정리했", "정비했", "걷었"),
}
OBS_WORDS = ("보인다", "보여", "보임", "생겼", "누렇", "누래", "시들", "벌레", "병이", "병 ", "잎이", "잎에", "싹이", "발아", "꽃이",
             "썩", "마름", "진딧물", "굼벵이", "나방", "고랑에 물", "말랐",
             # [발행자 2026-09-19 첫 발화 "오늘 상황은 줄기가 매우 왕성한 모습이다" → 분류 안 됨] 생육 상태 서술 어휘
             "줄기", "뿌리", "잎 ", "잎은", "잎도", "싹", "꽃", "알이", "구가", "왕성", "모습", "상태", "자랐", "자라", "컸다", "크다",
             "작다", "웃자", "쓰러", "누웠", "빽빽", "성글", "고르", "듬성")
PLAN_WORDS = ("예정", "할 것", "하려고", "하려 한다", "계획", "할까 한다", "할 생각", "하겠다", "할게", "해야겠")
# [시점 걷기 2026-09-20] 작기 종료 선언 — 사건 어휘('정리했' · '수확')보다 앞에서 본다. 명시 문구만(원문 '끝났다'류는 사건·관찰과 겹친다)
END_WORDS = ("작기 종료", "작기 끝", "재배 종료", "농사 끝", "농사 종료", "올해 농사 마", "이번 작기 마", "작기를 마", "작기 마감")
# 종료 문구가 **종속절**이면 선언이 아니다 — "작기 끝나기 전에 …" · "농사 끝날 때까지 …"(처방 직후 전수 2026-09-20)
_END_SUBORDINATE = re.compile(r"(끝|종료|마감|마치|마무리)\w*\s*(전에|전까지|기\s*전|때까지|때쯤|무렵|하면)")
_PLAN_RE = re.compile(r"(려고|려 한다|려한다|할 예정|예정|계획|할 것|겠다|겠습니다|겠어요|겠음|할게|해야겠|할 생각|생각\s*(이다|입니다|이에요|임)?\s*$)")
REQ_WORDS = ("틀렸", "틀린", "틀려", "잘못", "고쳐", "바꿔", "개선", "불편", "너무 넓", "너무 좁", "안 맞", "맞지 않", "원한다", "해 줬으면", "해줬으면")
# '이상하' 는 뺐다 — "잎이 이상하다" 는 작물 상태 서술(관찰)이지 시스템 교정 요구가 아니다 (발행자 2026-09-19 "내부 로직으로 분류")
# [칸 3 재측정 2026-09-20 · C15] 순서 주석은 처음부터 "교정 요구(**시스템을 향한** 동사)"라고 적고 있었는데, 구현은 어휘가 있기만
# 하면 걸었다 — 뜻은 맞고 범위가 넓었다. 그래서 밭일 서술이 개선 요구로 샜다(실측: "잘못 심어서 다시 심었다" · "종구를 잘못 심어서
# 다시 심었다"). 안 한 일이 원장에 안 들어가고 계획 대 실제가 놓침으로 세며 되먹임엔 가짜 요구가 쌓인다 — 판독·산출 오염.
# 가르는 표지: **시스템 지시어**가 있으면 교정 요구가 맞다("예찰 기록이 잘못됐다" · "수확 창이 너무 넓다"). 없고, 작업 어휘 +
# 한 일의 표지가 있으면 밭일 서술이다 — 아래 갈래로 흘려보낸다(사건 · 관찰). 종류는 확인에서 사람이 바꿀 수 있다.
SYS_WORDS = ("판정", "분류", "기록", "날짜", "화면", "앱", "시스템", "알림", "경보", "추천", "계획표", "결과",
             "대장", "목록", "카드", "표기", "수확 창", "창이", "답변", "메시지", "일지")
Q_WORDS = ("언제", "얼마나", "할까", "될까", "어떻게", "뭐 해야", "무엇을", "해야 하나", "해야 할까", "괜찮나", "괜찮을까", "되나",
           # [발행자 2026-09-19 라이브 "쪽파를 현재 관리해야 할 항목들을 알려줘요" → 분류 안 됨] 물음표 없는 요청형 — 알려/가르쳐 + 존대 어미
           "알려", "가르쳐", "궁금", "설명해", "나요", "까요", "할지", "해야 하는", "해야 할 항목", "해야 할 일", "할 일이",
           "왜 ", "어디", "어느", "인가", "는가", "은가", "을까", "줘요", "주세요", "줄래", "추천해", "제안해",
           # 전수 측정(2026-09-19 · 40문장)에서 나온 것: "지금 뭘 해야 하죠" · "오늘 상태 어때" · "뭐부터 챙겨야 해". '몇 ' 은 뺐다 — "벌레 먹은 잎이 몇 개" 가 질문으로 샜다
           "뭘 ", "뭘까", "뭐부터", "뭐가 ", "뭐를", "어때", "어떠", "하죠", "이죠", "인지 ")
TOPIC: tuple[tuple[str, tuple[str, ...]], ...] = (
    # [M-10 결정 등록] 구체 결정이 일반 결정보다 앞 — "웃거름 줘야 하나"가 자재 인용으로 새지 않게
    ("ship_or_store", ("출하", "저장할까", "납품할까", "저장")),
    ("top_dressing_1", ("웃거름", "추비")),
    ("base_fertilization", ("밑거름", "기비")),
    ("replant", ("보식", "결주", "안 난", "안 났", "듬성")),
    ("sowing_window", ("파종", "심을 때", "심어도", "언제 심")),
    ("drainage_alert", ("배수", "물 빠", "고랑", "물이 고")),
    ("harvest_timing", ("수확", "캐", "뽑을", "거둘")),
    ("pest_alert", ("벌레", "병", "나방", "파리", "진딧물")),
    ("risk_alert", ("서리", "추위", "얼", "비가", "장마", "위험", "경보", "습")),
    ("material_citation", ("약", "자재", "비료", "공시", "뿌려도", "써도", "쳐도")),
    ("plan_vs_actual", ("해야", "할 일", "계획", "뭐", "무엇", "다음", "관리", "항목", "챙겨", "신경", "지금")),   # "현재 관리해야 할 항목" → 계획 대 실제

)
# [U-16] 피해 어휘 — 갈래는 judge.evolve.RISK_FAMILIES 와 같은 이름(대조가 갈래로 잇는다)
DAMAGE_WORDS: dict[str, tuple[str, ...]] = {
    "서리": ("서리 맞", "서리에", "얼었", "얼어", "냉해", "동해", "서리 피해"),
    "부패": ("썩었", "썩어", "물러졌", "무름", "부패", "녹았"),
    "해충": ("벌레 먹", "벌레가 먹", "파리 유충", "구더기", "갉아", "유충이", "진딧물이", "나방이", "굼벵이가"),
    "병": ("병 걸", "병에 걸", "병이 났", "반점이", "곰팡이", "잎마름", "노균", "탄저"),
}
KIND_LABEL = {"event": "사건", "observation.note": "관찰", "plan.farmer": "계획", "plan.target_date": "납품 계획일",
              "feedback.request": "개선 요구", "decision.noncompliance": "불이행 사유", "subject.end": "작기 종료", "observation.video": "영상",
              "question": "질문", "subject.new": "새 목록"}


class ChatError(ValueError):
    pass


def chat_dir() -> Path:
    return Path(os.environ.get("AGRODSS_CHAT_DIR") or (ROOT / "data" / "chat"))


def index_path() -> Path:
    return chat_dir() / "index.jsonl"


def _now(now: datetime | None) -> datetime:
    """기록 시각은 발행자 PC 의 지역 시각(오프셋 포함) — 화면에 03:33 처럼 UTC 가 찍히면 사람이 시점을 오독한다."""
    return now or datetime.now(timezone.utc).astimezone()


def _append(rec: dict[str, Any]) -> dict[str, Any]:
    rec = sch.stamp(rec)
    index_path().parent.mkdir(parents=True, exist_ok=True)
    with index_path().open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return rec


def list_messages(subject: str) -> list[dict[str, Any]]:
    """같은 id 의 마지막 줄이 현재 상태(확인이 붙으면 한 줄 더). 순서는 첫 등장 순."""
    p = index_path()
    if not p.exists():
        return []
    order: list[str] = []
    latest: dict[str, dict[str, Any]] = {}
    for line in p.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        r = json.loads(line)
        if r.get("subject") != subject:
            continue
        if r["id"] not in latest:
            order.append(r["id"])
        latest[r["id"]] = r
    return [latest[i] for i in order]


def get_message(msg_id: str) -> dict[str, Any] | None:
    p = index_path()
    if not p.exists():
        return None
    cur = None
    for line in p.read_text(encoding="utf-8").splitlines():
        if line.strip():
            r = json.loads(line)
            if r["id"] == msg_id:
                cur = r
    return cur


# ── 날짜 ─────────────────────────────────────────────────────────────────────────
_ISO = re.compile(r"(\d{4})-(\d{1,2})-(\d{1,2})")
_MD = re.compile(r"(\d{1,2})\s*월\s*(\d{1,2})\s*일")
_SLASH = re.compile(r"(?<![\d/.\-])(\d{1,2})/(\d{1,2})(?![\d/])")   # "9/8 트랩 확인" — 빗금 월/일(걷기 실측 2026-09-20: 날짜로 안 읽혀 관찰 메모가 됐다)
_AGO = re.compile(r"(\d+)\s*일\s*전")
_REL = {"오늘": 0, "어제": -1, "그저께": -2, "엊그제": -2, "내일": 1, "모레": 2, "글피": 3}


def parse_day(text: str, today: date, past: bool = False) -> str | None:
    """텍스트의 날짜. past=True(사건 · 관찰 — 이미 일어난 것)면 연도 없는 월/일이 오늘보다 뒤일 때 **지난해**로 읽는다.
    [코드 평가 C6] 1월에 "12월 20일에 심었다"가 올해 12월(미래 사건)이 되던 경로. 계획은 past=False(앞날이 맞다)."""
    m = _ISO.search(text)
    if m:
        try:
            return date(int(m.group(1)), int(m.group(2)), int(m.group(3))).isoformat()
        except ValueError:
            return None
    m = _MD.search(text) or _SLASH.search(text)
    if m:
        try:
            d = date(today.year, int(m.group(1)), int(m.group(2)))
            if past and d > today:
                d = date(today.year - 1, d.month, d.day)
            return d.isoformat()
        except ValueError:
            return None
    m = _AGO.search(text)
    if m:
        return (today - timedelta(days=int(m.group(1)))).isoformat()
    for w, d in _REL.items():
        if w in text:
            return (today + timedelta(days=d)).isoformat()
    return None


# ── 분류(2층 — 제안만) ─────────────────────────────────────────────────────────────
def _event_type(text: str) -> str | None:
    for t, words in EVENT_SYNONYMS.items():
        if any(w in text for w in words):
            return t
    return None


# [검토 잔여 2026-09-20] 명사 어휘 하나("비료" · "거름" · "트랩" · "관수")로 사건이 되던 형태 — "비료 상태가 안 좋다"가 시비 사건이었다.
# 사건은 **한 일**이다: 과거 어미(받침 ㅆ — 았/었/했/줬/쳤/샀/캤…) · 습니다 · 완료/끝/마침 · 날짜(오늘 · 9월 10일 · 3일 전) 중 하나가 있어야 한다.
# 말뭉치 사건 13문장은 전부 과거 어미가 있었고(실측), "오늘 파종" · "9월 10일 방제" · "방제 완료"는 날짜·완료로 남는다.
_DONE_SUFFIX = re.compile(r"[가-힣]습니다|완료|끝냈|마쳤|마침|끝\s*$|함\s*$")


_NOT_PAST_SSANG = ("겠", "있", "없")   # 받침 ㅆ 이지만 과거가 아니다 — 하겠습니다(앞날) · 있다/없다(현재 서술)


def _past_ending(text: str) -> bool:
    """**한 일의 어미만** 본다 — 받침 ㅆ 과거형 · 완료 표현. 날짜·'내일' 같은 시각 표지는 안 센다.

    [처방 직후 전수 2026-09-20] 사건 갈래의 `_done_evidence` 는 시각 표지까지 세는 넓은 신호라 그 자리에선 맞지만,
    *"이건 한 일이지 계획이 아니다"* 를 가르는 데 쓰면 **"내일 웃거름 주려고"가 한 일이 된다**(말뭉치 래칫이 잡았다).
    받침 ㅆ 도 그대로 쓰면 **"다음 주에 트랩 확인하겠습니다"** 가 한 일이 된다 — '겠' 의 받침이 ㅆ 라서다(래칫이 또 잡았다).
    그래서 이 함수는 사건 갈래와 **따로** 선다: `_done_evidence` 의 동작은 건드리지 않는다.
    """
    for ch in text:
        if "가" <= ch <= "힣" and (ord(ch) - 0xAC00) % 28 == 20 and ch not in _NOT_PAST_SSANG:
            return True
    return bool(_DONE_SUFFIX.search(text) and not re.search(r"겠습니다", text))


def _done_evidence(text: str) -> bool:
    if any((ord(ch) - 0xAC00) % 28 == 20 for ch in text if "가" <= ch <= "힣"):   # 받침 ㅆ = 과거 어미
        return True
    if _DONE_SUFFIX.search(text):
        return True
    return bool(_ISO.search(text) or _MD.search(text) or _SLASH.search(text) or _AGO.search(text) or any(w in text for w in _REL))


# [발행자 2026-09-20 "쪽파 포장에는 웃거름 주지 않고 수분공급만 …. 그 근거는 토양검정 상태를 기준으로 함"]
# 사건 어휘 + **부정**은 사건이 아니라 불이행 사유다(I-3 §5 "안 따른 이유가 조언보다 값지다"). 쪽파는 사례일 뿐이다 — 작업 종류는
# EVENT_SYNONYMS(작목 공통), 계획 작업·계획일은 그 재배 단위의 격자 계획표에서 잇는다(_attach_plan). 작목별 분기는 없다.
#   · 부정은 사건 어휘 **바로 뒤**에서만 본다 — "비가 안 와서 물 줬다"의 '안'은 관수를 부정하지 않는다.
#   · '안/못 + 동사' 는 표지(§)로 접어 "약 안 쳤다"에서도 방제 어휘가 잡히게 한다(어휘 사이에 부정이 끼는 한국어 형태).
# [검토 2026-09-20 ②] 접기는 '안/못 + **동사**'에만 — "비료 상태가 안 좋다"의 '안 좋'을 접으면 시비 부정이 된다. 동사 첫 글자 목록(보 는 피해 "안 보인다")
_VERB_HEAD = "했줬쳤함줌하주치뿌심캐뽑걷보되돼썼쓰넣넜줍얼썩먹물녹걸맞"   # 뒤 여덟은 피해 동사(얼었 · 썩었 · 먹 · 물러 · 녹 · 걸 · 맞)
_NEG_FOLD = re.compile(rf"(?<![가-힣])(안|못)(?:\s+(?=[{_VERB_HEAD}])|(?=[{_VERB_HEAD}]))")
# 부정은 사건 어휘 **바로 뒤**의 서술어에 붙어야 한다: 어휘 뒤 한 덩이(조사·어미)에 과거 표지(았/었/했…)가 없고, 사이 토큰은 동사 어간 두 글자까지.
# "물 줬는데 충분하지 않다" · "수확했는데 많지 않다"는 이미 한 일이다 — 뒤의 '지 않'은 다른 서술어의 부정(검토 2026-09-20 ② 실측)
_PAST = "았었했줬쳤캤봤뒀냈"
# 사이 토큰 = 어간 두 글자 + 조사 하나까지("트랩 확인은 §했다" — 걷기 실측 2026-09-20: 조사 '은'이 붙자 창이 못 봐 안 한 예찰이 **사건**이 됐다)
_NEG_AFTER = re.compile(rf"^(?![^\s]*[{_PAST}])[^\s]*\s*(?:[가-힣]{{1,2}}[은는을를이가도]?\s*)?(?:지\s*않|지\s*못|§|않|생략|건너뛰|거른다|걸렀)")
_PAST_WORD = re.compile(rf"[{_PAST}]$")
_ALT_AFTER = re.compile(r"(대신|만\s|만[가-힣]|해\s?줌|해\s?준다|하고 있|하는 중)")   # '했다'는 넣지 않는다 — "생략했다"의 어미가 대신 한 일로 읽힌다(실측)


def _negated_task(text: str) -> tuple[str, int] | None:
    """(부정된 작업 종류, 부정 표현 끝 위치) — 사건 어휘 바로 뒤에 부정이 붙은 첫 종류. 없으면 None."""
    norm = _NEG_FOLD.sub("§", text)
    for et, words in EVENT_SYNONYMS.items():
        for w in words:
            m = re.search("§?".join(re.escape(ch) for ch in w), norm)
            if not m:
                continue
            if "§" in m.group(0):
                return et, m.end()
            if _PAST_WORD.search(w):
                continue                     # "물 줬" · "약 쳤" — 이미 한 일. 뒤에 오는 '지 않'은 다른 서술어의 부정이다(§ 가 안에 끼는 형태만 부정)
            a = _NEG_AFTER.match(norm[m.end():])
            if a:
                return et, m.end() + a.end()
    return None


def _plan_row_for(subject_id: str, et: str, today: date, stated: str | None = None) -> dict[str, Any] | None:
    """부정된 작업 종류 → 그 재배 단위의 계획표(계획 대 실제 봉투)에서 같은 종류의 미완 작업 한 줄. 작목 무관 — 격자가 무엇이든 그 격자의 줄이다.
    이행된 줄은 제외. 농가가 날짜를 말했으면(stated) 그 날에 가장 가까운 줄, 아니면 지난 것(놓침·미이행)을 먼저, 없으면 가장 가까운 예정.
    계획표가 없으면(기준점 없음 등) None."""
    from judge import run as judge_run   # answer() 와 같은 규율 — 3층 봉투만 받는다
    e = next((x for x in judge_run.judgments_for(subject_id, today=today) if x.decision_id == "plan_vs_actual"), None)
    if e is None or e.kind != "판단함":
        return None
    words = EVENT_SYNONYMS.get(et, ())
    rows = [r for r in (e.result or {}).get("rows", []) if r.get("status") not in ("이행", "사유 기록됨") and any(w in (r.get("task") or "") for w in words)]
    if not rows:
        return None
    if stated:
        sd = date.fromisoformat(stated)
        return min(rows, key=lambda r: abs((date.fromisoformat(r["work_date"]) - sd).days))
    past = [r for r in rows if (r.get("work_date") or "") <= today.isoformat()]
    return max(past, key=lambda r: r["work_date"]) if past else min(rows, key=lambda r: r["work_date"])


def _attach_plan(subject_id: str, drafts: list[dict[str, Any]], today: date) -> list[dict[str, Any]]:
    """불이행 초안에 계획표의 작업명·계획일을 잇는다(분류기는 재배 단위를 모른다 — 여기서만 잇는다). 계획표에 없으면 needs 로 남긴다.
    [검토 2026-09-20 ①] 날짜를 말한 발화("9월 16일에 … 안 줬다")도 잇는다 — 전에는 날짜가 있으면 건너뛰어 작업명이 종류 이름('시비')으로
    남았고, 그 사유는 계획표 줄·단계 결정과 영영 안 맞았다. 말한 날짜에 가장 가까운 줄을 잇고 계획일은 그 줄의 것, 말한 날짜는 사유(원문)에 남는다."""
    out = []
    for d in drafts:
        if d.get("kind") == "decision.noncompliance" and d.get("planned_task") == d.get("task_type"):
            row = _plan_row_for(subject_id, d["task_type"], today, stated=d.get("planned_day"))
            d = dict(d)
            if row:
                d.update(planned_task=row["task"], planned_day=row["work_date"], needs=[],
                         why=d["why"] + f" · 계획표 '{row['task']}'({row['work_date']} · {row.get('status')})에 맞췄다")
            elif not d.get("planned_day"):
                d["why"] += " · 계획표에 같은 종류의 미완 작업이 없다 — 계획일을 적는다"
        out.append(d)
    return out


NO_DAMAGE = "없음"
# 피해 어휘 뒤 부정 · '없' — 사건 어휘와 같은 창이되 두 토큰까지 본다("얼어 죽은 게 없다"). 긍정 피해 문장의 뒤에는 이 형태가 없다(말뭉치)
# [검토 2026-09-20 ③] 사이 토큰은 두 글자짜리 둘까지("얼어 죽은 게 없다") — "얼어서 상품성이 없다"의 '상품성이'는 피해가 **있었다**는 문장이다.
# '할 수 없다'의 없 은 불능이지 부재가 아니다("얼어붙어서 걷을 수 없었다") — 수 뒤의 없 은 안 본다.
_NEG_DMG = re.compile(r"^[^\s]*\s*(?:[가-힣]{1,2}\s*){0,2}(?:지\s*않|지\s*못|§|않|(?<!수)(?<!수\s)없)")


def _damage_risk(text: str) -> str | None:
    """피해 갈래 · '피해'(갈래 미상) · NO_DAMAGE(피해 어휘 + 부정 — 사건이 아니다) · None.
    [§7.5 처방 직후 전수 2026-09-20] 사건 어휘의 부정을 고친 직후 같은 형태를 세니 피해 갈래 13문장 중 7건이 "서리에 안 얼었다" ·
    "피해 없음"을 **피해 사건**으로 읽었다 — 그 사건은 경보↔피해 대조(evolve)에 적중으로 들어간다. 같은 규칙을 여기에도 둔다.
    [검토 2026-09-20 ④] 갈래 전부를 본다 — 한 갈래가 부정이고 다른 갈래가 긍정이면("벌레 먹은 잎은 없고 곰팡이가 폈다") 긍정 갈래가 이긴다.
    전에는 사전 순서에서 먼저 걸린 갈래의 부정으로 끝나 실제 피해를 잃었다."""
    norm = _NEG_FOLD.sub("§", text)
    m = re.search("피해", norm)
    if m and _NEG_DMG.match(norm[m.end():]):
        return NO_DAMAGE                     # "서리 맞았는데 피해는 없다" — 피해 없음을 **명시**한 문장이 갈래 어휘보다 앞선다
    negated = False
    for fam, words in DAMAGE_WORDS.items():
        for w in words:
            mm = re.search("§?".join(re.escape(ch) for ch in w), norm)
            if not mm:
                continue
            if "§" in mm.group(0) or _NEG_DMG.match(norm[mm.end():]):
                negated = True
                break
            return fam
    if m:
        return "피해"
    return NO_DAMAGE if negated else None


def _farm_work_not_a_request(t: str) -> bool:
    """[C15] 교정 어휘가 있어도 **밭일 서술**이면 개선 요구가 아니다.

    시스템 지시어가 하나라도 있으면 교정 요구가 맞다(그쪽이 우선 — 옛 판정을 지킨다). 없고, 작업 어휘와
    한 일의 표지가 둘 다 있으면 농가가 자기 일을 말한 것이다. 둘 중 하나만으로는 안 가른다:
    작업 어휘만 보면 "수확 창이 너무 넓다"가 새고, 한 일의 표지만 보면 "판정이 잘못됐다"가 샌다(둘 다 실측).
    """
    if any(w in t for w in SYS_WORDS):
        return False
    return bool(_event_type(t)) and _past_ending(t)


def classify(text: str, today: date) -> list[dict[str, Any]]:
    """발화 → 초안 목록. 하나도 못 나누면 [] (되묻는다). 초안은 확인 전까지 아무 원장에도 안 들어간다."""
    t = text.strip()
    if not t:
        return []
    day = parse_day(t, today)                      # 계획 — 앞날이 맞다
    day_past = parse_day(t, today, past=True)      # 사건 · 관찰 · 피해 — 이미 일어난 것(C6: 연도 없는 월/일이 오늘보다 뒤면 지난해)
    # [발행자 2026-09-19] "질문을 분석하고 그 성격을 분류해서 내부 로직으로" — 사람에게 종류를 고르라고 넘기지 않는다.
    # 순서: 교정 요구(시스템을 향한 동사) → 질문(물음표 · 의문 · 요청형) → 계획 → 피해 → 사건 → 관찰 어휘 → 서술문은 관찰 메모.
    # 종류는 규칙이 정하고 내용(날짜 · 사건 종류)은 지어내지 않는다 — 없으면 needs 로 남긴다. 확인에서 사람이 종류를 바꿀 수 있다.
    if any(w in t for w in REQ_WORDS) and not _farm_work_not_a_request(t):
        return [{"kind": "feedback.request", "text": t, "target": "other", "why": "교정·요구 어휘"}]
    if "?" in t or any(w in t for w in Q_WORDS):
        return [{"kind": "question", "why": "물음표·의문·요청형 어휘"}]
    et = _event_type(t)
    # [처방 직후 전수 2026-09-20 · C15 형태] 교정 어휘를 고친 직후 같은 형태를 다른 갈래에서 셌다 — **갈래 어휘가 밭일 서술 안에
    # 들어 있으면 그 갈래가 사건보다 먼저 가로챈다**. 실측: "계획대로 웃거름을 줬다" · "예정대로 파종했다" → 계획(한 일이 계획이 된다).
    # 계획은 앞날이고 한 일은 사건이다 — **한 일의 표지 + 작업 어휘**가 있으면 계획 갈래를 비켜 간다(계획 어휘는 부사로 쓰인 것).
    if (any(w in t for w in PLAN_WORDS) or _PLAN_RE.search(t)) and not (et and _past_ending(t)):
        if any(w in t for w in ("납품", "출하")):
            return [{"kind": "plan.target_date", "target_date": day, "note": t, "why": "납품·출하 + 계획 어휘",
                     "needs": [] if day else ["target_date"]}]
        return [{"kind": "plan.farmer", "task": et or t[:60], "planned_day": day, "note": t, "why": "계획 어휘",
                 "needs": [] if day else ["planned_day"]}]
    if any(w in t for w in END_WORDS) and not _END_SUBORDINATE.search(t):
        # [처방 직후 전수 2026-09-20] "작기 끝나기 **전에** 웃거름을 줬다"가 작기 종료 초안이 됐다 — 종료 문구가 종속절에 있는데
        # 선언으로 읽힌다. 확인하면 그 재배 단위가 닫히고 그날 뒤 계획을 놓침으로 안 센다(되돌리는 길은 발행자 몫) — 이 갈래는
        # 잘못 걸릴 때의 대가가 가장 크다. '전에 · 전까지 · 기 전' 이 뒤따르면 선언이 아니다.
        # [시점 걷기 2026-09-20] 작기 종료 — 상태를 바꾸는 길이 없어 시즌 뒤에도 '놓침 — 사유를 묻는다'가 계속 났다. 사건(정리·수확)과 다르다:
        # 그 재배 단위의 계획 대 실제를 닫는 선언이다. 종료일은 말한 날짜, 없으면 오늘(확인에서 고친다)
        return [{"kind": "subject.end", "ended_at": day_past or today.isoformat(), "note": t,
                 "why": "작기 종료 어휘 — 확인하면 이 목록이 '종료'가 되고 그날 뒤 계획은 놓침으로 세지 않는다", "needs": []}]
    neg = _negated_task(t)
    if neg:
        # 사건 어휘 + 부정 = 하지 않았다는 사실과 그 이유(원문이 사유다). 종류만 정하고 계획 작업·계획일은 send() 가 계획표에서 잇는다
        et_neg, end = neg
        drafts: list[dict[str, Any]] = [{"kind": "decision.noncompliance", "task_type": et_neg, "planned_task": et_neg, "planned_day": day_past,
                                         "reason": t, "why": f"사건 어휘 + 부정 → {et_neg} 불이행 사유(원문이 사유)",
                                         "needs": [] if day_past else ["planned_day"]}]
        if _ALT_AFTER.search(t[end:]):
            # 부정 뒤에 대신 한 일이 이어진다("… 주지 않고 수분공급만 …") — 그 관행은 관찰 메모로도 남길 수 있다(선택 · 원문 그대로)
            drafts.append({"kind": "observation.note", "text": t, "observed_at": day_past or today.isoformat(),
                           "why": "불이행 뒤에 이어진 실행 서술 — 관행을 관찰 메모로도 남긴다(선택)", "needs": []})
        return drafts
    dmg = _damage_risk(t)
    if dmg == NO_DAMAGE:
        # 피해 어휘 + 부정 = 피해가 **없었다**는 관찰. 사건으로 두면 경보↔피해 대조가 적중으로 센다(되먹임 오염)
        return [{"kind": "observation.note", "text": t, "observed_at": day_past or today.isoformat(),
                 "why": "피해 어휘 + 부정 → 피해 없음 관찰(사건이 아니다 · 경보 대조에 안 들어간다)", "needs": []}]
    if dmg:
        # [U-16] 피해는 사건이되 무엇의 피해인지(risk)가 있어야 경보와 대조된다. '피해'만 있고 갈래가 없으면 확인 화면이 묻는다
        risk = None if dmg == "피해" else dmg
        return [{"kind": "event", "type": ev.DAMAGE_TYPE, "observed_at": day_past or today.isoformat(), "risk": risk, "note": t,
                 "why": f"피해 어휘 → {risk or '갈래 미상'}", "needs": [] if risk else ["risk"]}]
    if et and _done_evidence(t):
        return [{"kind": "event", "type": et, "observed_at": day_past, "note": t, "why": f"사건 어휘 → {et}",
                 "needs": [] if day_past else ["observed_at"]}]
    if et:
        # 사건 어휘는 있는데 한 일의 표지가 없다("비료 상태가 안 좋다" · "웃거름 시기다") — 상태 서술이다. 사건이면 확인에서 '다른 종류'로 바꾼다
        return [{"kind": "observation.note", "text": t, "observed_at": day_past or today.isoformat(),
                 "why": f"'{et}' 어휘는 있으나 한 일의 표지(과거 어미 · 날짜 · 완료)가 없어 관찰 메모로 제안(사건이면 종류를 바꾼다)", "needs": []}]
    if any(w in t for w in OBS_WORDS):
        return [{"kind": "observation.note", "text": t, "observed_at": day_past or today.isoformat(),
                 "why": "관찰 어휘(날짜 없으면 오늘 본 것으로 제안 — 확인에서 고친다)", "needs": []}]
    # 아무 어휘도 안 걸린 서술문 — 농가가 밭에서 한 말은 관찰 메모(원문 그대로)로 제안한다. 내용을 지어내지 않고 종류만 정한다
    return [{"kind": "observation.note", "text": t, "observed_at": day_past or today.isoformat(),
             "why": "서술문 — 사건·계획·질문 어휘가 없어 관찰 메모로 제안(원문 그대로 · 종류는 확인에서 바꾼다)", "needs": []}]


# ── 질문 → 3층 봉투 ─────────────────────────────────────────────────────────────────
def topic_of(text: str) -> str | None:
    for did, words in TOPIC:
        if any(w in text for w in words):
            return did
    return None


def answer(subject: dict[str, Any], text: str, today: date) -> str:
    from judge import run as judge_run   # 4층 화면과 같은 규율 — 3층 봉투만 받는다
    did = topic_of(text)
    if not did:
        return "판단 불가(지식) — 이 질문에 대응하는 결정이 등록돼 있지 않다. 지어내지 않는다. (수확 시기 · 위험 경보 · 자재 · 계획 대 실제 는 답한다)"
    envs = judge_run.judgments_for(subject["id"], today=today)
    e = next((x for x in envs if x.decision_id == did), None)
    if e is None:
        return "판단 불가(데이터) — 이 목록은 아직 판정을 낼 재료(기준점·격자)가 없다"
    return summarize_envelope(e)


def summarize_envelope(e: Any) -> str:
    r = e.result or {}
    head = f"[{e.kind}]"
    if e.kind != "판단함" and e.kind != "사실 인용":
        why = r.get("why") or ""
        miss = " · ".join(f"{m.get('axis')}: {m.get('who_can_fill')}" for m in (e.missing or []))
        return f"{head} {why}" + (f" — 채울 사람: {miss}" if miss else "")
    if r.get("summary") and e.decision_id not in ("harvest_timing", "risk_alert", "material_citation", "plan_vs_actual"):
        caps = " · ".join(f"상한: {c.get('name')}({c.get('basis')})" for c in (e.caps or []))
        return f"{head} {r['summary']} · 등급 {e.grade}" + (f" · {caps}" if caps else "")
    if e.decision_id == "harvest_timing":
        return (f"{head} 수확 창 {r.get('window_start')} ~ {r.get('window_end')} (±{r.get('error_days')}일) · 등급 {e.grade} · "
                f"{r.get('basis', '')} · {r.get('final_say', '')}")
    if e.decision_id == "risk_alert":
        al = r.get("alerts") or []
        body = " / ".join(f"{a.get('level')} {a.get('risk')}({a.get('stage')})" for a in al) or "지금 창에 경보 없음"
        return f"{head} {body} · 등급 {e.grade} · 재판정 {e.revisit_at}"
    if e.decision_id == "material_citation":
        fams = r.get("cited_families")
        n = fams if isinstance(fams, int) else len(fams or [])
        return f"{head} {r.get('stage', '')} · 공시 자재 계열 {n}건 인용 — 효능 보증 아님. 화면 /judge 에 목록"
    if e.decision_id == "plan_vs_actual":
        # [발행자 2026-09-19 "현재 관리해야 할 항목"] 지금 것이 먼저다 — 마감 안 미이행 → 다음 예정 → 놓침(사유). 옛 놓침 6건만 보이던 표현 층 결함
        rows = r.get("rows") or []
        by = {k: [x for x in rows if x.get("status") == k] for k in ("미이행", "예정", "놓침")}
        parts = []
        if by["미이행"]:
            parts.append(f"지금 할 것(마감 안) {len(by['미이행'])}: " + " · ".join(f"{x.get('task')}(~{(x.get('deadline_date') or '')[5:]})" for x in by["미이행"]))
        if by["예정"]:
            parts.append(f"다음 예정 {len(by['예정'])}: " + " · ".join(f"{x.get('task')}({(x.get('work_date') or '')[5:]})" for x in by["예정"][:3]))
        ask = r.get("ask_reason") or []
        if by["놓침"]:
            parts.append(f"놓침 {len(by['놓침'])}" + (f" — 사유를 묻는다: {', '.join(a.get('task', '') for a in ask)}" if ask else ""))
        return f"{head} " + (" / ".join(parts) or "밀린 것 없음 · 다음 예정 없음")
    return f"{head} {json.dumps(r, ensure_ascii=False)[:300]}"


# ── 보내기 · 확인 ───────────────────────────────────────────────────────────────────
INPUT_MODES = ("text", "voice", "file")


def send(subject_id: str, text: str, today: date | None = None, now: datetime | None = None,
         role: str = "farmer", retry_of: str | None = None, edit_of: str | None = None,
         input_mode: str = "text", media_refs: list[dict[str, Any]] | None = None) -> tuple[dict[str, Any], dict[str, Any] | None]:
    """발화 1건 → (내 메시지, 시스템 답) . 분류 초안은 메시지에 붙고 답은 별도 메시지.
    retry_of / edit_of 는 '다시 시도' · '편집' 의 출처 메시지 — 원문은 지우지 않고 새 줄로 잇는다(원장은 append-only).
    input_mode=voice 는 브라우저 음성 인식에서 온 텍스트(D-15) — 오인식 교정은 '편집'으로."""
    s = subjects.by_id(subject_id)
    if not s:
        raise ChatError(f"없는 목록: {subject_id}")
    text = (text or "").strip()
    media_refs = media_refs or []
    if not text and media_refs:
        text = "[반입] " + " · ".join(f"{r.get('id')} {r.get('file', '')}" for r in media_refs)
        input_mode = "file"
    if not text:
        raise ChatError("빈 발화")
    if input_mode not in INPUT_MODES:
        raise ChatError(f"입력 방식은 {' · '.join(INPUT_MODES)} 중 하나")
    for ref in (retry_of, edit_of):
        if ref and not get_message(ref):
            raise ChatError(f"없는 메시지를 잇는다: {ref}")
    today = today or date.today()
    ts = _now(now).isoformat(timespec="seconds")
    drafts = _attach_plan(subject_id, classify(text, today), today)   # 불이행 초안만 계획표(재배 단위별)에 잇는다
    rec: dict[str, Any] = {"id": f"msg_{uuid.uuid4().hex[:12]}", "kind": "chat.message", "subject": subject_id, "role": role, "text": text[:2000],
                           "observed_at": today.isoformat(), "recorded_at": ts, "source": role, "resolution": RESOLUTION,
                           "drafts": drafts, "confirmed_refs": [], "input_mode": input_mode}
    if retry_of:
        rec["retry_of"] = retry_of
    if edit_of:
        rec["edit_of"] = edit_of
    if media_refs:
        rec["media_refs"] = [r.get("id") for r in media_refs]
    msg = _append(rec)
    media_line = ""
    if media_refs:
        media_line = "반입됨 " + " · ".join(f"{r.get('id')}(관측 {str(r.get('observed_at', ''))[:16]})" for r in media_refs) + " — 영상·사진 원장에 들어갔다. "
    if media_refs and not drafts:
        reply_text = media_line + "설명을 함께 적으면 사건·관찰로도 분류한다."
    elif drafts and drafts[0]["kind"] == "question":
        reply_text = answer(s, text, today)
    elif drafts:
        d = drafts[0]
        need = d.get("needs") or []
        reply_text = f"{KIND_LABEL[d['kind']]}(으)로 읽었다 — {d['why']}. " + ("날짜를 넣고 " if need else "") + "확인하면 원장에 들어간다. 아니면 다른 종류를 고른다."
        if len(drafts) > 1:
            reply_text += " 초안 " + " · ".join(f"{n + 1}) {KIND_LABEL.get(x['kind'], x['kind'])}" for n, x in enumerate(drafts)) + " — 각각 따로 확인한다."
    else:
        # [발행자 2026-09-21] 종류를 **사람에게 묻지 않는다** — 규칙이 못 고르면 시스템이 관찰 메모로 정한다(내용은 원문 그대로,
        # 지어내지 않는다). 사람은 초안의 '다른 종류' 로 고친다. 빈 발화는 위에서 이미 거부되므로 여기는 사실상 닿지 않지만,
        # **닿더라도 묻지 않는다**는 것이 이 자리의 약속이다(규칙이 넓어질 때 조용히 물음으로 되돌아가지 않게).
        drafts = [{"kind": "observation.note", "text": text, "observed_at": today.isoformat(),
                   "why": "규칙이 종류를 못 정했다 — 관찰 메모로 둔다(원문 그대로). 다른 종류로 고칠 수 있다", "needs": []}]
        msg["drafts"] = drafts
        _append(dict(msg))
        d = drafts[0]
        reply_text = f"{KIND_LABEL[d['kind']]}(으)로 읽었다 — {d['why']}. 확인하면 원장에 들어간다."
    if media_refs and drafts:
        reply_text = media_line + reply_text
    reply = _append({"id": f"msg_{uuid.uuid4().hex[:12]}", "kind": "chat.message", "subject": subject_id, "role": "system", "text": reply_text,
                     "observed_at": today.isoformat(), "recorded_at": ts, "source": "computed:chat", "resolution": RESOLUTION,
                     "drafts": [], "confirmed_refs": [], "reply_ref": msg["id"]})
    return msg, reply


def request_improvement(reply_id: str, text: str = "", now: datetime | None = None) -> tuple[dict[str, Any], dict[str, Any]]:
    """답변 아래 '개선 요구' — 그 답(시스템 메시지)을 겨냥한 feedback.request 를 바로 접수하고, 접수 사실을 대화에 남긴다.
    사람이 버튼을 눌러 낸 요구라 초안·확인 단계가 없다(다리 B: 사용자가 직접 말한 교정은 오탐일 수 없다)."""
    m = get_message(reply_id)
    if not m or m.get("role") != "system":
        raise ChatError("개선 요구는 시스템 답변에 대해 낸다")
    body = (text or "").strip() or f"이 답변이 틀리거나 부족하다: {m['text'][:200]}"
    req = fb.add_request(body, target="decision", target_ref=reply_id, subject=m.get("subject"), source="farmer", now=now)
    ts = _now(now).isoformat(timespec="seconds")
    note = _append({"id": f"msg_{uuid.uuid4().hex[:12]}", "kind": "chat.message", "subject": m["subject"], "role": "system",
                    "text": f"개선 요구 접수 {req['id']} — 개선 항목이 되면 /improve 에 보인다. 채택은 사람이 한다(D-14).",
                    "observed_at": ts[:10], "recorded_at": ts, "source": "computed:chat", "resolution": RESOLUTION,
                    "drafts": [], "confirmed_refs": [], "reply_ref": reply_id, "request_ref": req["id"]})
    return req, note


def choose_kind(msg_id: str, kind: str, today: date | None = None) -> dict[str, Any]:
    """분류 안 된 발화에 사람이 종류를 고른다 → 초안 생성(확인은 별도)."""
    m = get_message(msg_id)
    if not m:
        raise ChatError("없는 메시지")
    if m.get("confirmed_refs"):
        # [검토 2026-09-20 ⑥] 초안 일부가 이미 원장에 들어간 발화의 종류를 바꾸면 확인 표지가 사라져 새 초안이 '이미 확인됨'으로 읽혔다(영영 확인 불가).
        # 원장은 append-only — 들어간 것은 그대로 두고, 다른 종류가 필요하면 새로 보낸다
        raise ChatError(f"이미 원장에 들어간 초안이 있는 발화 — 원장 {', '.join(m['confirmed_refs'])}. 다른 종류는 새로 보낸다")
    today = today or date.today()
    t = m["text"]
    day = parse_day(t, today)
    day_past = parse_day(t, today, past=True)      # 관찰·불이행은 이미 지난 것 — classify 와 같은 규율(전에는 이 이름이 없어 관찰 선택이 NameError 였다)
    if kind == "event":
        d = {"kind": "event", "type": _event_type(t) or "기타", "observed_at": day_past, "note": t, "why": "사람이 고름", "needs": [] if day_past else ["observed_at"]}
    elif kind == "observation.note":
        d = {"kind": "observation.note", "text": t, "observed_at": day_past or today.isoformat(), "why": "사람이 고름", "needs": []}
    elif kind == "plan.farmer":
        d = {"kind": "plan.farmer", "task": t[:60], "planned_day": day, "note": t, "why": "사람이 고름", "needs": [] if day else ["planned_day"]}
    elif kind == "feedback.request":
        d = {"kind": "feedback.request", "text": t, "target": "other", "why": "사람이 고름"}
    elif kind == "decision.noncompliance":
        et = _event_type(_NEG_FOLD.sub("", t)) or t[:60]
        d = {"kind": "decision.noncompliance", "task_type": et, "planned_task": et, "planned_day": day_past, "reason": t, "why": "사람이 고름",
             "needs": [] if day_past else ["planned_day"]}
    elif kind == "subject.end":
        d = {"kind": "subject.end", "ended_at": day_past or today.isoformat(), "note": t, "why": "사람이 고름", "needs": []}
    else:
        raise ChatError(f"고를 수 없는 종류: {kind}")
    rec = dict(m)
    rec["drafts"] = _attach_plan(m["subject"], [d], today)
    rec.pop("schema_version", None)
    return _append(rec)


def confirm(msg_id: str, draft_index: int = 0, day: str | None = None, event_type: str | None = None,
            now: datetime | None = None, risk: str | None = None, planned_task: str | None = None) -> dict[str, Any]:
    """초안 → 원장. 날짜가 없으면 여기서 받은 day 가 필요하다. 확인된 레코드 id 가 메시지에 붙는다.

    [C17] 재확인 방지(C7)는 **읽고 → 검사하고 → 쓰는** 꼴이라 동시 요청 둘이 둘 다 "아직 안 썼다"를 본다
    (실측 2026-09-20: 같은 예찰 사건이 원장에 두 줄). 화면 서버가 요청마다 스레드를 세우므로 확인 단추
    더블탭·재전송이 그 형태다 — 검사부터 표시까지 한 덩이로 묶는다(정본 `sch.ledger_lock`).
    """
    with sch.ledger_lock:
        return _confirm_locked(msg_id, draft_index, day, event_type, now, risk, planned_task)


def _confirm_locked(msg_id: str, draft_index: int = 0, day: str | None = None, event_type: str | None = None,
                    now: datetime | None = None, risk: str | None = None, planned_task: str | None = None) -> dict[str, Any]:
    m = get_message(msg_id)
    if not m:
        raise ChatError("없는 메시지")
    drafts = m.get("drafts") or []
    if draft_index >= len(drafts):
        raise ChatError("없는 초안")
    done = confirmed_ref(m, draft_index)
    if done:
        # [코드 평가 C7] 재확인 방지 — 브라우저 POST 재전송이 같은 사건을 두 번 원장에 썼다. 확인은 **초안당** 한 번
        # (한 발화에 초안이 둘일 수 있다 — 불이행 사유 + 대신 한 일의 관찰 메모. 각각 따로 확인한다)
        raise ChatError(f"이미 확인된 초안 — 원장 {done}")
    d = dict(drafts[draft_index])
    sid, ref = m["subject"], m["id"]
    k = d["kind"]
    try:
        if k == "event":
            et = event_type or d.get("type")
            rec = ev.add_event(sid, et, day or d.get("observed_at") or "", note=d.get("note", ""), chat_ref=ref, now=now,
                               risk=(risk or d.get("risk")) if et == ev.DAMAGE_TYPE else None)
            if et in ("파종", "정식"):
                s = subjects.by_id(sid)
                if s and not s.get("anchor"):
                    subjects.set_anchor(sid, rec["observed_at"], f"{et}(채팅 확인)")
        elif k == "observation.note":
            rec = ev.add_observation(sid, d["text"], day or d.get("observed_at") or "", chat_ref=ref, now=now)
        elif k == "plan.farmer":
            rec = ev.add_farmer_plan(sid, d["task"], day or d.get("planned_day") or "", note=d.get("note", ""), chat_ref=ref, now=now)
        elif k == "plan.target_date":
            rec = ev.add_target_date(sid, day or d.get("target_date") or "", note=d.get("note", ""), chat_ref=ref, now=now)
        elif k == "feedback.request":
            rec = fb.add_request(d["text"], target=d.get("target", "other"), subject=sid, source=m.get("source", "farmer"), now=now)
        elif k == "decision.noncompliance":
            rec = ev.add_noncompliance(sid, (planned_task or d.get("planned_task") or "").strip() or d.get("task_type", ""), d["reason"],
                                       day or d.get("planned_day") or "", now=now)
        elif k == "subject.end":
            s = subjects.set_status(sid, "종료", ended_at=day or d.get("ended_at") or "")
            rec = {"id": s["id"], "kind": "subject", "observed_at": s["ended_at"], "status": s["status"]}   # 등록부 갱신 — 원장 레코드가 아니라 상태
        else:
            raise ChatError(f"확인할 수 없는 종류: {k}")
    except (ev.EventError, fb.FeedbackError, subjects.SubjectError) as e:
        raise ChatError(str(e))
    upd = dict(m)
    upd["confirmed_refs"] = list(m.get("confirmed_refs", [])) + [rec["id"]]
    upd["drafts"] = [dict(x, confirmed_ref=rec["id"]) if n == draft_index else x for n, x in enumerate(drafts)]
    upd.pop("schema_version", None)
    _append(upd)
    return rec


def confirmed_ref(m: dict[str, Any], draft_index: int) -> str | None:
    """이 초안이 이미 원장에 들어갔으면 그 원장 id. 초안에 confirmed_ref 가 붙은 것이 정본이고, 그 표지가 없는 옛 메시지는
    발화 단위(confirmed_refs)로 본다 — 옛 기록의 C7(재확인 방지)을 그대로 지킨다."""
    drafts = m.get("drafts") or []
    if draft_index < len(drafts) and drafts[draft_index].get("confirmed_ref"):
        return drafts[draft_index]["confirmed_ref"]
    refs = m.get("confirmed_refs") or []
    if refs and len(drafts) <= 1 and not any(x.get("confirmed_ref") for x in drafts):
        return refs[0]                       # 옛 기록은 초안이 하나뿐이었다 — 둘 이상이면 표지 없는 초안은 열린 것이다(검토 2026-09-20 ⑥)
    return None


def pending_drafts(subject_id: str) -> list[tuple[dict[str, Any], int, dict[str, Any]]]:
    out = []
    for m in list_messages(subject_id):
        if m.get("role") != "farmer" and m.get("source") != "publisher":
            continue
        for i, d in enumerate(m.get("drafts") or []):
            if d["kind"] != "question" and not confirmed_ref(m, i):
                out.append((m, i, d))
    return out


# ── 영농일지 — 원장을 날짜로 펼친다 ─────────────────────────────────────────────────
def diary(subject_id: str) -> list[dict[str, Any]]:
    items: list[dict[str, Any]] = []
    for r in ev.list_records(subject_id):
        k = r.get("kind")
        if k == "event":
            head = f"{r.get('type')}({r.get('risk')})" if r.get("risk") else str(r.get("type"))
            txt = f"{head} — {r.get('note') or ''} {', '.join(r.get('materials') or [])}".strip(" —")
        elif k == "observation.note":
            txt = r.get("text", "")
        elif k == "plan.farmer":
            txt = f"할 일: {r.get('task')} — {r.get('note') or ''}".strip(" —")
        elif k == "plan.target_date":
            txt = f"납품 계획일 {r.get('target_date')} — {r.get('note') or ''}".strip(" —")
        elif k == "decision.noncompliance":
            txt = f"{r.get('planned_task')} 안 한 이유: {r.get('reason')}"
        else:
            txt = json.dumps(r, ensure_ascii=False)[:120]
        items.append({"day": (r.get("observed_at") or "")[:10], "kind": k, "label": KIND_LABEL.get(k, k), "text": txt,
                      "id": r.get("id"), "source": r.get("source"), "from_chat": bool(r.get("chat_ref"))})
    for v in media.list_records(subject_id):
        items.append({"day": (v.get("observed_at") or "")[:10], "kind": "observation.video", "label": "영상",
                      "text": f"{v.get('file')} · {v.get('note') or ''}".strip(" ·"), "id": v.get("id"), "source": v.get("source"), "from_chat": False})
    items.sort(key=lambda x: (x["day"], x["id"] or ""), reverse=True)
    return items
