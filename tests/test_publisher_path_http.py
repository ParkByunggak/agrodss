# -*- coding: utf-8 -*-
# [2026-09-20] 발행자에게 지시한 경로를 **HTTP 로 그대로** 걷는다 — 채팅에 문장을 넣고 → 초안 둘 → 각각 확인 → /judge 사유 기록됨 → /changes 반영됨 →
# 메뉴. 조각 검사(분류 · 확인 · 판정 · 화면)는 다 있었지만 그 조각들을 발행자 순서로 이은 검사는 없었다(배선 래칫 — "검증 대상은 함수가 아니라 배선").
from __future__ import annotations

import http.client
from datetime import date
from urllib.parse import quote, urlencode

from frontend import chat_pages, config, serve
from ingest import chat, events as ev, fertilizer as fz, soil_store
from tests.test_brand_home import srv  # noqa: F401
from tests.test_fertilizer import PNU, USE_XML
from frontend import words


def _confirm_buttons(label: str) -> str:
    """[발행자 2026-09-21 문면] 단추 이름이 답변 문장에도 나오게 했다("'일지에 넣기' 를 누르면 …").
    그래서 낱말을 세면 프로즈까지 세어진다 — **단추인 자리**를 센다(있음을 세는 검사는 뚫린다의 사촌)."""
    return f'type="submit">{label}<'

SID = "p001-jjokpa-2026f"
SENTENCE = "쪽파 포장에는 웃거름 주지 않고 수분공급만 표면이 마르지 않게 해 줌. 그 근거는 토양검증 상태를 기준으로 함"
TODAY = "2026-09-19"     # 기준점(08-25)+25 — 웃거름 1회 창(09-16~09-24) 안. 실제 날짜로 걸으면 9/25 부터 거짓 실패(시점 축) → 화면의 오늘을 고정한다


def _get(port, path):
    c = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    c.request("GET", path)
    r = c.getresponse()
    return r.status, r.getheader("Location"), r.read().decode("utf-8")


def _post(port, path, form):
    c = http.client.HTTPConnection("127.0.0.1", port, timeout=5)
    c.request("POST", path, body=urlencode(form), headers={"Content-Type": "application/x-www-form-urlencoded"})
    r = c.getresponse()
    return r.status, r.getheader("Location"), r.read().decode("utf-8")


def test_publisher_path_sentence_to_reason_recorded_to_judge_and_changes(srv, monkeypatch):
    monkeypatch.setenv(config.TODAY_ENV, TODAY)
    assert config.today().isoformat() == TODAY
    # 0. live_check 가 남기는 것 — 필지 처방 정본(흙토람 FrtlzrUse)이 격리 저장소에 있다(발행자 2회차 실측: 처방 success 저장)
    soil_store.save(fz.parse_prescription_xml(USE_XML, PNU, "07027", fetched_at="2026-09-19T20:17:00+00:00"), "p001", "07027")
    # 1. 채팅 화면 — 메뉴가 있고 항목이 전부 실린다
    st, _, body = _get(srv, f"/c/{quote(SID)}")
    assert st == 200 and 'id="user-tab"' in body and all(f'href="{h}"' in body for h, _, _ in (i for i in chat_pages.USER_MENU if i))
    # 2. 문장 그대로 보내기 → 초안 둘(불이행 사유 · 관찰), 계획 작업명이 계획표에서 채워져 있다
    st, loc, _ = _post(srv, f"/c/{quote(SID)}/send", {"text": SENTENCE})
    assert st == 302
    st, _, body = _get(srv, loc)
    assert body.count(_confirm_buttons(chat.CONFIRM_LABEL)) == 2 and 'name="planned_task" value="웃거름 1회"' in body and 'value="2026-09-16"' in body
    assert chat.KIND_PLAIN["decision.noncompliance"] in body and "하나씩 넣습니다" in body
    m = chat.list_messages(SID)[0]
    assert m["text"] == SENTENCE and [d["kind"] for d in m["drafts"]] == ["decision.noncompliance", "observation.note"]
    assert m["observed_at"] == TODAY and m["drafts"][1]["observed_at"] == TODAY      # 고정한 오늘이 send 까지 닿는다(실제 날짜면 다르다 — 관문의 입력)
    # 1b. '다른 종류' 선택도 같은 오늘로 — 서술문을 관찰로 고르면 관찰일이 고정한 오늘
    _post(srv, f"/c/{quote(SID)}/send", {"text": "특별한 일 없음"})
    m0 = [x for x in chat.list_messages(SID) if x.get("role") == "farmer"][-1]
    _post(srv, f"/c/{quote(SID)}/choose", {"msg": m0["id"], "kind": "observation.note"})
    assert chat.get_message(m0["id"])["drafts"][0]["observed_at"] == TODAY
    st, _, body = _post(srv, f"/c/{quote(SID)}/confirm", {"msg": m0["id"], "i": "0", "day": ""})
    assert st == 200 and ev.list_records(SID)[-1]["observed_at"] == TODAY
    # 3. 초안 0 확인(폼이 보내는 그대로: planned_task · day) → 원장. 같은 초안 재확인은 거부, 초안 1 은 따로 확인
    st, _, body = _post(srv, f"/c/{quote(SID)}/confirm", {"msg": m["id"], "i": "0", "planned_task": "웃거름 1회", "day": "2026-09-16"})
    assert st == 200 and chat.SAVED_LABEL in body and chat.KIND_PLAIN["decision.noncompliance"] in body
    st, _, body = _post(srv, f"/c/{quote(SID)}/confirm", {"msg": m["id"], "i": "0", "planned_task": "웃거름 1회", "day": "2026-09-16"})
    assert st == 400 and "이미 확인된 초안" in body
    st, _, body = _post(srv, f"/c/{quote(SID)}/confirm", {"msg": m["id"], "i": "1", "day": ""})
    assert st == 200 and chat.SAVED_LABEL in body
    recs = ev.list_records(SID)[-2:]                                                  # 앞에 1b 의 관찰 한 줄
    assert [r["kind"] for r in recs] == ["decision.noncompliance", "observation.note"]
    assert recs[0]["planned_task"] == "웃거름 1회" and recs[0]["planned_day"] == "2026-09-16" and recs[0]["reason"] == SENTENCE
    # 3b. 계획표에 없는 종류("약 안 쳤다" → 방제) — 사람이 폼에서 계획 작업명·계획일을 채워 확인한다(폼 값이 원장에 실린다)
    st, loc, _ = _post(srv, f"/c/{quote(SID)}/send", {"text": "약 안 쳤다"})
    m2 = [x for x in chat.list_messages(SID) if x.get("role") == "farmer"][-1]     # 순서는 첫 등장 순 — 마지막 농가 발화
    assert m2["text"] == "약 안 쳤다" and m2["drafts"][0]["needs"] == ["planned_day"] and m2["drafts"][0]["planned_task"] == "방제"
    st, _, body = _post(srv, f"/c/{quote(SID)}/confirm", {"msg": m2["id"], "i": "0", "planned_task": "방제(예찰 뒤 필요 시)", "day": "2026-09-10"})
    assert st == 200 and chat.SAVED_LABEL in body
    assert ev.list_records(SID)[-1]["planned_task"] == "방제(예찰 뒤 필요 시)" and ev.list_records(SID)[-1]["planned_day"] == "2026-09-10"
    # 3c. 발행자의 다음 행위 — 9/8 예찰 한 줄. 부정형은 조사가 붙어도 불이행 사유이고 계획표의 예찰 줄(09-08 · 미이행)에 이어진다(걷기 실측 2026-09-20:
    #     "트랩 확인은 안 했다"가 예찰 **사건**이었다). 긍정형은 사건 예찰 09-08 → 확인 → 계획 대 실제 '예찰(트랩 · 육안)' 이행 — 농가 행위로 생긴 첫 이행 사례
    neg = chat.classify("트랩 확인은 안 했다", date.fromisoformat(TODAY))[0]
    assert neg["kind"] == "decision.noncompliance" and neg["task_type"] == "예찰"
    row = chat._plan_row_for(SID, "예찰", date.fromisoformat(TODAY))
    assert row and row["task"] == "예찰(트랩 · 육안)" and row["work_date"] == "2026-09-08" and row["status"] == "미이행"
    st, loc, _ = _post(srv, f"/c/{quote(SID)}/send", {"text": "9월 8일에 트랩 확인했다"})
    m3 = [x for x in chat.list_messages(SID) if x.get("role") == "farmer"][-1]
    assert m3["drafts"][0]["kind"] == "event" and m3["drafts"][0]["type"] == "예찰" and m3["drafts"][0]["observed_at"] == "2026-09-08"
    st, _, body = _post(srv, f"/c/{quote(SID)}/confirm", {"msg": m3["id"], "i": "0", "type": "예찰", "day": "2026-09-08"})
    assert st == 200 and chat.SAVED_LABEL in body
    # 4. 판단 화면 — 웃거름 1회 카드(등록부 이름)가 '사유 기록됨'을 요약으로 보이고 사유가 붙는다(전에는 M-10 카드가 배지와 축 표뿐이었다 — 2026-09-20 실측).
    #    계획 대 실제 표의 근거 칸에도 같은 문장이 있으므로 카드 요약의 변별 표지 '사유: ' 로 본다(§7.1 4번 겹침)
    st, _, body = _get(srv, "/judge")
    assert st == 200 and "<h2>웃거름 1회 " in body and "top_dressing_1" not in body
    assert "사유 기록됨 — 작업일 2026-09-16 · 마감 2026-09-24" in body and "· 사유: 쪽파 포장에는 웃거름 주지 않고" in body
    # [U-26 2026-09-26] /judge 도 사람 말로 낸다(칸 3 → 3단계) — 기대 문면을 낱말 정본에서 받는다(문면을 박으면 맞는 고침이 검사를 깨뜨린다)
    assert f"<h2>{words.plain('병해충 경보(칸 3)')} " in body and f"<h2>{words.plain('배수 경보(칸 4)')} " in body
    assert "사건 예찰 2026-09-08" in body and "이행 <b>2</b>" in body                  # 3c 의 예찰 한 줄이 계획 대 실제의 이행이 됐다
    # [발행자 화면 판독 2026-09-21] 같은 이름 작업(촬영)이 여러 칸에 있으면 답이 **칸을 말해야** 구별된다 —
    # 칸이 없어서 발행자가 "칸 1 촬영이 놓침(B13 회귀)"으로 읽었는데 실제로는 칸 1 은 기록 없음, 놓침은 칸 2 였다.
    st, loc, _ = _post(srv, f"/c/{quote(SID)}/send", {"text": "지금 뭘 해야 하죠"})
    ans = [x for x in chat.list_messages(SID) if x.get("role") == "system"][-1]["text"]
    # 변별 표지 — "촬영(칸 " 만 보면 **다른 묶음**의 촬영이 그 조건을 채운다(§7.1 4번). 칸 없는 꼴이 하나도 없어야 한다.
    assert "촬영(~" not in ans and "촬영(0" not in ans and "촬영," not in ans, ans[:250]
    assert "촬영(3단계)" in ans, ans[:250]      # 칸 번호는 붙되 화면 말로 나온다
    # 4b. 처방 정본이 있으면 웃거름 카드가 **양**을 낸다(추비 N·K, kg/10a) — 발행자 2회차 live_check 뒤 화면에서 보라고 한 그 값
    assert "양 추비 N 7.6" in body and "K₂O 5.5" in body and "정본 대기" not in body[body.index("<h2>웃거름 1회 "):body.index("<h2>웃거름 2회")]
    assert f"오늘이 {TODAY} 로 고정돼 있다" in body                                     # 고정은 화면이 말한다(잊힌 고정 방지)
    assert words.plain("기준점 후 25일") in body                                        # 판정 자체가 고정된 오늘로 났다(실제 날짜면 26일 이상) — 문면은 정본에서
    st, _, body = _get(srv, f"/c/{quote(SID)}")
    assert body.count(chat.SAVED_LABEL) >= 2 and _confirm_buttons(chat.CONFIRM_LABEL) not in body
    # 5. 영농일지에 불이행 사유 줄 · 변경 로그에 실행 중 = HEAD
    st, _, body = _get(srv, f"/diary/{quote(SID)}")
    assert st == 200 and "불이행 사유" in body
    st, _, body = _get(srv, "/changes")
    assert st == 200 and "반영됨" in body and serve.RUNNING_HEAD in body
