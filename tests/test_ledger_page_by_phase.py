# -*- coding: utf-8 -*-
# [앞날 걷기 2026-10-14 · W-20 · W-21 · W-22 · W-31 · W-33 · W-37 · W-38] 대장 페이지가 **날에 따라 다른 사실**을 한 문장으로 박아 두었다 —
# 창이 닫힌 뒤에도 「잎 기준 경보 둘 · 매일 · 주의」(실측: 「경보 수확 지연」 하나) · 수확 칸에서도 「오늘(생육 중기)은 비료뿐」 · 「10-15 부터 가뭄 답은 …」.
# 처방: 페이지가 수확 창 앞 · 안 · 뒤(_PHASE)에 따라 말을 고른다. 이 검사는 **그 말을 판정 · 답 · 화면으로 다시 잰다** — 페이지가 주장하는 것을
# 정본이 실제로 내는지(여러 날 · 격리 사본). 그리고 ⓪ˢ 의 「안 바뀌는 것」(W-22)은 **지금의 결함을 말하는 문장**이라, W-01 · W-02 · W-03 을 고치면 여기가
# 붉어진다 — 그때 페이지 문장도 함께 고치라는 뜻이다(고친 뒤에도 「안 바뀐다」 고 말하는 페이지가 되지 않게).
# [재검토 L1 · L2 · L3 · R1 · R2 · R3 · R4 · WF-4 · 2026-10-14] 첫 판은 창(_PHASE) 하나로 골라 **창이 열리는 날**(경계일 — 답은 아직 생육 중기 칸)과 **수확 후 칸**
# (촬영 칸이 아니다)에서 거짓이었고, 과습 · 배수 · 자기 점검 문장은 날을 아예 안 봤다. 이 검사는 창이 아니라 **답이 읽는 칸**(_AT)으로 나뉜 문장을 경계일 ·
# 수확 칸 · 수확 후 칸 · 달력 끝 뒤에서 다시 잰다 — 과습 · 배수는 배수 값을 바꿔 판정이 실제로 바뀌는지로(양방향).
from __future__ import annotations

import html
import importlib
import re
from datetime import date, timedelta

import pytest

from frontend import chat_pages
from ingest import chat, media, parcels
from tests.test_brand_home import srv  # noqa: F401
from tests.test_publisher_path_http import _get

SID = "p001-jjokpa-2026f"


def _page(monkeypatch, today: str):
    monkeypatch.setenv("AGRODSS_TODAY", today)
    return importlib.reload(importlib.import_module("scripts.build_ledger_page"))


def _sub():
    return next(s for s in media.load_subjects() if s["id"] == SID)


def _envs(day: str) -> dict:
    from judge import run as jr
    return {e.decision_id: e for _s, envs, _i in jr.all_judgments(date.fromisoformat(day), only=SID) for e in envs}


def _alerts(day: str) -> list[tuple[str, str]]:
    e = _envs(day).get("risk_alert")
    return [(str(a.get("level")), str(a.get("risk"))) for a in ((e.result if e else {}) or {}).get("alerts") or []]


def _ask(monkeypatch, day: str, q: str) -> str:
    monkeypatch.setenv("AGRODSS_TODAY", day)
    return chat.answer(_sub(), q, date.fromisoformat(day))


def _seen(monkeypatch, srv, day: str, path: str) -> str:
    monkeypatch.setenv("AGRODSS_TODAY", day)
    st, _, page = _get(srv, path)
    assert st == 200, (path, st)
    return html.unescape(re.sub(r"<[^>]+>", " ", page))


def _item(page, mark: str) -> str:
    return next(b for h, b in page.NEXT_PUBLISHER if h.startswith(mark))


LEAF = ("첫 서리 · 한파로 잎 손상", "수확 지연 — 잎 노화 · 도복")


@pytest.mark.parametrize("day,phase", [("2026-10-12", "앞"), ("2026-10-14", "창"), ("2026-10-20", "창"), ("2026-11-03", "창"), ("2026-11-04", "뒤"),
                                       ("2026-11-10", "뒤")])   # [재재검토] 창이 닫히는 날과 그 다음 날을 함께 — 한 날 어긋남이 초록으로 지나가지 않게
def test_the_alert_sentence_is_what_the_judgment_says_on_that_day(monkeypatch, day, phase):
    page = _page(monkeypatch, day)
    assert page._PHASE == phase
    why = page.BEST["do"]["why_now"] + " " + page.BEST["do"]["if_not"]
    zs = next(h for h, b in page.NEXT_PUBLISHER if h.startswith("⓪ˢ"))
    al = _alerts(day)
    if phase == "앞":
        assert sorted(lv for lv, r in al if r in LEAF) == ["예고", "예고"] and "「예고」" in why
    elif phase == "창":
        assert sorted(lv for lv, r in al if r in LEAF) == ["주의", "주의"] and "매일 「주의」" in why and "「주의」 로 나가고 있습니다" in zs
    else:
        assert al == [("경보", "수확 지연")], al                                     # 서리는 창과 함께 빠지고 수확 지연 하나가 경보
        assert "「수확 지연」 하나의 「경보」" in why and "서리 쪽은 창과 함께 빠졌습니다" in why and "「경보」 로 나가고 있습니다" in zs
        assert "잎 수확 기준 경보 둘이 매일" not in why                               # 원 결함(W-20)


@pytest.mark.parametrize("day,at", [("2026-10-12", "전"), ("2026-10-14", "전"), ("2026-10-15", "수확"), ("2026-11-03", "수확"),
                                    ("2026-11-04", "후"), ("2026-11-24", "밖")])
def test_the_stage_the_page_speaks_from_is_the_stage_the_answers_read(monkeypatch, day, at):
    """[재검토 L1] 창(경보의 축)과 칸(답의 축)은 경계일에 갈린다 — 페이지가 답을 인용할 때 쓰는 칸은 답이 읽는 칸(hint_for)과 같다."""
    from grid import capture
    page = _page(monkeypatch, day)
    stage = capture.hint_for(_sub(), date.fromisoformat(day))["stage"]
    kind = "밖" if stage is None else {"5": "수확", "6": "후"}.get(stage.split(".")[0], "전")
    assert page._AT == kind == at, (stage, page._AT)
    first = page._HARVEST_FROM
    assert capture.hint_for(_sub(), first)["stage"] == "5. 수확" != capture.hint_for(_sub(), first - timedelta(days=1))["stage"]


@pytest.mark.parametrize("day", ["2026-10-14", "2026-10-20", "2026-11-10", "2026-11-24"])
def test_what_the_seed_use_does_not_change_is_still_true(monkeypatch, srv, day):
    """⓪ˢ 「안 바뀌는 것」(W-22) — 용도를 넣은 뒤(격리 사본) 그 날 칸의 답 · 화면이 실제로 그렇다. 고치면 이 검사가 붉어진다(페이지 문장도 고칠 때)."""
    page = _page(monkeypatch, day)
    body = _item(page, "⓪ˢ")
    at = page._AT
    assert "안 바뀌는 것" in body
    risk_plain = _ask(monkeypatch, day, "위험한 거 있나")                                # 용도를 넣기 전
    parcels.set_fields("p001", use="종구 생산", overwrite=True)
    if at in ("전", "수확"):
        probe = page._HARVEST_FROM.isoformat() if at == "전" else day                 # 경계일의 문장은 「답이 수확 칸을 읽기 시작하는 날」 부터를 말한다
        assert "W-01 · W-02 · W-03" in body and "수확 직전 전경 + 수확물 근접" in body
        if at == "전":
            assert page.when(page._HARVEST_FROM) in body
            assert "지금 창에 경보 없음" not in _ask(monkeypatch, day, "위험한 거 있나")   # 그 날은 아직 생육 중기 칸 — 그래서 날짜를 붙여 말한다(L1 원 결함)
        assert "이번엔 할 일이 아닙니다" in _ask(monkeypatch, probe, "물 줘야 하나")         # W-01 — 물 답은 잎 수확 칸 기준
        assert "지금 창에 경보 없음" in _ask(monkeypatch, probe, "위험한 거 있나")            # W-03 — 머리가 「경보 없음」
        assert "수확 직전 전경 + 수확물 근접" in _seen(monkeypatch, srv, probe, "/media")      # W-02 — 촬영 안내는 잎 수확 장면
    elif at == "후":
        assert "「이 단계는 촬영 칸이 아니다」" in body and "W-06" in body and "수확 직전 전경" not in body
        media_seen = _seen(monkeypatch, srv, day, "/media")
        assert "이 단계는 촬영 칸이 아니다" in media_seen and "수확 직전 전경 + 수확물 근접" not in media_seen
        assert re.search(r"찍을 장면\s*·?\s*6\. 수확 후 · 후작\s+False", _seen(monkeypatch, srv, day, f"/c/{SID}"))   # W-06 — 고치면 붉어진다
        for q in ("물 줘야 하나", "약 뭐 쳐요"):
            a = _ask(monkeypatch, day, q)
            assert "이번엔 할 일이 아닙니다" in a and "수확 후 · 후작" in a, a[:120]
        assert "지금 창에 경보 없음" in _ask(monkeypatch, day, "위험한 거 있나")
    else:
        assert "「재배 달력 기간 밖」" in body and "W-01 · W-02 · W-03" in body
        assert "재배 달력 기간 밖" in _ask(monkeypatch, day, "약 뭐 쳐요")
        assert "단계 없음" in _seen(monkeypatch, srv, day, "/media")
        # [재재검토] 달력 끝 뒤에도 위험 머리는 용도에 따라 갈린다 — 「볼 칸이 없어 용도와 상관없이 같다」 는 거짓이었다(양쪽을 잰다)
        assert "수확 지연" in risk_plain and "지금 창에 경보 없음" not in risk_plain
        assert "지금 창에 경보 없음" in _ask(monkeypatch, day, "위험한 거 있나") and "(용도 없이는 「수확 지연」 경보" in body
        assert "볼 칸이 남지 않은" not in body


@pytest.mark.parametrize("day,said", [("2026-10-14", "칸 '수확' 에 유기 자재 계열이 없다"), ("2026-10-20", "칸 '수확' 에 유기 자재 계열이 없다"),
                                      ("2026-11-10", "칸 '수확 후 · 후작' 에 유기 자재 계열이 없다"), ("2026-11-24", "재배 달력 기간 밖")])
def test_the_material_sentence_names_what_the_answer_says_in_that_stage(monkeypatch, day, said):
    page = _page(monkeypatch, day)
    zm = _item(page, "⓪ᵐ")
    assert said in zm
    if page._AT == "전":                                                                 # [재검토 L1] 경계일은 아직 생육 중기 칸 — 그 날 답은 비료이고, 수확 칸 말은 날짜를 붙여 앞으로의 것
        today_says = _ask(monkeypatch, day, "약 뭐 쳐요")
        assert "생육 중기 · 비대(4단계)" in today_says and said not in today_says and "오늘(생육 중기 · 비대)" in zm
        assert page.when(page._HARVEST_FROM) in zm and said in _ask(monkeypatch, page._HARVEST_FROM.isoformat(), "약 뭐 쳐요")
    else:
        assert said in _ask(monkeypatch, day, "약 뭐 쳐요")                              # W-21 — 페이지가 인용한 그 문장을 답이 낸다


@pytest.mark.parametrize("day", ["2026-09-10", "2026-10-14", "2026-10-15", "2026-10-20", "2026-11-10"])   # 과습 칸 앞(아직 안 본다) · 끝나는 날 · 그 다음 날
def test_the_wet_and_drainage_sentences_hold_only_while_a_judgment_reads_drainage(monkeypatch, day):
    """[재검토 L3 · R2] 페이지가 날마다 「과습 경보는 그대로」 · 「과습 근거가 배수 값을 읽는다」 고 했다. 배수를 나쁨 → 좋음으로 바꿔 판정이 **실제로 바뀌는 날**에만
    그렇게 말하고, 안 바뀌는 날에는 말하지 않는다(양방향 — 생육 중기 칸이 닫힌 다음 날부터 과습 경보도 배수를 읽는 판단도 없다)."""
    from judge import risk_alert
    page = _page(monkeypatch, day)
    wet = any("과습" in r for _lv, r in _alerts(day))
    memo = any(n.startswith(risk_alert.DRAINAGE_NOTE_PREFIX) for n in _envs(day)["risk_alert"].notes)   # 배수를 안 적었을 때(격리 씨앗)의 메모

    def judged():
        envs = _envs(day)
        return {k: {f: v for f, v in envs[k].to_dict().items() if f != "as_of"} for k in parcels.FIELD_CONSUMERS["drainage"] if k in envs}

    parcels.set_fields("p001", drainage="나쁨", overwrite=True)
    poor = judged()
    parcels.set_fields("p001", drainage="좋음", overwrite=True)
    reads = judged() != poor
    assert page._WET == wet == reads, (page._WET, wet, reads)
    why, zs, zw = page.BEST["do"]["why_now"], _item(page, "⓪ˢ"), _item(page, "⓪ʷ")
    u20 = next(b for h, b in page.NEXT_SESSION if h.startswith("U-20"))
    assert ("과습 경보는 용도와 무관하게 그대로입니다" in why) == wet and ("과습 등 수확 전 칸은 그대로입니다" in zs) == wet
    assert ("과습 근거가 그 값을 읽습니다" in zw) == wet and ("그 한 줄이 과습 경보의 근거(배수)와 바로 잇닿습니다" in zs) == wet
    assert ("배수 값을 읽는 판단도 지금은 없습니다" in why) == (not wet) and ("지금은 그 값을 읽는 판단이 없습니다" in zw) == (not wet)
    # [재재검토] ⓪ʷ 「지금 화면」 — 과습 줄 · 메모는 과습 칸을 볼 때만 선다(10-15 부터 「메모가 뜹니다」 는 없는 것을 찾게 했다)
    assert memo == wet and ("메모가 뜹니다. " in zw) == memo and ("판단 화면에 그 줄도 메모도 없습니다" in zw) == (not memo)
    if not wet:                                                                          # 지난 말인지 앞의 말인지 — 과습 칸 앞의 날에 「…까지였습니다」 는 거짓
        assert ("까지였습니다" in zw) == (date.fromisoformat(day) > page._WET_END) and ("아직 볼 때가 아닙니다" in zw) == (date.fromisoformat(day) <= page._WET_END)
    assert f"마지막 과습 칸({page._WET_STAGE})은 {page.md(page._WET_END)} 까지" in u20 and "볼 때만" in u20   # 상시 문장은 조건(볼 때 · 그 날까지)을 함께


@pytest.mark.parametrize("day", ["2026-10-14", "2026-10-20", "2026-11-10", "2026-11-24"])
def test_the_selfcheck_and_drought_sentences_follow_the_stage(monkeypatch, day):
    """[재검토 R1] ① 이 「전부 맞다 (5/5)」 · 「⑤b 는 비 기록이 있어야 맞다」 를, ②b 가 칸 3·4 의 화면을 날과 상관없이 약속했다 — 수확 칸부터는 가뭄 판단이 없어
    ⑤b 가 자료와 상관없이 '다르다' 다(W-13 · 화면 쪽). 그 날부터는 그렇게 말하고, 칸 3·4 를 바꿔도 이번 작기에 달라지는 답이 없다고 말한다."""
    from frontend import selfcheck
    page = _page(monkeypatch, day)
    one, zb = _item(page, "①"), _item(page, "②b")
    b5 = next(c for c in selfcheck.run(date.fromisoformat(day), None)["checks"] if c["id"] == "⑤b")
    na = "이번엔 할 일이 아닙니다" in str(b5.get("actual"))                             # 이 칸에는 가뭄 판단이 없다 — 비 기록과 상관없다
    assert na == (page._AT != "전"), (day, page._AT, str(b5.get("actual"))[:80])
    assert ("「전부 맞다 (5/5)」" in one) == (not na) and ("'다르다' 로 뜹니다" in one) == na
    assert ("지금은 그 두 칸이 지났습니다" in zb) == na and "그 뒤 화면 — 칸 3·4" in zb
    # [재재검토] 가뭄 판단이 없는 까닭도 칸마다 — D-22 는 수확 칸의 결정이다(수확 후 칸 · 달력 끝 뒤에 D-22 를 대면 안 한 결정을 댄다)
    assert ("결정 D-22 대로" in one) == (page._AT == "수확")
    if page._AT == "밖":
        assert "W-24" in one and "단계이 없다" in str(b5.get("actual"))                  # 깨진 문면(W-24) — 고치면 붉어진다
    if na:
        assert not b5["ok"]                                                              # W-13 — 고치면 붉어진다(① 문장도 함께 고칠 때)


def test_every_open_finding_the_publisher_must_answer_is_asked_on_the_page(monkeypatch):
    """[재검토 R3] 발행자 값이 있어야 고치는 즉시급(W-05)을 남은 수를 세는 줄이 걸러 페이지 어디에도 없었다 — 정본에 있고 소비자가 0 인 G1 꼴."""
    page = _page(monkeypatch, "2026-10-14")
    pub = [r for r in page.walk_rows() if r["grade"] == "즉시" and r["owner"] == "발행자" and r["state"].startswith("열림")]
    said = " ".join(h + " " + b for h, b in page.NEXT_PUBLISHER)
    assert any(h.startswith("⓪ᵂ") for h, _ in page.NEXT_PUBLISHER) == bool(pub)
    for r in pub:
        assert f"<b>{r['id']}</b>" in said and r["what"] in said, r["id"]


@pytest.mark.parametrize("day", ["2026-10-14", "2026-11-10", "2026-11-24"])
def test_what_the_page_says_the_session_will_fix_is_still_open(monkeypatch, day):
    """[재검토 WF-4] 「세션이 고칩니다(W-…)」 · 「남았습니다」 가 가리키는 번호는 발견 목록에서 아직 열림이다 — 고치면 그 항목의 문장도 함께 고친다.
    [재재검토] ⓪ᴿ 의 등재급은 범위(「W-23~」)가 아니라 표에서 센 목록이다 — 그 범위 안 넷은 이미 고쳤고 하나는 발행자 결정이었다."""
    page = _page(monkeypatch, day)
    open_ids = {r["id"] for r in page._WALK if r["state"].startswith("열림")}
    for h, b in page.NEXT_PUBLISHER:
        if h.startswith(("⓪ˢ", "⓪ᴿ", "⓪ᵐ", "①", "⓪ᵂ")):
            cited = set(re.findall(r"W-\d+", h + b))
            assert cited <= open_ids, (h[:12], sorted(cited - open_ids))
            assert not re.search(r"W-\d+~", h + b), h[:12]                                # 범위 꼴은 손 셈이다
    reg = [r["id"] for r in page._WALK if (r["grade"], r["owner"]) == ("등재", "세션") and r["state"] == "열림"]
    assert f"세션 몫 {len(reg)}개({' · '.join(reg)})" in _item(page, "⓪ᴿ")


@pytest.mark.parametrize("day", ["2026-10-14", "2026-10-20", "2026-11-10", "2026-11-24"])
def test_the_examples_of_what_is_left_show_on_that_day(monkeypatch, day):
    """[재재검토] ⓪ᴿ 의 보기 둘을 날과 상관없이 현재형으로 적었다 — 경계일에 「약 뭐 쳐요」 는 아직 비료 인용이고, 수확 칸이 지나면 「서리 오나」 에 서리가 없다.
    보기는 그 날 답이 실제로 그럴 때만 든다(양방향)."""
    page = _page(monkeypatch, day)
    zr = _item(page, "⓪ᴿ")
    drug, frost = _ask(monkeypatch, day, "약 뭐 쳐요"), _ask(monkeypatch, day, "서리 오나")
    dev = "유기 자재 계열이 없다" in drug or "재배 달력 기간 밖" in drug                      # W-10 — 개발자 사유 그대로
    calendar_frost = "주의 첫 서리" in frost                                                   # W-11 — 예보 없이 달력만으로 낸 「주의」(격리 사본 · 예보 키 없음)
    assert ("(W-10)" in zr) == dev and ("(W-11)" in zr) == calendar_frost, (day, dev, calendar_frost)


def test_the_findings_reader_counts_bold_cells_and_stops_on_unknown_words(monkeypatch, tmp_path):
    """[재검토 WF-4] 굵게 쓴 「**즉시**」 · 「**열림**」 이 같음 비교에서 말없이 빠졌다(F36 의 꼴) — 별표를 걷고, 정해진 말이 아니면 멈춘다."""
    page = _page(monkeypatch, "2026-10-14")
    head = "| 번호 | 급 | 몫 | 언제부터 | 무엇 | 어디서 다시 보나 | 렌즈 | 상태 |\n|---|---|---|---|---|---|---|---|\n"
    one = "| W-01 | 즉시 | 세션 | 지금 | 가 | 나 | 답 | 열림 |\n"
    doc = tmp_path / "walk.md"
    monkeypatch.setattr(page, "WALK_DOC", doc)
    doc.write_text("## 표\n\n" + head + "| **W-01** | **즉시** | 세션 | 지금 | 가 | 나 | 답 | **열림** |\n"
                   "| *W-02* | 즉시 | 세션 | 지금 | 가 | 나 | 답 | `열림` |\n| `W-03` | _즉시_ | 세션 | 지금 | 가 | 나 | 답 | 열림 |\n\n## 다음\n", encoding="utf-8")
    rows = page.walk_rows()                                                              # [재재검토] 꾸민 번호(* · ` · _)도 빠지지 않는다 — 행은 표 구역의 몸 줄 전부
    assert [(r["id"], r["grade"], r["state"]) for r in rows] == [("W-01", "즉시", "열림"), ("W-02", "즉시", "열림"), ("W-03", "즉시", "열림")]
    for bad in ("| W-02 | 급함 | 세션 | 지금 | 가 | 나 | 답 | 열림 |", "| W-02 | 즉시 | 누군가 | 지금 | 가 | 나 | 답 | 열림 |",
                "| W-02 | 즉시 | 세션 | 지금 | 가 | 나 | 답 | 닫힘 |", one.strip(), "| X-02 | 즉시 | 세션 | 지금 | 가 | 나 | 답 | 열림 |"):
        doc.write_text("## 표\n\n" + head + one + bad + "\n", encoding="utf-8")
        with pytest.raises(AssertionError):
            page.walk_rows()


def test_the_findings_doc_counts_nothing_by_hand_and_keeps_its_order():
    """[재검토 L4 · WF-5] 머리가 「아래 42 개다」 라고 손으로 셌고 표는 43 행 · W-43 이 W-42 앞에 있었다 — 행이 정본이고 번호 순이다."""
    from scripts import build_ledger_page as blp
    text = blp.WALK_DOC.read_text(encoding="utf-8")
    ids = [int(x) for x in re.findall(r"^\|\s*\**W-(\d+)", text, re.M)]
    assert ids == sorted(ids) and len(ids) == len(set(ids))
    assert not re.search(r"아래\s*\d+\s*개", text)


@pytest.mark.parametrize("day", ["2026-10-14", "2026-10-20", "2026-11-24"])
def test_the_readers_of_the_use_value_today_are_the_judgments_that_change(monkeypatch, day):
    """[재재검토] 정본(FIELD_CONSUMERS)은 「읽을 수 있는」 판단이다 — 페이지는 「오늘 읽는」 판단을 말한다. 첫 판은 정본 수를 그대로 적고 검사도 같은 정본과 대조해
    (같은 것끼리 비교 — 공허) 10-15 부터 해당 없음인 배수 경보까지 「5개」 로 셌다. 용도를 넣고 빼서 봉투가 실제로 바뀌는 판단을 센다."""
    from frontend import words
    page = _page(monkeypatch, day)
    why = page.BEST["do"]["why_now"]

    def judged():
        return {k: {f: v for f, v in e.to_dict().items() if f != "as_of"} for k, e in _envs(day).items()}

    plain = judged()
    parcels.set_fields("p001", use="종구 생산", overwrite=True)
    seed = judged()
    changed = tuple(k for k in parcels.FIELD_CONSUMERS["use"] if plain.get(k) != seed.get(k))
    assert page._USE_LIVE == changed, (page._USE_LIVE, changed)
    assert f"지금 읽는 판단은 **{len(changed)}개**" in why and words._names_said(changed) in why and "**다섯**" not in why


def test_the_readers_of_the_use_value_are_counted_from_the_canon(monkeypatch):
    page = _page(monkeypatch, "2026-10-20")
    assert "「종구 재배의 수확 때는 재배 달력에 아직 없습니다 — 잎 수확 기준으로는 말하지 않습니다」" in page.BEST["do"]["why_now"]   # [재검토 R5] 답의 문면 그대로
    parcels.set_fields("p001", use="종구 생산", overwrite=True)
    assert "종구 재배의 수확 때는 재배 달력에 아직 없습니다 — 잎 수확 기준으로는 말하지 않습니다" in _ask(monkeypatch, "2026-10-20", "수확 언제 해요")


def test_the_drought_sentence_names_both_stages_without_a_date(monkeypatch):
    page = _page(monkeypatch, "2026-10-20")
    zb = next(h for h, b in page.NEXT_PUBLISHER if h.startswith("②b"))
    for day, said in (("2026-10-20", "수확 칸에는 가뭄 · 관수 판단을 두지 않습니다"), ("2026-11-10", "수확 후 · 후작 칸에는 가뭄 · 관수 판단이 없습니다")):
        assert f"「{said}」" in zb and said in _ask(monkeypatch, day, "물 줘야 하나"), (day, said)
    assert "10-15 부터 가뭄" not in zb                                                   # W-31 원 결함


def test_the_decisions_header_and_the_long_range_line_are_quoted_as_shown(monkeypatch):
    page = _page(monkeypatch, "2026-10-20")
    zp = _item(page, "⓪⁺")
    shape = f"결정됨 {page._DEC['decided']} · 전체 {page._DEC['total']}"
    header = re.search(r'<p class="meta">남은.*?</p>', chat_pages.decisions_main()).group(0)
    assert shape in zp and shape in header and "(D-22) · 전체" not in zp              # W-33 — 화면 머리에 대장 번호가 없다
    five = _item(page, "⑤")
    head = "등재된 장기 전망 없음 — 기상청 1·3개월 전망은 발표되지만"
    assert head in five and head in _ask(monkeypatch, "2026-10-20", "내일 날씨 어때")   # W-37
    zs = _item(page, "⓪ˢ")
    assert "--stage 5 --key by_use" in zs and "--stage 6" in zs                         # W-38 — 칸마다 한 명령
