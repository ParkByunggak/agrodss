# -*- coding: utf-8 -*-
# [2026-10-06 실측 — 날이 바뀌어 드러났다] 대장 페이지의 ②b 줄은 이미 이렇게 적고 있었다:
#     "날수를 여기 적지 않습니다 — 날마다 변하는 숫자를 안내에 박으면 하루 뒤 거짓이 됩니다"
# 그런데 **같은 파일의 BEST 블록**이 「10/7 부터(이틀 뒤)」 라고 손으로 적어 두었고, 날이 10-06 으로 바뀌자 그대로 거짓이 됐다(이틀 → 하루).
# 규율이 한 자리에만 닿아 있던 §7.5 지점 축이고, 발행자에게 나가는 **한 수 블록**이라 값이 가장 큰 자리다(그 줄 하나로 하루를 늦게 움직인다).
# 처방: 상대 날수는 글이 아니라 **계산**이고(`when`), 그 날짜·날수도 정본에서 센다(`alert_start` = 수확 창 − horizon · 격자와 결정 params).
#
# 이 검사가 고정하는 것 넷:
#   ① `when` 이 센다 — 오늘 · 내일 · 모레 · N일 뒤 · N일 전(양방향)
#   ② BEST **원문**에는 상대 날수 말이 없고, **렌더된 글**에는 있다(생성기가 넣은 것이다)
#   ③ 머리의 날짜도 센다 — 손으로 적은 날짜는 자정을 넘기면 거짓이다
#   ④ 경보 시작일·창·horizon 셋 다 정본에서 다시 세어 대조한다(안내가 격자보다 오래 살지 못하게)
from __future__ import annotations

import importlib
import re
from datetime import date, timedelta
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
REL_WORDS = ("오늘", "내일", "모레", "하루 뒤", "이틀 뒤", "사흘 뒤", "일 뒤", "일 전")
QUOTED = re.compile(r"「[^」]*」")      # 「오늘 할 일 다 했다」 같은 **인용된 농가 문장**은 안내가 아니라 보기다 — 날이 바뀌어도 거짓이 되지 않는다


def typed_relative(block: str) -> list[tuple[str, str]]:
    """손으로 적은 상대 날수만 고른다 — 인용(「…」)은 걷어 내고, 바로 앞이 `}`(계산해 넣은 것)이면 통과.

    [탐지 축 2026-10-06] 처음엔 낱말만 찾아서 인용된 농가 문장(「내일 물 줄 것」)과 계산된 「{_HORIZON}일 전」 을 같이 잡았다 —
    이 트랙에서 **세 번째** 같은 실수다(모양으로 좁히거나 넓히면 도구가 거짓을 말한다). 그래서 규칙을 글로 적고 검사가 그 규칙을 지킨다."""
    plain = QUOTED.sub(" ", block)
    out = []
    for w in REL_WORDS:
        for m in re.finditer(re.escape(w), plain):
            if not plain[:m.start()].rstrip().endswith("}"):
                out.append((w, plain[max(0, m.start() - 40):m.start() + len(w)]))
    return out


def _page(monkeypatch=None, today: str | None = None):
    if today is not None:
        monkeypatch.setenv("AGRODSS_TODAY", today)
    page = importlib.import_module("scripts.build_ledger_page")
    return importlib.reload(page)


def test_when_counts_the_days(monkeypatch):
    page = _page(monkeypatch, "2026-10-06")
    t = date(2026, 10, 6)
    assert page.when(t) == "10/6 부터(오늘)"
    assert page.when(t + timedelta(days=1)) == "10/7 부터(내일)"
    assert page.when(t + timedelta(days=2)) == "10/8 부터(모레)"
    assert page.when(t + timedelta(days=3)) == "10/9 부터(3일 뒤)"
    assert page.when(t - timedelta(days=2)) == "10/4 부터(2일 전)"
    assert page.when(t + timedelta(days=1), "까지") == "10/7 까지(내일)"      # 조사는 날짜 **뒤**에 — 안내 래칫이 「그 날 부터」 꼴로 본다


def test_the_block_itself_types_no_relative_day(monkeypatch):
    """BEST 원문(소스의 그 블록)에 상대 날수 말이 없다 — 있으면 다음 자정에 거짓이 된다. 구조로 자른다(줄 번호·리터럴을 박지 않는다)."""
    src = (ROOT / "scripts" / "build_ledger_page.py").read_text(encoding="utf-8")
    block = src[src.index("\nBEST = {"):]
    block = block[:block.index("\nBEST_MAX_LINES")]
    assert typed_relative(block) == [], typed_relative(block)
    assert typed_relative("경보는 이틀 뒤부터")[0][0] == "이틀 뒤"              # 규칙이 살아 있다(손으로 적은 것은 잡는다)
    assert typed_relative("「내일 물 줄 것」 이 할 일로") == []                  # 인용은 보기다
    assert typed_relative("그 **{_HORIZON}일 전**에 섭니다") == []              # 계산해 넣은 것은 통과
    page = _page(monkeypatch, "2026-10-06")
    said = page.render_best(page.BEST)
    assert any(w in said for w in REL_WORDS), said[:200]                     # 렌더에는 있다 — 생성기가 센 것이다
    assert "(내일)" in said, said[:200]


def test_the_header_date_is_counted_not_typed(monkeypatch):
    for day, want in (("2026-10-06", "10-06"), ("2026-11-03", "11-03")):
        page = _page(monkeypatch, day)
        assert page.BEST["date"] == want, (day, page.BEST["date"])
        assert page.render_best(page.BEST).startswith(f"최선의 다음 한 수 ({want} · ")


def test_the_alert_day_is_read_from_the_canon(monkeypatch):
    """경보 시작일 = 수확 창 − horizon. 검사도 **정본에서 다시 세어** 대조한다(같은 숫자를 두 벌 적지 않는다)."""
    page = _page(monkeypatch, "2026-10-06")
    from grid import schema as grid_schema
    from ingest import subjects
    from judge import registry, risk_alert, stage_decisions  # noqa: F401

    s = subjects.by_id("p001-jjokpa-2026f")
    unit, miss = grid_schema.load_unit(s)
    assert unit and not miss, miss
    stage = next(st for st in unit["stages"] if str(st.get("name", "")).strip() == "수확")
    start = date.fromisoformat(s["anchor"]) + timedelta(days=int(stage["window"]["from_day"]))
    hz = int(registry.get(risk_alert.DECISION_ID).params["horizon_days"])
    assert page.harvest_window_start() == start and page.horizon() == hz
    assert page.alert_start() == start - timedelta(days=hz)
    # [주입 D 2026-10-06] 값만 대조하면 **오늘 맞는 날짜를 박아 두는 것**을 못 잡는다(그 주입이 통과했다) — 정본이 움직일 때 따라오는지를 본다
    monkeypatch.setattr(page, "horizon", lambda: 3)
    monkeypatch.setattr(page, "harvest_window_start", lambda: date(2026, 11, 20))
    assert page.alert_start() == date(2026, 11, 17), page.alert_start()
    said = page.BEST["do"]["why_now"] + " " + page.BEST["do"]["if_not"]
    first = start - timedelta(days=hz)
    assert f"{first.month}/{first.day} 부터" in said                          # 안내가 잰 날을 말한다(기존 래칫과 같은 계약 · 여기서도 본다)
    assert f"({start.month}/{start.day})" in said and f"**{hz}일 전**" in said


def test_the_generator_still_builds(tmp_path, monkeypatch):
    """래칫이 생성기를 멈추게 하지 않는지 — 실제로 한 번 만든다(assert check_best 가 적재 때 돈다)."""
    page = _page(monkeypatch, "2026-10-06")
    out = tmp_path / "page.html"
    page.main([str(out)]) if hasattr(page, "main") else None
    if not out.exists():                                                     # main 이 없으면 적재만으로 검증(모듈이 쓰기까지 한다)
        import subprocess
        import sys
        r = subprocess.run([sys.executable, "-B", str(ROOT / "scripts" / "build_ledger_page.py"), str(out)],
                           capture_output=True, text=True, encoding="utf-8", cwd=str(ROOT), timeout=600)
        assert r.returncode == 0, r.stdout + r.stderr
    body = out.read_text(encoding="utf-8")
    assert "최선의 다음 한 수" in body and "(내일)" in body or "(오늘)" in body
