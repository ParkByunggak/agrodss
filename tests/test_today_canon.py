# -*- coding: utf-8 -*-
# [발행자 제정 2026-09-20 "정본을 세운 회차에 소비자 배선을 전수로 센다"] 화면의 오늘 정본 config.today() 의 소비자 전수 래칫.
#   세는 법(CLAUDE.md 검사 규율): 정본이 대체한 옛 호출형(date.today())과 정본을 받아야 하는 인자(today=)를 둘 다 본다.
#   실측(2026-09-20): 정본을 세운 직후 서버→ingest 두 호출(send · choose_kind)이 today 를 안 넘겨 초안 날짜가 실제 날짜였다(fa49bfd).
# + scripts/update.bat — U-18 뒤 발행자 PC 의 pull 이 "commit or stash" 로 멈추지 않게 하는 갱신 배치(ASCII · 괄호 규칙은 전 배치 공통 검사).
from __future__ import annotations

import ast
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


def _code(path: Path) -> str:
    return "\n".join(ln.split("#", 1)[0] for ln in path.read_text(encoding="utf-8").splitlines())


def test_frontend_has_one_today_canon_and_every_consumer_uses_it():
    # [재검토 F3 · 2026-10-14] 정본은 이제 밭의 시각(서울)으로 센다(datetime.now(FARM_TZ)) — 지키는 것은 꼴이 아니라 **시계를 읽는 자리가 하나**라는 것
    for py in (ROOT / "frontend").glob("*.py"):
        code = _code(py)
        if py.name == "config.py":
            # 호출만 센다(구문 트리) — 독스트링이 옛 호출형을 이름으로 말하는 것은 시계를 읽는 자리가 아니다
            tree = ast.parse(py.read_text(encoding="utf-8"))
            clocks = [n for n in ast.walk(tree) if isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                      and isinstance(n.func.value, ast.Name) and (n.func.value.id, n.func.attr) in {("date", "today"), ("datetime", "now")}]
            today_fn = next(n for n in tree.body if isinstance(n, ast.FunctionDef) and n.name == "today")
            assert len(clocks) == 1 and clocks[0] in list(ast.walk(today_fn)), "정본 자리 하나뿐(today 안)"   # 밭의 시각인지는 아래 검사가 동작으로 잰다
        else:
            assert "date.today()" not in code, f"{py.name}: 옛 호출형이 남아 있다 — config.today() 로"
    serve = _code(ROOT / "frontend" / "serve.py")
    # 정본을 받아야 하는 호출 — ingest/judge 로 오늘을 넘기는 자리 전부(옛 호출형이 없어도 인자를 안 넘기면 ingest 가 실제 날짜로 메운다)
    for call in ("chat.send(", "chat.choose_kind(", "judge_run.all_judgments("):
        for m in re.finditer(re.escape(call), serve):
            seg = serve[m.end():m.end() + 300].split(")\n", 1)[0]
            assert "config.today()" in seg, f"{call} 에 오늘이 안 넘어간다: {seg[:80]}"
    assert "hint_for(s, config.today())" in serve and "product_view(sid, today=config.today())" in serve


def test_today_is_counted_on_the_farm_clock(monkeypatch):
    """[재재검토 2026-10-14] 첫 판은 호출 글자(「datetime.now(FARM_TZ)」)를 박았다 — 같은 뜻의 다른 표기에 빨갛고, 시간대를 UTC 로 바꿔도 초록이었다.
    동작으로 잰다: 세계 시각 10-13 22:00(서울 10-14 07:00 — 세션이 실제로 돈 시각대)에 「오늘」 은 10-14 다. 프로세스 시각이나 다른 시간대로 돌아가면 붉다."""
    from datetime import date, datetime, timezone
    from frontend import config
    moment = datetime(2026, 10, 13, 22, 0, tzinfo=timezone.utc)

    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            return moment.astimezone(tz) if tz else moment.replace(tzinfo=None)

        @classmethod
        def today(cls):
            return moment.replace(tzinfo=None)

    class Day(date):
        @classmethod
        def today(cls):
            return moment.date()

    monkeypatch.delenv(config.TODAY_ENV, raising=False)
    monkeypatch.setattr(config, "datetime", Clock)
    monkeypatch.setattr(config, "date", Day)
    assert config.today() == date(2026, 10, 14)


def test_update_bat_discards_stale_registry_edit_then_pulls():
    raw = (ROOT / "scripts" / "update.bat").read_bytes()
    assert all(b < 128 for b in raw)                                              # ASCII — cmd 는 cp949 로 읽는다
    text = raw.decode("ascii")
    lines = [ln.strip() for ln in text.splitlines()]
    i_diff = next(i for i, ln in enumerate(lines) if ln.startswith("git diff --quiet -- data/parcels.json"))
    i_co = next(i for i, ln in enumerate(lines) if ln.startswith("if errorlevel 1 git checkout -- data/parcels.json"))
    i_pull = next(i for i, ln in enumerate(lines) if ln.startswith("git pull origin main"))
    assert i_diff < i_co < i_pull                                                  # 수정됐을 때만 버리고, 그 뒤에 pull
    assert "parcels_local" not in text.replace("data\\parcels_local.json", "")     # 덮개는 절대 건드리지 않는다(주석의 이름만 허용)
