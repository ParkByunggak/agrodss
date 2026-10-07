# -*- coding: utf-8 -*-
# [미확인 사건 실측 2026-10-06] 아직 일지에 **안 넣은** 사건 초안이 있으면 판정은 그것을 못 읽는다. 그 사실을 답이 말하는 줄이 **가뭄 답 한 곳**에만 있었다.
# 실측(오늘 2026-10-20 · 초안 셋: 관수 10-19 · 수확 10-18 · 방제 10-18):
#     「물 줘야 하나」      → 「아직 일지에 넣지 않은 관수 기록 1건」 말한다
#     「오늘 뭐 해야 하나」 → 「놓침 8 … 수확(뽑기) 다음 예정」 **그 초안을 말하지 않는다** — 한 일이 놓침으로 읽힌다
# 뒤가 더 나쁘다. 앞은 "못 읽었다" 를 말하지 않은 것이고, 뒤는 **한 일을 안 한 일로** 말한 것이다(짐작을 이행으로 세던 사고의 반대 방향).
#
# 이 검사가 고정하는 것 다섯:
#   ① 표(`events.EVENT_CONSUMERS`)가 **선언이 아니라 측정**이다 — 사건을 넣어 봉투 전부를 대조해 다시 잰다
#   ② 사건 종류 **전수**와 같다 — 안 쟀던 줄이 "소비자 0"(= 말하지 않기로 함)으로 읽히는 자리를 막는다
#   ③ 그 사건을 읽는 판정의 답에만 붙는다(양방향 — 수확 초안은 계획 대 실제에 붙고 수확 시기에는 안 붙는다)
#   ④ 문장은 4층 정본 하나(`words.not_in_diary`) — 같은 말이 두 곳에 손으로 적혀 있었다(조사까지 손으로)
#   ⑤ 사람 말 · 조사 · 0건 금지
#
# 재는 법(조건 축 — 이 측정이 두 번 틀렸다): 사건을 **그 날의 하루 전**으로 넣고, 날 셋(09-20 · 10-07 · 10-20)을 합친다.
#   틀렸던 이유 ① 날짜를 10-18 로 고정하니 9월 측정에서 미래 사건이었다 ② 10-20 은 수확 칸이라 가뭄 판정 자체가 없다(D-22 N/A) → 관수→가뭄이 두 번 안 보였다.
from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone

import pytest

from frontend import words
from ingest import chat, events as ev, subjects
from judge import run as judge_run
from tests.test_screen_speaks_plainly import JARGON

SID = "p001-jjokpa-2026f"
DAYS = (date(2026, 9, 20), date(2026, 10, 7), date(2026, 10, 20))
SAID = "아직 일지에 넣지 않은"


def _judge(T: date) -> dict[str, tuple]:
    out = {}
    for _s, envs, _info in judge_run.all_judgments(T):
        for e in envs:
            ed = e.to_dict()
            r = ed.get("result") or {}
            out[ed["decision_id"]] = (ed["kind"], len(r.get("alerts") or []), json.dumps(r, ensure_ascii=False, sort_keys=True),
                                      tuple(str(n) for n in (ed.get("notes") or [])))
    return out


def test_the_event_table_is_measured_not_declared(tmp_path, monkeypatch):
    """표를 **다시 재서** 대조한다 — 사건 하나를 넣어 판정을 돌리고, 달라진 결정 id 가 표와 같은지 본다(원장은 넣을 때마다 새 폴더 — 쌓이면 측정이 섞인다)."""
    union: dict[str, set[str]] = {}
    for T in DAYS:
        monkeypatch.setenv("AGRODSS_EVENTS_DIR", str(tmp_path / f"base_{T}"))
        base = _judge(T)
        for kind in ev.EVENT_CONSUMERS:
            monkeypatch.setenv("AGRODSS_EVENTS_DIR", str(tmp_path / f"{kind}_{T}"))
            ev.add_event(SID, kind, (T - timedelta(days=1)).isoformat(), **({"risk": "서리"} if kind == ev.DAMAGE_TYPE else {}))
            after = _judge(T)
            union.setdefault(kind, set()).update(k for k in set(base) | set(after) if base.get(k) != after.get(k))
    for kind, ids in ev.EVENT_CONSUMERS.items():
        assert union[kind], (kind, "사건을 넣었는데 아무 판정도 안 달라졌다 — 소비자 선언이 거짓이거나 측정이 닿지 않은 것이다")
        assert union[kind] == set(ids), (kind, sorted(union[kind]), sorted(ids))


def test_every_event_kind_is_in_the_table():
    """[②] 쟀던 일곱만 적었더니 아홉 줄이 빠져 있었다 — 빠진 줄은 「소비자 0」(= 말하지 않기로 함)으로 읽힌다. 종류가 늘면 재서 적는다."""
    assert set(ev.EVENT_CONSUMERS) == set(ev.EVENT_TYPES), sorted(set(ev.EVENT_TYPES) ^ set(ev.EVENT_CONSUMERS))
    assert all(ids for ids in ev.EVENT_CONSUMERS.values())
    assert "측정 경계" in (chat.ROOT / "ingest" / "events.py").read_text(encoding="utf-8")      # 봉투만 봤다는 사유가 소스에 적혀 있다(못 잼 ≠ 소비자 0)


def _draft(kind: str, said: str, T: date) -> None:
    m, _r = chat.send(SID, said, today=T, now=datetime(T.year, T.month, T.day, 9, tzinfo=timezone.utc))
    kinds = [(d["kind"], d.get("type")) for d in m["drafts"]]
    assert ("event", kind) in kinds, (said, kinds)        # 조건부터 — 초안이 그 종류로 섰는가(안 섰으면 아래 판정은 뜻이 없다)
    assert len(chat.unconfirmed_of(SID, kind)) == 1, kinds


def test_only_the_judgments_that_read_that_event_say_it():
    """[③ 양방향] 수확 초안은 **계획 대 실제**에 붙고(그 판정이 읽는다), 수확 시기·가뭄에는 안 붙는다(안 읽는다)."""
    T = date(2026, 10, 20)
    _draft("수확", "10월 18일에 수확했다", T)
    assert "수확" in chat.unconfirmed_line(SID, "plan_vs_actual")
    for did in ("harvest_timing", "drought_alert", "symptom_triage"):
        assert did not in ev.EVENT_CONSUMERS["수확"]                       # 전제부터 — 측정 표에 없다
        assert chat.unconfirmed_line(SID, did) == "", did
    _draft("관수", "어제 물 줬다", T)                                      # 관수는 둘이 읽는다 — 가뭄 쪽도 이제 말한다
    assert "관수" in chat.unconfirmed_line(SID, "drought_alert")
    assert "관수" in chat.unconfirmed_line(SID, "plan_vs_actual") and "수확" in chat.unconfirmed_line(SID, "plan_vs_actual")


def test_the_plan_answer_carries_every_pending_kind():
    """실측 그대로 — 초안 셋을 안 넣은 채 「오늘 뭐 해야 하나」 를 물으면 셋을 다 말한다(한 일이 놓침으로 읽히지 않는다)."""
    T = date(2026, 10, 20)
    for kind, said in (("관수", "어제 물 줬다"), ("수확", "10월 18일에 수확했다"), ("방제", "그저께 약 쳤다")):
        _draft(kind, said, T)
    s = subjects.by_id(SID)
    line = chat.unconfirmed_line(SID, "plan_vs_actual")
    # [길이 측정 2026-10-07] 셋을 **세 문장**으로 말하니 꼬리가 세 번 똑같이 나가 답이 651자였다 — 한 문장으로 합쳤다(종류·건수는 그대로 · 꼬리는 한 번).
    assert line.count(SAID) == 1 and line.count("누르면 판단이 읽습니다") == 1, line
    said_text, _asks = chat.answer_with_asks(s, "오늘 뭐 해야 하나", T)
    for kind in ("관수", "수확", "방제"):
        assert f"{kind} 1건" in said_text, (kind, said_text[-400:])        # 덜 말하지는 않는다 — 셋이 다 이름과 건수로 남는다
    assert SAID in said_text


def test_the_sentence_is_one_canon_and_speaks_plainly():
    """[④⑤] 문장은 4층 하나 · 조사는 정본 · 0건은 말하지 않는다(말할 자리가 없다 — 빈 줄을 만드는 쪽이 결함이다)."""
    said = words.not_in_diary("관수", 2, chat.confirm_label("event"))
    assert not [w for w in JARGON if w in said], said
    assert words.plain(said) == said
    assert "'일지에 넣기' 를" in said and "2건" in said                     # 조사도 정본에서(기 → 를)
    assert words.not_in_diary("수확", 1, "밭 정보에 넣기").count("'밭 정보에 넣기' 를") == 1
    with pytest.raises(ValueError):
        words.not_in_diary("관수", 0, chat.confirm_label("event"))
    src = (chat.ROOT / "ingest" / "chat.py").read_text(encoding="utf-8")
    body = src[src.index("def unconfirmed_line"):]
    body = body[:body.index("\ndef ", 10)]
    assert "_w.not_in_diary_many(" in body and SAID not in body.split('"""')[2]   # 문면을 2층에서 다시 적지 않는다(독스트링 밖) · 합치는 일도 4층 정본이 한다
    assert src.count(f'f" · {SAID}') == 0                                    # 일지 조회 꼬리도 같은 정본을 쓴다(손으로 적힌 조사가 거기 있었다)
