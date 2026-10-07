# -*- coding: utf-8 -*-
# [목록 전수 2026-10-07] 앞 회차가 「지금 답할 수 있는 것」 을 세게 했으니 §7.5 는 **같은 형태를 전수로** 묻는다. 농가 화면에서 "무엇을 할 수 있다" 고
# 말하는 손 목록이 셋 더 있었고 **셋이 다 달랐다**.
#
#     채팅 머리말    한 일 · 본 것 · 할 일 · 못 한 이유 · 고쳐 달라는 말 · 물음        「농사 끝」 빠짐
#     입력칸 밑      한 일 · 본 것 · 할 일 · 고쳐 달라는 말 · 물음                   「못 한 이유」 도 빠짐
#     일지 머리      한 일 · 본 것 · 할 일 · 못 한 이유 · 영상                      「납품 날짜」 빠짐(일지는 그 줄을 **보여 준다**)
#
# 그리고 기록을 넣고 일지를 그려 보니 줄머리가 **원장의 이름**이었다 — 「사건」 · 「관찰」 · 「계획」 · 「불이행 사유」. 2026-09-21 발행자 지적
# ("이런 답변을 보여 주는 것을 이해할 사람이 얼마나 될까?")의 그 말이고, 코드 주석도 그 표를 *"원장의 이름이고 개발자의 사유"* 라고 적어 두었다.
# **사람 말 가드가 그것을 못 봤다**: 운영 원장이 비어 있어 그 검사는 **줄 없는 화면**을 걸었다(가드가 있는데 자고 있던 자리 — 기록을 넣으니 둘이 붉었다).
#
# 고정하는 것 여덟:
#   ① 적을 수 있는 것은 **정본 하나**(`chat.WRITABLE`) — 범위는 `confirm()` 이 받는 종류 전부 + 물음(ast 로 세어 대조)
#   ② 화면 둘(머리말 · 입력칸 밑)이 그 목록을 **그대로** 보인다 — 하나라도 빠지면 붉다
#   ③ 일지 머리의 목록은 **일지가 펼치는 종류**에서 온다(`chat.DIARY_SHOWS`) — 납품 날짜가 빠져 있던 자리
#   ④ 원장이 쓰는 종류 전부가 일지에 갈래를 갖는다 — 없으면 농가가 **날것(JSON)** 을 읽는다(지금은 안 닿지만 쓰는 종류가 늘면 그날 난다)
#   ⑤ 일지 줄머리는 **사람 말**이고 정확한 이름은 버리지 않는다(화면의 title)
#   ⑥ 원장의 이름이 농가 화면에 **글로** 나오지 않는다(사람 말이 있는 종류는 전수)
#   ⑦ 사람 말 가드의 상태에 **기록이 실제로 있다**(검사의 검사 — 비면 그 가드가 눈을 감는다)
#   ⑧ 저장소에 그 목록의 **사본 리터럴**이 없다
from __future__ import annotations

import ast
import json
import re
from datetime import date
from pathlib import Path

import pytest

from frontend import chat_pages
from ingest import chat, events as ev, media
from tests.test_screen_speaks_plainly import JARGON, _records, _visible

ROOT = Path(chat.__file__).resolve().parent.parent
T = date(2026, 10, 7)


def _confirm_kinds() -> set[str]:
    """`confirm()` 이 받는 종류 — 소스 분기를 **세어** 온다(목록을 검사에 박으면 종류가 늘 때 조용히 지나간다)."""
    fn = next(n for n in ast.walk(ast.parse((ROOT / "ingest" / "chat.py").read_text(encoding="utf-8")))
              if isinstance(n, ast.FunctionDef) and n.name == "_confirm_locked")
    out: set[str] = set()
    for cmp_ in (n for n in ast.walk(fn) if isinstance(n, ast.Compare)):
        if isinstance(cmp_.left, ast.Name) and cmp_.left.id == "k":
            for c in cmp_.comparators:
                if isinstance(c, ast.Constant) and isinstance(c.value, str):
                    out.add(c.value)
    return out


def _ledger_kinds() -> set[str]:
    """사건 원장이 **쓰는** 종류 — `ingest/events.py` 의 레코드 리터럴에서 센다(add_* 가 하나 늘면 여기도 는다)."""
    src = (ROOT / "ingest" / "events.py").read_text(encoding="utf-8")
    return set(re.findall(r'"kind":\s*"([a-z._]+)"', src))


def test_what_can_be_written_is_one_canon():
    """[①] 목록의 **범위**는 정본이다 — `confirm()` 이 받는 종류 전부 + 물음(저장하지 않고 답한다)."""
    want = _confirm_kinds() | {"question"}
    assert set(chat.WRITABLE) == want, sorted(want ^ set(chat.WRITABLE))
    assert len(chat.WRITABLE) == len(set(chat.WRITABLE)), chat.WRITABLE
    said = chat.writable_said()
    assert len(said) == len(chat.WRITABLE) and all(said), said
    for w in said:
        assert "_" not in w and "." not in w, w                          # 사람 말이다(안쪽 이름이 아니다)


def test_the_two_places_that_offer_it_show_the_whole_list(tmp_path, monkeypatch):
    """[②] 채팅 머리말과 입력칸 밑이 **같은 목록**을 보인다 — 손으로 적었을 때 각각 하나씩 빠져 있었다."""
    s = media.load_subjects()[0]
    html = chat_pages.thread_main(s, T)                # 대화 화면 — 머리말(기록이 없을 때)과 입력칸 밑이 둘 다 여기 있다
    # 자리를 **따로** 본다 — 한 자리가 다 말하면 다른 자리의 누락이 가린다(주입 C 가 그렇게 통과했다 · §7.1 3번 미검사 가드)
    intro = _visible(html[html.index("그날 밭에서 있었던 일"):html.index("</div></div>", html.index("그날 밭에서 있었던 일"))])
    hint = _visible(html[html.index('id="hint"'):html.index("</span>", html.index('id="hint"'))])
    for place, text in (("머리말", intro), ("입력칸 밑", hint)):
        for w in chat.writable_said():
            assert w in text, (place, w, "그 자리가 적을 수 있는 것 하나를 빠뜨렸다")
    # 보기(예)는 흔한 셋에만 — 열 가지에 다 붙으면 읽히지 않는다
    assert intro.count("(오늘 물 줬다)") == 1 and "(잎이 누렇다)" in intro, intro[:200]


def test_the_diary_header_counts_what_the_diary_shows():
    """[③] 일지 머리의 목록은 일지가 펼치는 종류에서 온다 — 납품 날짜가 빠져 있었다."""
    s = media.load_subjects()[0]
    head = re.search(r"넣으신 것\(([^)]*)\)", _visible(chat_pages.diary_main(s, T)))
    assert head, "일지 머리에 목록이 없다"
    names = [x.strip() for x in head.group(1).split("·")]
    want = list(dict.fromkeys(chat.KIND_PLAIN[k] for k in chat.DIARY_SHOWS))
    assert names == want, (names, want)
    assert "납품 날짜" in names, names


def test_every_kind_the_ledger_writes_has_a_diary_branch():
    """[④] 원장이 쓰는 종류 전부가 일지에 갈래를 갖는다 — 없으면 그날 농가가 날것을 읽는다."""
    missing = _ledger_kinds() - set(chat.DIARY_SHOWS)
    assert missing == set(), f"일지가 모르는 기록 종류: {sorted(missing)}"
    assert "observation.video" in chat.DIARY_SHOWS                        # 영상은 원장이 아니라 매체 쪽 — 목록에는 있다
    fn = next(n for n in ast.walk(ast.parse((ROOT / "ingest" / "chat.py").read_text(encoding="utf-8")))
              if isinstance(n, ast.FunctionDef) and n.name == "diary")      # 구조로 자른다(파일 끝 함수라 「다음 def」 창이 없다 · 창은 약속이 된다)
    dumps = [c for c in ast.walk(fn) if isinstance(c, ast.Call) and getattr(c.func, "attr", "") == "dumps"]
    assert dumps == [], "일지 갈래가 레코드를 날것으로 낸다 — 농가가 읽을 줄이 아니다"


def test_the_diary_rows_say_the_plain_word_and_keep_the_exact_one(tmp_path):
    """[⑤] 줄머리는 사람 말 · 정확한 이름은 title 에(정확함을 버리지 않는다)."""
    sid = media.load_subjects()[0]["id"]
    _records(sid)
    rows = chat.diary(sid)
    assert len(rows) >= 5, rows
    for r in rows:
        assert r["label"] == chat.KIND_PLAIN.get(r["kind"], r["label"]) or r["label"] in ("사진", "영상"), r
        assert r.get("label_exact"), r
        assert "{" not in r["text"] and '"kind"' not in r["text"], r["text"]      # 날것이 본문에 안 들어간다
    html = chat_pages.diary_main(media.load_subjects()[0], T)
    for r in rows:
        assert f'title="{r["label_exact"]}"' in html, (r["label_exact"], "정확한 이름을 남길 자리가 없다")


def test_the_ledger_names_never_reach_the_farmer_as_text(tmp_path):
    """[⑥] 원장의 이름(사건 · 관찰 · 계획 · 불이행 사유 …)이 농가 화면의 **글**에 없다 — 사람 말이 따로 있는 종류는 전수."""
    sid = media.load_subjects()[0]["id"]
    _records(sid)
    seen = _visible(chat_pages.diary_main(media.load_subjects()[0], T))
    for kind, exact in chat.KIND_LABEL.items():
        plain = chat.KIND_PLAIN[kind]
        if exact == plain or kind not in chat.DIARY_SHOWS:
            continue
        assert exact not in seen, (kind, exact, "원장의 이름이 일지 글에 나왔다")
    assert not [w for w in JARGON if w in seen], [w for w in JARGON if w in seen]


def test_the_plain_words_guard_actually_has_rows(tmp_path):
    """[⑦] 검사의 검사 — 사람 말 가드가 **줄이 있는 화면**을 본다(비어 있으면 그 가드는 눈을 감는다)."""
    sid = media.load_subjects()[0]["id"]
    assert chat.diary(sid) == [], "이 검사의 전제 — 기록을 넣기 전에는 비어 있다"
    _records(sid)
    rows = chat.diary(sid)
    assert len(rows) >= 5 and {r["kind"] for r in rows} >= set(_ledger_kinds()), [r["kind"] for r in rows]
    seen = _visible(chat_pages.diary_main(media.load_subjects()[0], T))
    assert "아직 기록이 없다" not in seen and "물 줬다" in seen, seen[:200]


def test_no_copy_of_the_list_is_left_in_the_repo():
    """[⑧] 사본 리터럴이 없다 — 손 목록이 하나 남아 있으면 다음 회차에 그것만 낡는다."""
    copies = []
    # 화면을 **그리는** 모듈만 본다 — `scripts/build_ledger_page.py` 의 보고 문장은 그 회차에 한 일의 서술이고(지난 일) 흐르는 숫자 가드가 따로 본다.
    # 여기서 막는 것은 **살아 있는 목록의 사본**이다(그 사본이 다음 회차에 혼자 낡는다).
    for d in ("frontend", "ingest", "judge"):
        for f in sorted((ROOT / d).glob("*.py")):
            src = f.read_text(encoding="utf-8")
            body = "\n".join(ln for ln in src.splitlines() if not ln.lstrip().startswith("#"))
            for m in re.finditer(r"한 일[^\n\"']{0,8}·[^\n\"']{0,8}본 것", body):
                copies.append(f"{f.name}: {m.group(0)[:40]}")
    assert copies == [], copies
