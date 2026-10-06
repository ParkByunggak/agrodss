# -*- coding: utf-8 -*-
# [낡음 대조 2026-10-06] 날수를 손으로 적지 않게 한 그 규율의 **건수 판**이다. 발행자가 읽는 목록이 정본에서 셀 수 있는 수를 손으로 적고 있었다:
#     「화면의 15줄 · 답 0」 · 「기대 종류 열넷」 · 「답 없는 줄 14 · 저장 폼도 14」
# 오늘 재니 세 수는 다 맞았다(15 · 14 · 20 중 기대 6) — 아직 거짓이 아니었다. 그래서 급은 **칸 2**(구조적 위험)다: 항목이 하나 늘거나 기대가 하나 붙는 날
# 조용히 거짓이 되고, 발행자는 그것을 사실로 읽는다(날수는 하루 만에 그렇게 됐다).
#
# 그런데 **그중 하나는 이미 틀렸다**. 「답 0」 은 세션이 **못 보는 수**다 — 답은 발행자 PC 덮개(`AGRODSS_DECISIONS_LOCAL_PATH`)에만 있다. 잰 수처럼 적혀 있었다(못 잼 ≠ 0).
# 그리고 그 셈 자체가 **닿을 수 없는 셈**이었다: 화면이 「답 0/15」 를 내는데 그 15 안에 **폼이 없는 결정됨 카드**(D-22 · 발행자 10-03 「맞다」 → 재배 달력 반영)가 있어
# 발행자가 끝까지 답해도 14/15 다. 측정 스크립트(`measure_publisher_bottleneck`)는 D-22 를 이미 빼고 있었다 — 같은 사실이 한 소비자에만 닿아 있던 §7.5 지점 축이다.
#
# 이 검사가 고정하는 것 다섯:
#   ① 페이지의 수는 **정본을 움직이면 따라온다**(값 대조는 공허하다 — 오늘 맞는 수를 박아도 통과한다 · 앞 회차 주입 D 의 교훈)
#   ② 결정 화면의 셈은 셋으로 갈린다 — 남은 것 · 답함 · 결정됨(그리고 남은 것 + 결정됨 = 전체)
#   ③ 발행자 목록은 **세션이 못 보는 수**를 잰 수처럼 적지 않는다(「답 0」 금지 · 그 PC 에 있다고 말한다)
#   ④ 외부 상태 측정(저장소 공개 여부)은 **측정 시점과 함께** 적힌다
#   ⑤ 결정됨 카드는 폼이 없다(답한 카드로 남는다) — 그래서 셈에서 갈라야 한다는 전제 자체를 양방향으로 본다
from __future__ import annotations

import json
import re
from pathlib import Path

import pytest

from frontend import chat_pages
from ingest import decisions as dc
from scripts import build_ledger_page as blp

ROOT = Path(blp.__file__).resolve().parent.parent
SRC = (ROOT / "scripts" / "build_ledger_page.py").read_text(encoding="utf-8")


def _publisher_text() -> str:
    """발행자 목록의 글만 — 머리와 본문을 잇고 태그를 걷는다(다른 칸의 글이 섞이면 판정이 흐려진다)."""
    raw = " ".join(f"{h} {b}" for h, b in blp.NEXT_PUBLISHER)
    return re.sub(r"\s+", " ", re.sub(r"<[^>]*>", " ", raw))


def test_the_counts_follow_the_canon_when_the_canon_moves(monkeypatch):
    """[①] 값을 대조하면 공허하다 — 정본을 움직여 본다(항목 둘을 더하고 기대를 하나 더 붙인 꼴)."""
    assert blp.decisions_count() == {"total": len(dc.IDS), "decided": len(dc.DECIDED),
                                     "open": len(dc.IDS) - len(dc.DECIDED)}
    monkeypatch.setattr(dc, "IDS", tuple(dc.IDS) + ("X-1", "X-2"))
    moved = blp.decisions_count()
    assert moved["total"] == len(dc.IDS) and moved["open"] == len(dc.IDS) - len(dc.DECIDED), moved
    monkeypatch.setattr(dc, "DECIDED", dict(dc.DECIDED, **{"X-1": "맞다 — 가짜"}))
    assert blp.decisions_count()["open"] == len(dc.IDS) - 2

    doc = {"groups": [{"name": "가짜", "rows": [{"text": "ㄱ", "expected": "event"}, {"text": "ㄴ"}, {"text": "ㄷ"}]}]}
    p = ROOT / "data" / "utterance_probes.json"
    real = p.read_text(encoding="utf-8")
    try:
        tmp = ROOT / "data" / "_probe_moved.json"
        tmp.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
        monkeypatch.setattr(blp, "ROOT", tmp.parent.parent)      # 같은 자리를 읽되 내용이 다른 꼴 — 경로를 바꿔 끼운다
        monkeypatch.setattr(Path, "read_text", Path.read_text)   # (읽기 함수는 그대로 — 바꾼 것은 내용뿐)
        p.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
        assert blp.probe_count() == {"total": 3, "expected": 1, "left": 2}, blp.probe_count()
    finally:
        p.write_text(real, encoding="utf-8")
        (ROOT / "data" / "_probe_moved.json").unlink(missing_ok=True)
    assert blp.probe_count()["total"] == 20 and blp.probe_count()["expected"] == 6      # 되돌려 놓았는가(검사가 정본을 더럽히지 않는다)


def test_the_page_body_uses_those_counted_values():
    """[① 배선] 세는 함수가 있는데 문면이 손으로 적은 수를 쓰면 아무것도 안 고친 것이다 — f-string 이 그 값을 쓰는지 본다."""
    assert "_DEC, _PROBE = decisions_count(), probe_count()" in SRC
    for name in ("_DEC['open']", "_DEC['total']", "_DEC['decided']", "_PROBE['left']", "_PROBE['total']", "_PROBE['expected']"):
        assert name in SRC, name
    text = _publisher_text()
    d, pr = blp.decisions_count(), blp.probe_count()
    assert f"남은 {d['open']}줄" in text and f"전체 {d['total']}" in text
    assert f"기대 종류 {pr['left']}줄" in text and f"전체 {pr['total']}줄" in text
    assert "15줄" not in text or d["total"] == 15                 # 수가 바뀌면 문면이 따라온다(옛 수가 남으면 터진다)


def test_the_decision_count_is_split_three_ways():
    """[②] 남은 것 · 답함 · 결정됨. 「답 0/15」 는 **닿을 수 없는 셈**이었다(그 15 안에 폼 없는 카드가 있다)."""
    sm = dc.summary({})
    assert sm["total"] == len(dc.IDS) and sm["decided"] == len(dc.DECIDED) and sm["decided_ids"] == list(dc.DECIDED)
    assert sm["open"] == sm["total"] - sm["decided"] - sm["answered"]
    assert sm["open"] + sm["decided"] + sm["answered"] == sm["total"]
    with_answer = dc.summary({dc.IDS[0]: {"verdict": "맞다"}})
    assert with_answer["answered"] == 1 and with_answer["open"] == sm["open"] - 1      # 답이 하나 서면 남은 것이 하나 줄고
    assert with_answer["decided"] == sm["decided"]                                     # 결정됨은 답으로 움직이지 않는다
    decided_answer = dc.summary({d: {"verdict": "맞다"} for d in dc.DECIDED})
    assert decided_answer["open"] == sm["open"], "결정된 줄에 답이 또 와도 남은 것이 줄면 안 된다(두 번 센다)"


def test_the_screen_says_the_three_numbers():
    html = chat_pages.decisions_main()
    visible = re.sub(r"\s+", " ", re.sub(r"<[^>]*>", " ", html))
    sm = dc.summary(dc.load())
    assert f"남은 {sm['open']}" in visible and f"결정됨 {sm['decided']}" in visible and f"전체 {sm['total']}" in visible
    assert not re.search(r"답 \d+/\d+", visible), visible[:400]        # 옛 「답 N/15」 — 닿을 수 없는 셈이라 다시 쓰지 않는다
    for i in dc.DECIDED:
        assert i in visible


def test_the_page_does_not_report_a_number_the_session_cannot_see():
    """[③] 답은 발행자 PC 덮개에만 있다 — 그 수를 잰 것처럼 적지 않는다(못 잼 ≠ 0).

    인용(「…」)은 걷어 내고 본다 — 이 처방이 *고친 옛 문면*을 설명하려면 그 말을 적어야 하고, 글자로만 찾으면 그 설명이 걸린다(§7.1 4번 · 이 트랙에서 네 번째).
    계약은 *페이지가 그 수를 제 말로 주장하지 않는다* 이지 그 글자가 없는 것이 아니다."""
    text = re.sub(r"「[^」]*」", "", _publisher_text())
    assert "답 0" not in text, text[max(0, text.find("답 0") - 120):text.find("답 0") + 60]
    assert "그 PC 에만 있어 세션이 못 셉니다" in text
    assert "답하신 수" in text or "답한 수" in text


def test_the_decided_card_has_no_form_which_is_why_the_count_had_to_split():
    """[⑤ 양방향] 전제부터 — 결정됨 카드에는 저장 폼이 없고(답한 카드로 남는다), 남은 줄에는 있다."""
    html = chat_pages.decisions_main()
    forms = html.count('action="/me/decisions"')
    assert forms == dc.summary(dc.load())["open"], (forms, dc.summary(dc.load())["open"])
    for i in dc.DECIDED:
        assert f'value="{i}"' not in html, i                       # 결정된 줄에는 보낼 폼이 없다
        assert "결정됨:" in html
    other = next(x for x in dc.IDS if x not in dc.DECIDED)
    assert f'value="{other}"' in html                              # 남은 줄에는 있다


def test_external_measurements_carry_the_day_they_were_made():
    """[④ 시점 축] 저장소 공개 여부처럼 **밖에서** 바뀌는 값은 측정 시점과 함께 적는다 — 날짜 없는 「재측정」 은 인상이다."""
    text = _publisher_text()
    for m in re.finditer(r"재측정", text):
        near = text[max(0, m.start() - 90):m.start() + 90]
        assert re.search(r"20\d\d-\d\d-\d\d", near), near
    assert re.search(r"2026-10-06 [0-9:]+ UTC 재측정", text), "저장소 공개 여부는 이 회차에 다시 쟀다"


def test_the_verifier_claim_actually_measures(monkeypatch):
    """[검사의 검사] 주입 H 가 통과했다 — 보고 확인기의 그 줄을 `st == 200` 으로 줄여도 아무 검사가 안 터졌다(주장은 남고 측정이 사라진 꼴).
    그래서 **화면을 틀리게 만들어** 그 줄이 「틀림」 을 내는지 본다 — 값을 박는 대신 다시 재는 쪽이다."""
    from scripts import verify_claims as vc
    good = vc.Sheet()
    vc.check_screens(good)
    claim = next(r for r in good.rows if "결정됨을 갈라 센다" in r[1])
    assert claim[0] == vc.OK, claim

    real = chat_pages.decisions_main
    monkeypatch.setattr(chat_pages, "decisions_main", lambda *a, **k: re.sub(r"남은 \d+", "남은 999", real(*a, **k)))
    bad = vc.Sheet()
    vc.check_screens(bad)
    broken = next(r for r in bad.rows if "결정됨을 갈라 센다" in r[1])
    assert broken[0] == vc.NO, broken      # 화면이 거짓 수를 내면 그 줄이 틀림이어야 한다(안 그러면 그 줄은 아무것도 재지 않는다)


@pytest.mark.parametrize("fn,keys", [(blp.decisions_count, ("total", "decided", "open")),
                                     (blp.probe_count, ("total", "expected", "left"))])
def test_the_counters_are_honest_about_their_parts(fn, keys):
    c = fn()
    assert set(c) == set(keys) and all(isinstance(v, int) and v >= 0 for v in c.values()), c
    assert c["total"] == sum(c[k] for k in keys if k != "total") or c["total"] >= max(c.values())
