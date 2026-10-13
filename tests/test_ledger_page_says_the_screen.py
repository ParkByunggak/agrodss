# -*- coding: utf-8 -*-
# [앞날 걷기 2026-10-13 — 발행자 한 수 하루 전] 대장 페이지가 발행자의 10/14 한 수를 이렇게 적고 있었다:
#     「채팅에 아무 말이나 한 줄 보내면 「밭 정보 → 종구 생산」 카드가 섭니다 → '일지에 넣기'」
# 화면의 그 카드는 「용도 → 종구 생산」 이고 단추는 「밭 정보에 넣기」 다. '일지에 넣기' 는 **방금 보낸 그 한 줄(본 것)** 의 단추라 안내대로 누르면
# 그 말이 일지에 들어가고 용도는 빈 채로 남는다 — 그러면 10/14 부터 잎 기준 경보 둘이 「주의」 로 나간다(그 안내가 막으려던 것).
# 같은 목록(⓪ˢ)은 「10/14 전에」 · 「**10/7 부터** 나갈」 · 「7일 전부터」 를 손으로 적어, 10/7 이 지나도 앞일로 말하고 10/14 가 지나도 「전에」 였다.
# 날수 래칫(test_best_counts_days_instead_of_typing_them)은 **BEST 블록 하나**만 보고 있었다 — 처방이 한 자리에 닿고 검사도 그 자리만 본 형태(§7.5 지점).
#
# 이 검사가 고정하는 것:
#   ① 페이지가 말하는 카드 머리 · 단추가 **실제 화면 카드**와 같다(채팅으로 카드를 세워 그려 보고 대조한다)
#   ② 두 목록과 BEST 에서 따옴표로 든 '…넣기' 는 실제 단추 이름이다 · 「X → Y」 카드에서 든 단추는 그 칸이 가는 자리의 단추다
#   ③ 정본에서 세는 날짜(경보 첫날 · 수확 창 · 그 전날)와 horizon 을 **세 블록 어디에도** 손으로 적지 않는다(인용 「…」 · 주석은 보기)
#   ④ 「10/14 전에」 꼴은 그날이 지나면 다른 말이 된다
#   ⑤ 두 목록의 강조(**…**)는 <b> 로 그려진다 — 별표가 글자로 보이지 않는다
from __future__ import annotations

import importlib
import re
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest

from frontend import chat_pages, words
from ingest import chat, parcels, subjects

ROOT = Path(__file__).resolve().parent.parent
SID = "p001-jjokpa-2026f"
QUOTED = re.compile(r"「[^」]*」")


def _page(monkeypatch=None, today: str | None = None):
    if today is not None:
        monkeypatch.setenv("AGRODSS_TODAY", today)
    return importlib.reload(importlib.import_module("scripts.build_ledger_page"))


def _visible(html: str) -> str:
    return re.sub(r"\s+", " ", re.sub(r"<[^>]*>", " ", html)).strip()


def _rows_text(page) -> str:
    return " ".join(h + " " + b for h, b in page.NEXT_PUBLISHER + page.NEXT_SESSION) + " " + " ".join(str(v) for v in page.BEST["do"].values())


def test_the_use_card_the_page_names_is_the_card_the_chat_draws(monkeypatch):
    page = _page(monkeypatch, "2026-10-13")
    m, _ = chat.send(SID, "종구용이다", today=date(2026, 10, 13), now=datetime(2026, 10, 13, tzinfo=timezone.utc))
    i, d = next((i, d) for i, d in enumerate(m["drafts"]) if d["kind"] == "parcel.field" and d.get("field") == "use")
    card = _visible(chat_pages._draft_html(m, i, d))
    head, button = page._USE["head"], page._USE["button"]
    assert head == f"{parcels.FIELD_WORDS['use']} → {d['value']}", (head, d)
    assert head in card and button in card, (head, button, card)                  # 화면 카드에 그 머리 · 그 단추가 있다
    assert chat.CONFIRM_LABEL not in card, card                                  # 그 카드에는 '일지에 넣기' 가 없다(옆 카드의 단추다)
    said = _rows_text(page)
    assert f"「{head}」 카드에서 '{button}'" in page.BEST["do"]["what"], page.BEST["do"]["what"]
    zs = next(h + b for h, b in page.NEXT_PUBLISHER if h.startswith("⓪ˢ"))
    assert f"「{head}」 카드에서 '{button}'" in zs, zs[:300]
    assert "「밭 정보 → " not in said, "카드 머리는 칸 이름이다(「용도 →」) — 「밭 정보 →」 는 화면에 없는 머리"


def test_the_page_says_how_to_find_a_card_that_is_already_standing(monkeypatch):
    """[검토 2026-10-13] 「카드가 안 보이면 아무 말이나 한 줄 보내면 섭니다」 는 카드가 이미 서 있으면 거짓이다(같은 카드는 다시 안 선다 — 발행자 PC 상태).
    셈 줄이 자리마다 세므로(「… 밭 정보 N」) 그 줄로 가른다 — 줄 이름 · 자리 이름은 화면 정본에서."""
    page = _page(monkeypatch, "2026-10-13")
    find = page._USE["find"]
    assert chat.PENDING_LABEL in find and chat.place_noun("parcel.field") in find, find
    zs = next(h + b for h, b in page.NEXT_PUBLISHER if h.startswith("⓪ˢ"))
    assert find in page.BEST["do"]["what"] and find in zs
    assert "안 보이면 아무 말이나" not in _rows_text(page)                         # 손으로 적은 옛 말이 안 남았다
    # 그 줄이 정말 그 이름으로 서는가 — 셈 줄 정본이 「밭 정보」 를 센다
    assert chat.place_noun("parcel.field") in chat.pending_said(["parcel.field"])


def test_every_quoted_button_on_the_page_is_a_real_button_and_the_right_one_for_its_card(monkeypatch):
    page = _page(monkeypatch, "2026-10-13")
    said = _rows_text(page)
    real = set(chat.CONFIRM_LABELS.values()) | {chat.CONFIRM_LABEL}
    quoted = re.findall(r"'([^']*넣기)'", said)
    assert quoted, "단추를 드는 자리가 하나도 안 세어진다 — 측정이 죽었다"
    assert set(quoted) <= real, sorted(set(quoted) - real)
    # [자기 도구 오류 2026-10-13] 처음엔 「X → Y」 카드를 전부 밭 정보 카드로 셌다 — 「증상 → 원인 좁히기」 는 **판단 카드의 이름**이다(탐지 축). 판단 이름은 걷는다
    judged = set(words.decision_table().values())
    heads = [w for w, rest in re.findall(r"「([^」→]+?) → ([^」]+)」 카드", said) if f"{w} → {rest}" not in judged]
    assert len(heads) >= 4, f"「칸 → 값」 카드를 드는 자리가 넷 아래다 — 측정이 죽었거나 자리가 줄었다: {heads}"   # ⓪ˢ · BEST · ⓪ʷ · ⓪⁻(2026-10-13 전수)
    for word in heads:                                                           # 카드 머리는 화면 카드의 칸 이름이다(「밭 정보 →」 는 화면에 없는 머리)
        assert _kind_of(word), f"「{word} →」 는 화면 카드의 칸 이름이 아니다"
    pairs = re.findall(r"「([^」→]+?) → [^」]+」 카드[^'「」]{0,40}'([^']+넣기)'", said)
    assert len(pairs) >= 4, f"카드와 단추를 함께 드는 자리가 넷 아래다: {pairs}"
    for word, button in pairs:
        assert button == chat.confirm_label(_kind_of(word)), (word, button, chat.confirm_label(_kind_of(word)))


def _kind_of(word: str) -> str | None:
    """카드 머리의 칸 이름 → 그 카드가 가는 자리(밭 정보 · 농사 정보). 화면 카드가 쓰는 같은 낱말 표에서."""
    return ("parcel.field" if word in parcels.FIELD_WORDS.values()
            else "subject.field" if word in subjects.SUBJECT_FIELD_WORDS.values() else None)


def test_the_check_catches_the_old_line():
    """검사의 검사 — 옛 문면을 넣으면 위 대조가 잡는다(단추가 실제 이름이긴 하지만 그 카드의 단추가 아니다 · 머리가 화면에 없다)."""
    old = "채팅에 아무 말이나 한 줄 보내면 「밭 정보 → 종구 생산」 카드가 섭니다 → '일지에 넣기'"
    (word,) = re.findall(r"「([^」→]+?) → [^」]+」 카드", old)
    assert word == "밭 정보" and _kind_of(word) is None                            # 머리 검사가 옛 머리를 잡는다
    (word, button), = re.findall(r"「([^」→]+?) → [^」]+」 카드[^'「」]{0,40}'([^']+넣기)'", old)
    assert button != chat.confirm_label("parcel.field")                          # 단추 검사도 옛 단추를 잡는다(머리가 맞았어도)
    (word, button), = re.findall(r"「([^」→]+?) → [^」]+」 카드[^'「」]{0,40}'([^']+넣기)'", "「배수 → 좋음」 카드가 서고 '일지에 넣기' 한 번")
    assert _kind_of(word) == "parcel.field" and button != chat.confirm_label("parcel.field")


def _blocks(src: str) -> dict[str, str]:
    """구조로 자른다 — 할당 이름에서 그 목록의 끝까지(줄 번호 · 리터럴을 박지 않는다)."""
    out = {}
    for name, end in (("NEXT_PUBLISHER = [", "\n]\n"), ("NEXT_SESSION = [", "\n]\n"), ("\nBEST = {", "\nBEST_MAX_LINES")):
        a = src.index(name)
        out[name.strip(" =[{\n")] = src[a:src.index(end, a)]
    return out


def _typed(block: str) -> str:
    """손으로 적은 글만 — 주석 줄 · 인용(「…」) · 계산해 넣은 자리({…})를 걷는다."""
    lines = [ln for ln in block.splitlines() if not ln.lstrip().startswith("#")]
    return re.sub(r"\{[^{}]*\}", " ", QUOTED.sub(" ", "\n".join(lines)))


def test_no_block_types_a_date_or_a_day_count_that_the_canon_counts(monkeypatch):
    page = _page(monkeypatch, "2026-10-13")
    src = (ROOT / "scripts" / "build_ledger_page.py").read_text(encoding="utf-8")
    blocks = _blocks(src)
    assert set(blocks) == {"NEXT_PUBLISHER", "NEXT_SESSION", "BEST"}, set(blocks)
    canon = {page.alert_start(), page.harvest_window_start(), page.harvest_window_start() - timedelta(days=1)}
    forms = {f for d in canon for f in (f"{d.month}/{d.day}", f"{d.month:02d}/{d.day:02d}")}
    for name, block in blocks.items():
        typed = _typed(block)
        hits = [f for f in forms if re.search(rf"(?<![\d/]){re.escape(f)}(?![\d/])", typed)]
        assert not hits, f"{name}: 정본이 세는 날짜를 손으로 적었다 — {hits} (when()/md() 로)"
        assert not re.search(rf"(?<!\d){page.horizon()}일 전", typed), f"{name}: horizon({page.horizon()}일)을 손으로 적었다 — {{_HORIZON}} 으로"


def test_the_typed_check_is_alive():
    typed = _typed('("⓪ˢ 경보는 10/7 부터 나갈 · 7일 전부터", f"{when(_ALERT_FROM)} 「10/7 부터(내일)」")\n    # 9/20 주석')
    assert "10/7" in typed and "7일 전" in typed                                    # 손으로 적은 것은 남는다
    assert typed.count("10/7") == 1 and "9/20" not in typed                         # 인용 · 계산 · 주석은 걷힌다


@pytest.mark.parametrize("delta,want,unwanted", [(-1, "전에(내일)", "「주의」 로 나가고 있습니다"),
                                                  (1, "「주의」 로 나가고 있습니다", "전에(")])
def test_the_by_when_phrase_turns_once_the_window_has_opened(monkeypatch, delta, want, unwanted):
    page = _page(monkeypatch, "2026-10-13")
    day = page.harvest_window_start() + timedelta(days=delta)
    page = _page(monkeypatch, day.isoformat())
    zs = next(h for h, _ in page.NEXT_PUBLISHER if h.startswith("⓪ˢ"))
    assert want in zs and unwanted not in zs, zs[-160:]


def test_the_alert_phrase_counts_from_the_canon_on_both_sides_of_it(monkeypatch):
    page = _page(monkeypatch, "2026-10-13")
    first = page.alert_start()
    for day, rel in ((first - timedelta(days=1), "(내일)"), (first + timedelta(days=6), "(6일 전)")):
        page = _page(monkeypatch, day.isoformat())
        body = next(b for h, b in page.NEXT_PUBLISHER if h.startswith("⓪ˢ"))
        assert f"{first.month}/{first.day} 부터{rel}" in body, (day, body[:200])
        assert f"{page.horizon()}일 전부터" in body


def test_the_lists_draw_their_emphasis_instead_of_showing_asterisks(monkeypatch):
    page = _page(monkeypatch, "2026-10-13")
    raw = sum((h + b).count("**") for h, b in page.NEXT_PUBLISHER + page.NEXT_SESSION)
    assert raw >= 2, "목록에 강조가 하나도 없다 — 이 검사가 뜻을 잃었다"
    out = page.li(page.NEXT_PUBLISHER + page.NEXT_SESSION)
    assert "**" not in out, out[out.index("**") - 80:out.index("**") + 40]
    assert page._bold("가 **나** 다 **라**") == "가 <b>나</b> 다 <b>라</b>"
