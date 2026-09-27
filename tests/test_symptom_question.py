# -*- coding: utf-8 -*-
# [발행자 실사용 2026-09-26] "잎 끝이 노란 형상을 어떻게 대처해야 하는가?" 에 계획표(다음 예정 5 · 놓침 4)가 나갔다.
# 발행자 판독: *"답이 아닙니다. 질문을 못 읽고 계획표를 낸 것입니다."* — 한 질의가 셋을 드러냈다.
#
#   ① 라우팅   분류는 `question` 으로 맞았고(재현), 그 다음 `topic_of` 의 맨 '해야' 가 계획 대 실제로 끌고 갔다
#   ② 결정 부재  증상 → 원인 좁히기 결정이 등록부에 없다 — 규칙대로면 판단 불가(지식). 계획표는 답한 것처럼 보여 더 나쁘다
#   ③ 관찰 유실  "잎 끝이 노랗다" 는 관찰인데 물음으로 분류되면 관찰 원장에 안 남았다 — I-3 의 질의 이중 사용이 여기서 샜다
#
# 거부와 통과를 둘 다 본다 — 증상 물음은 계획표로 가지 않는다 · 할 일을 묻는 꼴은 그대로 계획 대 실제 · 증상 없는 물음은 관찰 초안이 없다.
from __future__ import annotations

import http.client
from datetime import date
from urllib.parse import quote, urlencode

from frontend import words
from ingest import chat, events as ev, media
from tests.test_brand_home import srv  # noqa: F401

TODAY = date(2026, 9, 24)
Q = "잎 끝이 노란 형상을 어떻게 대처해야 하는가?"


def test_a_symptom_question_is_a_question_and_also_an_observation():
    ds = chat.classify(Q, TODAY)
    assert [d["kind"] for d in ds] == ["question", "observation.note"]
    assert ds[1]["text"] == Q and ds[1]["why_key"] == "asked_about_symptom" and ds[1]["observed_at"] == "2026-09-24"
    assert chat.plain_why(ds[1]) == chat.PLAIN_BY_KEY["asked_about_symptom"]
    for q in ("잎이 왜 시드나요", "밑이 물러졌는데 뭐가 문제인가", "잎에 반점이 생겼는데 어떻게 하나"):
        assert [d["kind"] for d in chat.classify(q, TODAY)] == ["question", "observation.note"], q


def test_a_question_without_a_symptom_stays_a_single_question():
    """반대편 — 증상이 없는 물음에 관찰 초안을 지어내지 않는다."""
    for q in ("언제 캐면 되나?", "지금 뭘 해야 하죠", "웃거름은 언제 주나요", "현재 관리해야 할 항목들을 알려줘요"):
        assert [d["kind"] for d in chat.classify(q, TODAY)] == ["question"], q


def test_how_to_deal_with_is_not_routed_to_the_plan():
    assert chat.topic_of(Q) is None
    assert chat.topic_of("어떻게 대처해야 하는가") is None
    for q in ("지금 뭘 해야 하죠", "현재 관리해야 할 항목들을 알려줘요", "다음에 할 일이 뭔가요", "오늘 해야 할 게 있나"):
        assert chat.topic_of(q) == "plan_vs_actual", q                # 반대편 — 할 일을 묻는 꼴은 그대로


def test_the_answer_to_a_symptom_question_says_we_do_not_know_yet_not_a_plan():
    s = media.load_subjects()[0]
    a = chat.answer(s, Q, TODAY)
    assert a.startswith(f"[{words.said('판단 불가(지식)')}]"), a
    for bad in ("다음 예정", "놓침", "판단 불가", "계획 대 실제"):
        assert bad not in a, (bad, a)
    # 주제 어휘(웃거름)가 함께 있어도 증상 물음이다 — 그 판단은 증상에 답하지 않으니 가진 것을 꺼내지 않는다
    assert chat.answer(s, "잎 끝이 노란데 웃거름 줘야 하나?", TODAY).startswith(f"[{words.said('판단 불가(지식)')}]")
    # 반대편 — 증상이 없는 주제 물음은 그 판단으로 답한다
    assert not chat.answer(s, "지금 뭘 해야 하죠", TODAY).startswith(f"[{words.said('판단 불가(지식)')}]")


def test_a_symptom_inside_a_plan_or_a_request_or_an_end_is_also_kept_as_an_observation():
    """[처방 직후 전수 §7.5] 물음만이 아니었다 — 계획 · 교정 요구 · 작기 종료는 원문을 원장에 안 남긴다(탐침 9 중 3 유실)."""
    for text, first in (("잎이 노래서 내일 웃거름 주려고", "plan.farmer"),
                        ("잎이 노란데 수확 창이 너무 넓어요 고쳐주세요", "feedback.request"),
                        ("잎이 노란데 이번 작기 끝낼게요", "subject.end")):
        ds = chat.classify(text, TODAY)
        assert [d["kind"] for d in ds] == [first, "observation.note"], (text, ds)
        assert ds[1]["text"] == text and ds[1]["why_key"] == "symptom_alongside"
        assert chat.plain_why(ds[1]) == chat.PLAIN_BY_KEY["symptom_alongside"]
    # 반대편 — 원문을 이미 남기는 갈래(사건 note · 불이행 reason · 관찰)에는 붙이지 않는다(같은 말을 두 번 적지 않는다)
    for text, only in (("잎이 노래서 오늘 약 쳤다", "event"), ("잎 끝이 노란데 웃거름 안 줬다", "decision.noncompliance"),
                       ("잎 끝이 노랗게 변했어요", "observation.note")):
        assert [d["kind"] for d in chat.classify(text, TODAY)] == [only], text


def test_no_decision_word_is_a_single_syllable_that_hides_inside_other_words():
    """[처방 직후 전수 §7.5] 한 글자 어휘(캐 · 병 · 얼 · 습 · 약)가 다른 말 속에 걸려 엉뚱한 판단을 꺼냈다 — 형태 독립 래칫."""
    # 뒤에 공백이 붙은 꼴("약 " · "병 ")은 경계 표지라 두 글자로 센다. 의문사(뭐 · 뭘)는 내용어가 아니라 물음 자체라 예외로 둔다.
    interrogatives = {"뭐", "뭘"}
    short = [(did, w) for did, words in chat.TOPIC for w in words if len(w) < 2 and w not in interrogatives]
    assert short == [], f"한 글자 결정 어휘 — 다른 말 속에 걸린다: {short}"
    # 탐침(인공 질문 · 그 어휘가 다른 뜻으로 든 물음)은 결정으로 가지 않는다
    for q in ("병원 다녀와서 밭에 가도 되나", "얼마나 자주 물 줘야 하나", "습관적으로 물을 주는데 괜찮나", "비가림 없이 키워도 되나", "캐릭터 이름은 어떻게 지을까"):
        assert chat.topic_of(q) is None, (q, chat.topic_of(q))
    # 반대편 — 진짜 그 뜻이면 그대로 간다
    for q, did in (("언제 캐면 되나?", "harvest_timing"), ("병이 온 것 같은데 약 있나", "pest_alert"), ("서리 오면 어떻게 하죠", "risk_alert"),
                   ("지금 쓸 수 있는 약 있나요", "material_citation"), ("비가 많이 오면 위험한가", "risk_alert"), ("고랑이 과습인데", "drainage_alert")):
        assert chat.topic_of(q) == did, (q, chat.topic_of(q))


def _post(port: int, path: str, fields: dict) -> tuple[int, str]:
    c = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
    body = urlencode(fields)
    c.request("POST", path, body=body, headers={"Content-Type": "application/x-www-form-urlencoded", "Content-Length": str(len(body))})
    r = c.getresponse()
    return r.status, r.read().decode("utf-8", "replace")


def test_walk_the_publisher_question_to_the_diary(srv, monkeypatch):
    """발행자 경로를 HTTP 로 그대로 — 물음을 넣고 → 답이 '아직 모릅니다' → 물음 안의 본 것을 확인 → 일지에 원문 그대로."""
    from frontend import config
    monkeypatch.setenv(config.TODAY_ENV, TODAY.isoformat())
    sid = media.load_subjects()[0]["id"]
    st, _ = _post(srv, f"/c/{quote(sid)}/send", {"text": Q})
    assert st in (200, 302, 303)
    msgs = chat.list_messages(sid)
    mine = [m for m in msgs if m.get("role") == "farmer"][-1]
    reply = [m for m in msgs if m.get("role") == "system"][-1]["text"]
    assert reply.startswith(f"[{words.said('판단 불가(지식)')}]") and "다음 예정" not in reply and chat.CONFIRM_LABEL in reply
    assert [d["kind"] for d in mine["drafts"]] == ["question", "observation.note"]
    st, body = _post(srv, f"/c/{quote(sid)}/confirm", {"msg": mine["id"], "i": "1"})
    assert st in (200, 302, 303)
    notes = [r for r in ev.list_records(sid) if r.get("kind") == "observation.note"]
    assert notes and notes[-1]["text"] == Q and notes[-1]["observed_at"] == TODAY.isoformat()   # 원문 그대로 · 그날
    assert any(x["kind"] == "observation.note" and x["text"] == Q for x in chat.diary(sid))
