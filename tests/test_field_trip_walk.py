# -*- coding: utf-8 -*-
# [U-17 걷기 2026-09-21] 발행자께 *"한 번 나가시는 김에 넷"* 이라고 지시했다 — 예찰 · 촬영 · 제초 · 필지 답.
# 지시한 경로는 **세션이 먼저 걷는다**(조각 검사가 다 초록이어도 이어 붙인 길은 따로 깨진다).
#
# 걷는 순서는 발행자가 실제로 할 순서 그대로다.
#
#   ① /me 에서 필지 답을 넣는다(밭에서 보고 온 것)      → 입력 대기가 줄고, 판정이 읽는 값과 아닌 값이 구분돼 보인다
#   ② 채팅에 예찰 한 줄                                 → 사건 초안 → 확인 → 원장
#   ③ /judge 에서 예찰이 '이행'으로 바뀐다               → 농가 행위로 생긴 **첫 이행 사례**
#   ④ 결주를 봤다고 적으면 보식이 '조건부' → '놓침'      → 조건이 서면 놓침이 되살아난다(이번 회차 처방)
#   ⑤ 어느 화면에나 AI 고지가 한 번, 꼬리도 한 벌        → 발행자가 붙여 준 그 줄의 재발 방지
from __future__ import annotations

import http.client
import json
from datetime import date
from urllib.parse import quote, urlencode

import pytest

from frontend import config, serve
from ingest import chat, events as ev, parcels
from tests.test_brand_home import srv  # noqa: F401

SID = "p001-jjokpa-2026f"
TODAY = "2026-09-21"          # 예찰 마감 9/24 전 · 웃거름 창 안


def _get(port, path):
    c = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
    c.request("GET", path)
    r = c.getresponse()
    return r.status, r.read().decode("utf-8")


def _post(port, path, form):
    c = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
    c.request("POST", path, body=urlencode(form), headers={"Content-Type": "application/x-www-form-urlencoded"})
    r = c.getresponse()
    return r.status, r.getheader("Location"), r.read().decode("utf-8")


def _rows(port):
    st, body = _get(port, "/judge")
    assert st == 200
    return body


def test_the_field_trip_path_walks_end_to_end(srv, monkeypatch):
    monkeypatch.setenv(config.TODAY_ENV, TODAY)
    assert config.today().isoformat() == TODAY

    # ① 밭에서 보고 온 필지 답 — 주소·좌표는 폼에 칸조차 없다(PII)
    st, body = _get(srv, "/me")
    assert st == 200 and 'action="/me/parcel"' in body
    before_missing = len(parcels.missing_inputs(parcels.by_id("p001")))
    st, _, body = _post(srv, "/me/parcel", {"id": "p001", "soil_texture": "양토", "slope": "완경사",
                                            "drainage": "보통", "irrigation": "점적", "night_light": "없음",
                                            "microclimate": "동쪽 트임 · 안개 잦음 · 바람길 남북"})
    assert st == 200 and "필지 p001 저장" in body
    rec = parcels.by_id("p001")
    assert rec["soil_texture"] == "양토" and rec["microclimate"].startswith("동쪽")
    assert len(parcels.missing_inputs(rec)) == before_missing - 6
    st, body = _get(srv, "/me")
    assert "판정이 읽는 값" in body and "지금은 등록부에만 쌓인다" in body       # 무엇이 열리고 무엇이 안 열리는지 화면이 말한다

    # ② 밭에서 한 일 — 예찰 한 줄(발행자가 실제로 칠 문장에 가깝게)
    st, loc, _ = _post(srv, f"/c/{quote(SID)}/send", {"text": "9월 8일 트랩 확인했다. 고자리파리 성충은 안 보였다"})
    assert st == 302
    m = [x for x in chat.list_messages(SID) if x.get("role") != "system"][-1]
    kinds = [d["kind"] for d in m["drafts"]]
    assert "event" in kinds, kinds                                            # 한 일 = 사건
    i = kinds.index("event")
    st, _, body = _post(srv, f"/c/{quote(SID)}/confirm", {"msg": m["id"], "i": str(i), "day": "2026-09-08", "type": "예찰"})
    assert st == 200 and "원장에 들어감" in body
    assert any(r["type"] == "예찰" and r["observed_at"].startswith("2026-09-08") for r in ev.list_records(SID, "event"))

    # ③ 판정 화면 — 예찰이 이행으로 바뀐다(농가 행위로 생긴 첫 이행)
    #    [단언 조이기] 첫 판은 `"예찰" in body and "이행" in body` 였다 — 그 두 낱말은 화면 아무 데나 있어서
    #    **아무것도 검사하지 않는다**(§7.1 4번 · 헐거운 단언은 주입이 안 걸린다). 그 행의 상태를 직접 본다.
    plan = _plan(SID)
    assert plan["예찰(트랩 · 육안)"] == "이행", plan
    body = _rows(srv)
    assert "계획 대 실제" in body and "이행" in body                           # 화면에도 실린다(판정만 맞고 화면이 안 실으면 소용없다)

    # ④ 결주를 봤다고 적으면 보식이 되살아난다 — 조건부는 '안 했다'가 아니라 '조건이 안 섰다'였다
    env = json.loads(json.dumps(_plan(SID)))
    assert env["보식"] == "조건부", env
    st, loc, _ = _post(srv, f"/c/{quote(SID)}/send", {"text": "군데군데 결주가 보인다"})
    assert st == 302
    m2 = [x for x in chat.list_messages(SID) if x.get("role") != "system"][-1]
    k2 = [d["kind"] for d in m2["drafts"]]
    assert "observation.note" in k2, k2
    _post(srv, f"/c/{quote(SID)}/confirm", {"msg": m2["id"], "i": str(k2.index("observation.note")), "day": "2026-09-04"})
    assert _plan(SID)["보식"] == "놓침"                                        # 조건이 섰으니 이제 진짜 놓침이다

    # ⑤ 화면 꼬리 — 고지 한 번 · 꼬리 한 벌(발행자가 붙여 준 그 줄의 재발 방지)
    st, body = _get(srv, f"/c/{quote(SID)}")
    assert body.count(serve.AI_NOTICE) == 1 and body.count("외부 배포 없음(D-6)") == 1


def _plan(sid: str) -> dict[str, str]:
    from judge import run as judge_run
    e = next(x for x in judge_run.judgments_for(sid, today=date.fromisoformat(TODAY)) if x.decision_id == "plan_vs_actual")
    return {r["task"]: r["status"] for r in e.result["rows"]}
