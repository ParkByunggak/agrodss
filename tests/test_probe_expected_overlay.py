# -*- coding: utf-8 -*-
# [손 노릇 2026-10-07] 결정 화면을 한 번 저장으로 고친 직후 **같은 형태를 전수로 셌다**(§7.5). 누르는 횟수는 다른 화면이 다 괜찮았는데(측정: /me 2 · 결정 1 · 전망 1 · 채팅 1)
# **문장 형태 점검에는 폼이 0** 이었다 — 기대 종류를 붙이는 길이 **채팅뿐**이다: 묶음 복사 → 종류 열넷 적기 → 세션에 보내기 → 세션이 정본 커밋. 왕복이 한 번 더 붙고,
# 그 사이 이 항목은 **열흘 넘게** 막혀 있었다(발행자 몫 ⓪ᵖ · 3분이라고 적어 둔 그 일).
#
# 처방: 화면에서 **고르고 한 번 저장**한다(결정 화면과 같은 꼴). 쓰기는 **덮개**(git 밖 · AGRODSS_PROBES_LOCAL_PATH)에만 — **정본은 세션 커밋으로만** 바뀐다.
# 덮개가 있으면 그 줄은 바로 맞다/다르다로 셈이 돌고(머리의 「다름 N」 — WO-LLM 문턱의 재료), 세션에 보낼 묶음은 **답한 줄만** 낸다.
#
# 이 검사가 고정하는 것 일곱:
#   ① 세션은 기대를 붙이지 않는다 — 화면에 **미리 고른 것 0**(고르면 채점자와 응시자가 같아진다) · 정본 파일은 화면이 안 고친다
#   ② 저장은 한 폼 · 칸은 기대 **없는** 줄마다(있는 줄에는 안 선다 — 양방향)
#   ③ 검증이 먼저 — 어휘 밖 · 목록 밖 문장 · 빈 저장 · 같은 줄 두 번이면 **아무것도 안 쓴다**
#   ④ 덮개가 이긴다(발행자가 나중에 붙인 것) · 깨진 덮개는 조용히 비우지 않고 이유를 낸다
#   ⑤ 셈이 바로 돈다 — 기대 수 · 맞음 · 다름이 덮개를 반영한다
#   ⑥ 보낼 묶음은 **덮개에서 온 줄만**(정본에 이미 있는 줄은 다시 보내지 않는다)
#   ⑦ 칸 **이름**에 들어가는 사람 문장은 낱말 표를 거쳐도 그대로다 — 안 싸면 「격자를 보여줘」 가 「재배 달력을…」 으로 나가고 그 저장이 **거부된다**(실측)
from __future__ import annotations

import json
from datetime import date
from pathlib import Path

import pytest

from frontend import selfcheck, words
from ingest import probes
from tests.test_brand_home import srv  # noqa: F401 — 화면을 실제로 띄운다(배선까지 본다)

T = date(2026, 10, 7)
ROOT = Path(probes.__file__).resolve().parent.parent


@pytest.fixture()
def local(tmp_path, monkeypatch):
    p = tmp_path / "probes_local.json"
    monkeypatch.setenv("AGRODSS_PROBES_LOCAL_PATH", str(p))
    return p


def _u():
    return selfcheck.utterances(T, selfcheck.subject())


def _page(u) -> str:
    """쪽이 실제로 나가는 꼴 — 낱말 표를 통과시킨 뒤에 본다(`main_html` 과 같은 길 · 싸 둔 사람 말은 여기서 표지가 벗겨진다)."""
    return words.plain_outside(selfcheck._utterance_html(u, __import__("html").escape))


def test_the_session_does_not_fill_in_the_expected_kinds(local):
    """[①] 미리 고른 것 0 · 화면은 정본 파일을 고치지 않는다(덮개만)."""
    html = _page(_u())
    assert "selected" not in html and "checked" not in html
    before = (ROOT / "data" / "utterance_probes.json").read_bytes()
    probes.set_expected_all([(probes.texts()[6], "event")])
    assert (ROOT / "data" / "utterance_probes.json").read_bytes() == before      # 정본은 세션 커밋으로만
    assert local.exists() and "발행자" in local.read_text(encoding="utf-8")       # 누가 붙였는지가 레코드에 남는다


def test_one_save_form_and_a_field_only_where_the_expectation_is_missing(local):
    u = _u()
    html = _page(u)
    assert html.count('action="/selfcheck/expected"') == 1 and html.count(f'id="{selfcheck.SAVE_FORM}"') == 1
    assert html.count(f'form="{selfcheck.SAVE_FORM}"') == u["without_expected"]
    for g in u["groups"]:
        for r in g["rows"]:
            has = f'name="k:{r["text"]}"' in html
            assert has == (r["expected"] is None), (r["text"], r["expected"], has)      # 양방향


@pytest.mark.parametrize("rows,why", [
    ([("관수했다", "없는종류")], "어휘 밖"),
    ([("목록에 없는 문장이다", "event")], "목록 밖"),
    ([], "빈 저장"),
    ([("관수했다", "event"), ("관수했다", "question")], "같은 줄 두 번"),
])
def test_a_bad_row_writes_nothing(local, rows, why):
    """[③] 검증이 먼저다 — 좋은 줄이 섞여 있어도 쓰지 않는다(결정 답과 같은 규율)."""
    with pytest.raises(ValueError):
        probes.set_expected_all(rows)
    assert not local.exists() or probes.load_local() == {}, why


def test_the_overlay_wins_and_the_count_moves_at_once(local):
    """[④⑤] 발행자가 붙인 것이 정본보다 **나중**이다 — 덮개가 이기고, 셈이 그 자리에서 돈다."""
    u0 = _u()
    t = next(r["text"] for g in u0["groups"] for r in g["rows"] if r["expected"] is None)
    probes.set_expected_all([(t, "event")])
    u1 = _u()
    assert u1["with_expected"] == u0["with_expected"] + 1 and u1["without_expected"] == u0["without_expected"] - 1
    assert u1["ok"] + u1["differ"] == u1["with_expected"]
    row = next(r for g in u1["groups"] for r in g["rows"] if r["text"] == t)
    assert row["expected"] == "event" and row.get("from_local") is True
    pinned = next(r["text"] for g in u0["groups"] for r in g["rows"] if r["expected"] == "question")   # 정본에 있는 줄을 덮어써도 덮개가 이긴다
    probes.set_expected_all([(pinned, "event")])
    row2 = next(r for g in _u()["groups"] for r in g["rows"] if r["text"] == pinned)
    assert row2["expected"] == "event" and row2["from_local"] is True


def test_a_broken_overlay_says_why_instead_of_emptying_itself(local):
    local.write_text("{bad", encoding="utf-8")
    with pytest.raises(ValueError):
        probes.load_local()
    local.write_text(json.dumps({"expected": {"관수했다": {"expected": "없는종류"}}}, ensure_ascii=False), encoding="utf-8")
    with pytest.raises(ValueError):
        probes.load_local()
    assert selfcheck.utterances(T, None)["error"]                                 # 화면은 죽지 않고 이유를 말한다(/changes 에도 남는다)


def test_the_block_to_send_carries_only_the_rows_the_publisher_added(local):
    """[⑥] 정본에 이미 있는 줄을 다시 보내면 세션이 같은 값을 또 커밋한다 — 보낼 것은 **새로 붙인 것**뿐이다."""
    assert probes.to_session_text(_u()["doc"]) == ""
    t = next(r["text"] for g in _u()["groups"] for r in g["rows"] if r["expected"] is None)
    probes.set_expected_all([(t, "observation.note")])
    text = probes.to_session_text(_u()["doc"])
    assert text == f"{t} — observation.note"
    html = _page(_u())
    assert selfcheck.SEND_HOW in html and t in html
    assert selfcheck.FROM_LOCAL in html                                           # 그 줄에 「저장소에는 아직」 이 붙는다(안 실으면 발행자가 보낼 이유를 모른다)
    for said in (selfcheck.SEND_HOW, selfcheck.SAVE_HOW, selfcheck.FROM_LOCAL):   # 보이는 말은 그 자체로 사람 말이다(낱말 표 전후가 같다)
        assert words.plain(said) == said, said


def test_the_screen_really_saves_through_http(local, srv):  # noqa: F811
    """[배선] 화면이 `k:<문장>` 으로 보내도 **서버가 그 꼴을 안 보면** 아무 일도 안 생긴다(앞 회차 주입 D 가 그래서 통과했다).
    띄워서 두 줄을 한 번에 POST 하고 덮개에 둘이 들어갔는지 본다."""
    import http.client
    from urllib.parse import urlencode
    rows = probes.texts()
    body = urlencode({f"k:{rows[6]}": "event", f"k:{rows[7]}": "question", f"k:{rows[8]}": ""})
    c = http.client.HTTPConnection("127.0.0.1", srv, timeout=20)
    c.request("POST", "/selfcheck/expected", body=body, headers={"Content-Type": "application/x-www-form-urlencoded"})
    r = c.getresponse()
    page = r.read().decode("utf-8", "replace")
    assert r.status == 200 and "적었다 — 2줄" in page, page[page.find("적었다") - 60:][:160]
    over = probes.load_local()
    assert over[rows[6]]["expected"] == "event" and over[rows[7]]["expected"] == "question" and rows[8] not in over
    c = http.client.HTTPConnection("127.0.0.1", srv, timeout=20)
    c.request("POST", "/selfcheck/expected", body=urlencode({"k:없는 문장": "event"}), headers={"Content-Type": "application/x-www-form-urlencoded"})
    r2 = c.getresponse()
    page2 = r2.read().decode("utf-8", "replace")
    assert r2.status == 400 and "저장하지 않았다" in page2 and len(probes.load_local()) == 2      # 틀린 저장은 아무것도 안 쓴다


def test_the_sentence_in_the_field_name_survives_the_word_table(local, monkeypatch, tmp_path):
    """[⑦] 사람 말이 바뀌면 **기능이 깨지는** 첫 자리다 — 바뀐 이름으로 온 저장은 「목록에 없는 문장」 으로 거부된다."""
    doc = {"groups": [{"name": "묶음", "rows": [{"text": "격자를 보여줘"}, {"text": "원장을 보여줘"}]}]}
    p = tmp_path / "probes.json"
    p.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setattr(probes, "PATH", p)
    u = selfcheck.utterances(T, None)
    page = words.plain_outside(selfcheck._utterance_html(u, __import__("html").escape))
    assert 'name="k:격자를 보여줘"' in page and 'name="k:원장을 보여줘"' in page, page[:400]
    assert "재배 달력을 보여줘" not in page and "일지를 보여줘" not in page
    probes.set_expected_all([("격자를 보여줘", "question")])                       # 그 이름으로 온 저장이 받아들여진다
    assert probes.load_local()["격자를 보여줘"]["expected"] == "question"
