# -*- coding: utf-8 -*-
# [WO-ASK-01 §10 · §14 의 5 · 2026-10-03] 추론 고지와 고치기 — *"추론값은 쓰이는 그 자리에서 고칠 수 있다. 대상은 추론값 중 농가가 알 수 있는 것(P1)만. 농가가
# 알 수 없는 것(병해충 임계 · 내한 한계 — P2/P4)은 제외 — 답할 수 없는 요청이 매번 뜨면 ⑦이 깨진다. 침묵은 동의가 아니다. 승격은 셋 중 하나로만."*
#
#   출처 규율의 다음 칸: 추론값마다 **누가 고칠 수 있는가**(fixable_by ∈ 농가 · 정본 · 실측) — 검증기가 요구하고(거부·통과 둘 다) · 목록은 한 자리(sourced_values) ·
#   문서가 표로 싣고(발행자가 한 번에 보고 뒤집는다) · 경보 항목이 그 표지를 들고 · 채팅 답과 /judge 가 **농가 것만** 「고칠 수 있다」 고 말한다.
#   승격 경로는 명시적 고침뿐 — 「농가 확인」 출처는 날짜가 있어야 하고, 노출 횟수로 확신을 올리는 코드는 없다.
from __future__ import annotations

import copy
import re
from datetime import date, timedelta
from pathlib import Path

import pytest

from frontend import words
from grid import schema
from ingest import chat, media
from judge import inference, risk_alert
from judge.need import DEV_TOKENS
from tests.test_screen_speaks_plainly import JARGON, _get, _visible, srv  # noqa: F401 — 같은 화면 걷기 · 같은 낱말 표

ROOT = Path(__file__).resolve().parent.parent
JJ = schema.GRID_DIR / "jjokpa_autumn.json"
SUBJ = media.load_subjects()[0]
ANCHOR = date.fromisoformat(SUBJ["anchor"])


def _unit():
    return copy.deepcopy(schema.load(JJ))


def _stage(unit, order):
    return next(s for s in unit["stages"] if s["order"] == order)


# ── 정본 · 검증기 ──────────────────────────────────────────────────────────────────────────
def test_every_inference_value_in_the_real_grid_says_who_can_fix_it():
    u = _unit()
    vals = schema.sourced_values(u)
    inf = [v for v in vals if v["inference"]]
    assert len(vals) >= 24 and len(inf) >= 20, (len(vals), len(inf))                       # 실측 2026-10-03: 출처 27 · 추론 24
    assert all(v["fixable_by"] in schema.FIXABLE_BY for v in inf), [v["name"] for v in inf if v["fixable_by"] not in schema.FIXABLE_BY]
    assert {v["fixable_by"] for v in inf} >= {"농가", "정본"}                              # 두 갈래가 다 있다 — 전부 한쪽이면 갈래가 아니다
    assert schema.validate(u).ok
    # 결정(「발행자 결정 D-22 …」)은 추론이 아니다 — 수확 칸 N/A 에는 요구하지 않는다
    d22 = next(v for v in vals if v["stage"] == 5 and v["kind"] == schema.DROUGHT_RULES_KEY)
    assert not d22["inference"] and d22["fixable_by"] is None
    assert schema.is_inference("추론 — 양은 미채움") and schema.is_inference("발행자 측 추론 2026-09-30 — 표준 아님") and not schema.is_inference("격자") \
        and not schema.is_inference("발행자 결정 D-22 2026-10-03 — 제 추론")


@pytest.mark.parametrize("mutate, word", [
    (lambda u: _stage(u, 3)["risks"][0].pop("fixable_by"), "fixable_by 가 없다"),
    (lambda u: _stage(u, 2)["tasks"][0].pop("fixable_by"), "fixable_by 가 없다"),
    (lambda u: _stage(u, 3)["drought_rules"].pop("fixable_by"), "fixable_by 가 없다"),
    (lambda u: u["unit"].pop("fixable_by"), "fixable_by 가 없다"),
    (lambda u: _stage(u, 4)["risks"][0].__setitem__("fixable_by", "세션"), "어휘 밖"),
    (lambda u: _stage(u, 5)["tasks"][1].__setitem__("fixable_by", "개발자"), "어휘 밖"),      # 추론이 아니어도 적혀 있으면 어휘 안
    (lambda u: _stage(u, 3)["risks"][0].__setitem__("source", "농가 확인 — 밭에서 봤다"), "날짜(YYYY-MM-DD)가 없다"),
    (lambda u: _stage(u, 5).__setitem__("by_use", {"종구": {"source": "추론 — 검사", "window": {"from_day": 50, "to_day": 70, "basis": "anchor"}}}), "fixable_by 가 없다"),
])
def test_an_inference_value_without_a_fixer_is_refused_with_the_reason(mutate, word):
    u = _unit()
    mutate(u)
    rep = schema.validate(u)
    assert not rep.ok and any(word in e for e in rep.errors), rep.errors


def test_the_pass_side_a_confirmed_source_with_a_date_and_a_fixer_on_a_by_use_override_validate():
    u = _unit()
    _stage(u, 3)["risks"][0]["source"] = "농가 확인 2026-10-05 — 밭에서 본 대로(미숙 퇴비 없음)"
    _stage(u, 5)["by_use"] = {"종구": {"source": "추론 — 검사", "fixable_by": "정본", "window": {"from_day": 50, "to_day": 70, "basis": "anchor"}}}
    rep = schema.validate(u)
    assert rep.ok, rep.errors
    assert any(v["kind"] == "by_use" and v["fixable_by"] == "정본" for v in schema.sourced_values(u))


def test_the_doc_carries_the_table_the_publisher_flips():
    """정본이 있는데 문서가 안 싣는 G1 을 미리 막는다 — 표 한 장에 추론값 전부 · 갈래 · 출처. 문서는 생성물이라 생성기와 같아야 한다."""
    import sys
    sys.path.insert(0, str(ROOT / "scripts"))
    import build_grid_doc as bg
    u = _unit()
    doc = (ROOT / "docs" / "grid_jjokpa_autumn.md").read_text(encoding="utf-8")
    assert doc == bg.build(u)
    sec = doc[doc.index("## 추론값 — 누가 고칠 수 있는가"):doc.index("## 단계별 칸")]
    inf = [v for v in schema.sourced_values(u) if v["inference"]]
    assert f"{len(inf)}건" in sec and "세션 갈래 판정" in sec and "침묵은 동의가 아니다" in sec
    for v in inf:
        assert f"| {v['name']} | **{v['fixable_by']}** |" in sec, v["name"]


# ── 소비자 — 경보 항목 · 고르기 · 채팅 · 화면 ───────────────────────────────────────────
def test_alert_and_watch_items_carry_the_fixer_and_only_farmer_items_are_offered():
    env = risk_alert.judge(dict(SUBJ), today=ANCHOR + timedelta(days=55))                 # 칸 5 열림 — 수확 지연(농가) · 첫 서리(정본) 둘 다 회복 불가
    items = list(env.result["alerts"]) + list(env.result["watch"])
    assert items and all("fixable_by" in it for it in items)
    by = {it["risk"]: it["fixable_by"] for it in items}
    assert by["수확 지연 — 잎 노화 · 도복"] == "농가" and by["첫 서리 · 한파로 잎 손상"] == "정본"
    assert inference.farmer_fixable(items) == ["수확 지연 — 잎 노화 · 도복"]                   # 정본 몫은 부르지 않는다(§10 제외)
    assert inference.farmer_fixable([{"risk": "x", "source": "격자", "fixable_by": "농가"}]) == []          # 추론이 아니면 고칠 것이 아니다
    assert inference.farmer_fixable([{"risk": "x", "source": "추론", "fixable_by": "농가"}, {"risk": "x", "source": "추론", "fixable_by": "농가"}]) == ["x"]
    assert inference.farmer_fixable([]) == [] and inference.farmer_fixable([{"task": "제초", "source_note": "추론", "source": "추론", "fixable_by": "농가"}]) == ["제초"]


def test_the_chat_answer_offers_the_fix_only_when_a_farmer_fixable_inference_is_in_it():
    q = "위험 경보 있나"
    late = chat.answer(dict(SUBJ), q, ANCHOR + timedelta(days=55))
    assert words.fix_offer(["수확 지연 — 잎 노화 · 도복"]) in late                             # 농가 몫 하나만 이름을 부른다
    assert "첫 서리 · 한파로 잎 손상」" not in late and "첫 서리 · 한파로 잎 손상(" in late      # 내한 한계는 경보엔 있되 고치라고 하지 않는다(정본 몫)
    mid = chat.answer(dict(SUBJ), q, ANCHOR + timedelta(days=34))                          # 칸 4 — 과습 · 녹병 둘 다 정본 몫
    assert "검토 전 추론이고" not in mid and "고쳐 주세요" not in mid
    # 고침의 입구는 그대로 '고쳐 달라는 말' — 안내한 꼴이 실제로 그 종류로 읽힌다(안내와 분류가 두 벌이 아니다)
    assert chat.classify("고쳐 주세요: 잎이 노화한 것이 아니라 종구용이라 그대로 둔 것입니다", ANCHOR)[0]["kind"] == "feedback.request"


def test_plan_rows_carry_the_fixer_and_the_plan_answer_offers_only_farmer_tasks():
    """[§10 지점 전수 — 처방 직후] 위험 경보만 고쳤었다. 추론값 24 중 농가 몫 9 가운데 6 이 **할 일**(관수 · 보식 · 제초 · 배수 관리 · 수확 작업 · 잔사)이라
    계획표가 '쓰이는 그 자리' 다 — 같은 결함 · 같은 처방이라 전 지점으로 넓힌다(계획 행 표지 · 같은 고르기 함수 · 채팅 답 · /judge 표)."""
    from judge import plan_vs_actual
    env = plan_vs_actual.judge(dict(SUBJ), today=ANCHOR + timedelta(days=24))             # 칸 3 — 예찰(정본) · 웃거름(정본) · 제초(농가)
    rows = env.result["rows"]
    assert rows and all("fixable_by" in x and "source_note" in x for x in rows)
    by = {x["task"]: x["fixable_by"] for x in rows}
    assert by["제초"] == "농가" and by["예찰(트랩 · 육안)"] == "정본" and by["웃거름 1회"] == "정본"
    assert "제초" in inference.farmer_fixable(rows) and "예찰(트랩 · 육안)" not in inference.farmer_fixable(rows)
    assert inference.farmer_fixable([{"task": "x", "source": "computed:grid", "source_note": "추론", "fixable_by": "농가"}]) == ["x"]    # 계획 행은 source_note 가 출처
    assert inference.farmer_fixable([{"task": "x", "source": "추론", "source_note": "격자", "fixable_by": "농가"}]) == []                 # source_note 가 있으면 그것만 본다
    a = chat.answer(dict(SUBJ), "지금 할 일 뭐 있나", ANCHOR + timedelta(days=24))
    assert "검토 전 추론이고 밭에서 보시는 분이 고칠 수 있는 것입니다" in a and "제초" in a.split("「")[1] and "예찰" not in a.split("「")[1].split("」")[0]


def test_the_judge_page_plan_table_also_says_who_can_fix(srv):
    st, html = _get(srv, "/judge")
    assert st == 200
    src = (ROOT / "frontend" / "serve.py").read_text(encoding="utf-8")
    assert src.count("<th>고칠 수 있나</th>") == 2                                        # 경보 표 · 계획 표 — 쓰이는 두 자리
    seen = _visible(html)
    assert seen.count("고칠 수 있나") >= 2 and "밭에서 보신 것으로 고칠 수 있습니다" in seen   # 09-19(25일째) 계획표에 제초(농가)가 있다


def test_the_offer_and_the_fixer_words_are_farmer_words():
    for text in (words.fix_offer(["수확 지연 — 잎 노화 · 도복"]), *(words.fixer(k) for k in schema.FIXABLE_BY), words.fixer(None), words.fixer("농가", inference=False)):
        assert words.plain(text) == text, text                                              # 낱말 표가 바꿀 것이 없다 — 이미 사람 말
        assert not [w for w in JARGON if w in text], (text, [w for w in JARGON if w in text])
        assert not [t for t in DEV_TOKENS if t in text], text
    assert words.fixer("농가") != words.fixer("정본") != words.fixer("실측") and words.fixer("농가", inference=False) == "—"
    assert set(words.FIXER_SAID) == set(schema.FIXABLE_BY)                               # 갈래가 늘면 사람 말도 함께 는다


def test_the_judge_page_says_who_can_fix_each_alert_in_plain_words(srv):
    st, html = _get(srv, "/judge")
    assert st == 200
    seen = _visible(html)
    assert "고칠 수 있나" in seen and ("기준 자료가 와야 바뀝니다" in seen or "밭에서 보신 것으로 고칠 수 있습니다" in seen)
    assert not [w for w in JARGON if w in seen], [w for w in JARGON if w in seen]
    src = (ROOT / "frontend" / "serve.py").read_text(encoding="utf-8")
    assert src.count("_alert_table(") == 3 and "<th>회복</th><th>근거</th></tr>\" + \"\".join(" not in src   # 표는 한 자리 — 두 카드가 같은 표를 따로 그리지 않는다(변별 표지: 회복 열은 경보 표에만)


def test_promotion_has_no_silent_route():
    """§10 "침묵은 동의가 아니다" — 격자 값 · 출처 · 확신을 바꾸는 코드는 한 명령(apply_grid_value)뿐이고, 노출 횟수 · 질문 횟수를 읽어 격자를 고치는 자리는 없다."""
    for rel in ("judge/inference.py", "judge/risk_alert.py", "ingest/chat.py", "ingest/questions.py", "ingest/asks.py", "ingest/feedback.py"):
        src = (ROOT / rel).read_text(encoding="utf-8")
        assert "dump_text(" not in src and "GRID_DIR" not in src.replace("grid_schema.GRID_DIR", ""), rel
        assert not re.search(r"\[\s*[\"']confidence[\"']\s*\]\s*=", src), rel
    assert "farmer_fixable" in (ROOT / "ingest" / "chat.py").read_text(encoding="utf-8")   # 배선 — 고르기는 3층 하나를 부른다
