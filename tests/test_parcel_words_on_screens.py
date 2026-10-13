# -*- coding: utf-8 -*-
# [앞날 걷기 2026-10-13 — 발행자 한 수 하루 전] 발행자가 10/14 에 용도를 넣는 두 길 가운데 **밭 정보 화면**의 길을 걸으니, 답과 대장은 그 값을
# 「용도」 · 「배수」 로 부르는데 그 화면만 다른 말이었다:
#   ① 고르는 칸 이름이 안쪽 키   environment · soil_texture · slope · drainage · irrigation · night_light
#   ② 입력 대기 줄                「입력 대기 13: lat, lon, area_m2, use, soil_texture, …」 · 채팅 옆 칸 「필지 입력 대기 13 lat, lon, …」(물러난 말 · 어디서 넣는지 없음)
#   ③ 머리와 저장 줄이 등록부 id  「p001 · 용도 미기재 …」 · 「밭 정보(p001) 저장」(2026-10-04 표의 목록 칸을 농사 이름으로 바꾼 처방이 밭 쪽엔 안 닿았다)
#   ④ 모든 화면의 사용자 탭       「필지 0」 — 사용자 정보 파일에 찍어 둔 사본을 셌다(그 파일이 없으면 0 · 밭 정보 화면은 같은 때 밭 하나)
# 처방: 칸의 사람 말은 정본 하나(parcels.FIELD_WORDS → parcels.field_word — 없던 셋을 채움 · 위도 · 경도는 「좌표」 하나) · 입력 대기 말도 그 하나(missing_words) ·
# 밭을 부르는 말은 짓는 작목으로(words.parcel_label) · 탭은 등록부에서 센다. 정확한 키 · id 는 title 에 남긴다(정확함을 안 버린다).
# [검토 2026-10-13] 같은 회차의 검토가 더 가른 것: 이 화면에 칸이 없는 것(좌표 · 토양 검정 근거)은 「이 화면 밖」 으로 따로 센다(다 채워도 「입력 대기 2」 가 남았다) ·
# 밭 정보에 없는 밭은 「… 에서 넣습니다」 대신 없다고 말한다 · 새 채팅의 밭 칸은 고른다(id 를 적게 하면서 id 를 안 보였다) · 등록부를 못 읽으면 수를 지어내지 않는다(?) ·
# 마친 농사는 밭 이름에서 빼고 같은 이름의 밭은 id 로 가른다.
# 같은 회차에 대장 페이지의 내 문장도 고쳤다(F32 · F33): 화면에 없는 옛 길(「사용자 탭 → 설정 → 필지 구역」) · 손으로 적은 셈(「그 열두 줄」 — 셈은 14) ·
# 옛 길을 지운 자리에 **옛 화면을 가르는 표지**(꼬리의 커밋 — 자동 갱신이 안 돈 PC 는 그 단추가 없다).
from __future__ import annotations

import html
import importlib
import json
import re
from pathlib import Path
from urllib.parse import quote

import pytest

from frontend import autopull, chat_pages, words
from ingest import media, parcels, profile
from schema import labels
from tests.test_brand_home import srv  # noqa: F401
from tests.test_publisher_path_http import _get, _post

ROOT = Path(__file__).resolve().parent.parent
SID = "p001-jjokpa-2026f"
KEY_RE = re.compile(r"(?<![A-Za-z_])(" + "|".join(sorted(parcels.missing_inputs({}), key=len, reverse=True)) + r")(?![A-Za-z_])")


def _visible(page: str) -> str:
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]*>", " ", re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", page, flags=re.S))))


def test_every_waiting_key_and_every_form_field_has_a_farmer_word():
    keys = parcels.missing_inputs({})
    assert len(keys) >= 14, keys                                                   # 측정이 살아 있다 — 입력 대기 전부
    assert not [k for k in keys if k not in parcels.FIELD_WORDS], [k for k in keys if k not in parcels.FIELD_WORDS]
    assert set(parcels.FIELD_WORDS) >= set(parcels.input_fields())
    said = parcels.missing_words({})
    assert said.count("좌표") == 1 and "위치" not in said and not any(KEY_RE.search(w) for w in said), said   # 위도 · 경도는 「좌표」 하나(「위치 있음」 과 다른 말) · 안쪽 키가 말로 새지 않는다
    assert len(said) == len(dict.fromkeys(parcels.FIELD_WORDS[k] for k in keys))


def test_here_and_away_split_the_waiting_words_by_whether_the_screen_has_a_box():
    """이 화면에서 넣을 수 있는 것(here) 과 없는 것(away — 좌표 · 토양 검정 근거) 은 서로 겹치지 않고 합치면 전부다."""
    here, away, every = parcels.missing_words({}, here=True), parcels.missing_words({}, here=False), parcels.missing_words({})
    assert set(here) | set(away) == set(every) and not set(here) & set(away), (here, away)
    assert "좌표" in away and "좌표" not in here and "토양 검정 근거" in away            # 주소 · 좌표는 폼에도 없다(PII) · 검정 근거는 칸이 없다
    assert here and set(here) == {parcels.FIELD_WORDS[k] for k in parcels.input_fields()}


def test_field_word_is_one_place_for_both_tables():
    """두 표 찾기(FIELD_WORDS → SUBJECT_FIELD_WORDS)가 다섯 군데 손으로 적혀 있었다 — 정본 하나(parcels.field_word)를 다 쓴다."""
    from ingest import chat, subjects
    assert parcels.field_word("use") == parcels.FIELD_WORDS["use"] and parcels.field_word("cert") == subjects.SUBJECT_FIELD_WORDS["cert"]
    assert parcels.field_word("없는칸") == "없는칸" and chat.field_word("cert") == parcels.field_word("cert")
    for rel in ("frontend/words.py", "frontend/chat_pages.py", "ingest/chat.py"):
        src = (ROOT / rel).read_text(encoding="utf-8")
        assert "SUBJECT_FIELD_WORDS.get(" not in src, rel                           # 사본이 다시 생기면 붉다


def test_the_parcel_screen_speaks_field_words_and_keeps_the_keys_in_titles(srv):
    st, _, page = _get(srv, "/me")
    v = _visible(page)
    assert st == 200
    for key in parcels.FIELD_CHOICES:                                              # 고르는 칸 — 사람 말 · 키는 title
        assert f'<label title="{key}">{html.escape(parcels.FIELD_WORDS[key])}' in page, key
    p = parcels.by_id("p001")
    here, away = parcels.missing_words(p, here=True), parcels.missing_words(p, here=False)
    assert f"입력 대기 {len(here)}: {' · '.join(here)}" in v, v[v.find("입력 대기"):][:200]
    assert (f"이 화면 밖 {len(away)}: {' · '.join(away)}" in v) == bool(away) and away, v[v.find("입력 대기"):][:300]
    assert f"입력 대기 {len(parcels.missing_words(p))}:" not in v                   # 한 줄로 다 세지 않는다(다 채워도 2 가 남는 셈)
    assert words.parcel_label("p001") in v and f'title="{p["id"]}"' in page      # 머리는 밭을 부르는 말 · id 는 title
    # 구역은 **구조로** 자른다(밭 정보 머리 ~ 다음 구역 머리) — 첫 등장 · 글자 창으로 자르면 왼쪽 메뉴 꼬리에서 시작해 둘째 카드부터 빠진다(재검토 TV-7)
    sect_html = page[page.index('<h2 id="parcel"'):page.index('<h2 id="sync"')]
    sect = _visible(sect_html)
    # 표지도 저장 줄과 같은 말(판단 · 밭 정보) — 셋 다(판단이 읽는 값 · 읽는 판단 없음 · 다른 소비자). 칸 하나를 label 요소째 잘라 본다
    for key in ("drainage", "use"):
        lab = sect_html.split(f'<label title="{key}">', 1)[1]
        lab = lab[:lab.index("</label>")]
        assert html.escape(parcels.FIELD_WORDS[key]) in lab and html.escape(chat_pages.READS_LABEL) in lab, (key, lab)
    assert chat_pages.READS_LABEL == "판단이 읽는 값" and "판정" not in sect, sect[sect.find("판정") - 60:][:120]
    assert "인증 근거" in sect and "판단은 안 읽는다" in sect                        # 셋째 표지(다른 소비자)가 실제로 그려진 상태에서 본다
    assert not KEY_RE.search(sect), KEY_RE.findall(sect)                         # 밭 정보 구역에 안쪽 키가 글로 보이지 않는다
    assert "필지" not in v


def _side_card(page: str, head: str) -> str:
    """옆 칸의 그 카드 하나 — 다음 카드 앞까지(구조로 자른다 · 글자 창 대신)."""
    a = page.index(f'<div class="card"><b>{head}')
    nxt = page.find('<div class="card', a + 10)
    return _visible(page[a:nxt if nxt > 0 else len(page)])


def test_the_chat_side_panel_counts_only_what_that_screen_can_take_and_says_where(srv):
    st, _, page = _get(srv, f"/c/{quote(SID)}")
    v = _visible(page)
    here = parcels.missing_words(parcels.by_id("p001"), here=True)
    head = f"{labels.ME_SECTIONS['parcel']} 입력 대기 {len(here)}"
    card = _side_card(page, head)
    assert st == 200 and labels.PLACES["parcel"] in card and " · ".join(here[:6]) in card, card
    assert f"입력 대기 {len(parcels.missing_words(parcels.by_id('p001')))}" not in v  # 좌표 · 토양 검정 근거는 그 화면에 칸이 없다 — 「… 에서 넣습니다」 에 못 든다
    assert "좌표" not in card and not KEY_RE.search(card), card
    assert "필지" not in v


def test_the_side_panel_says_the_field_is_missing_instead_of_where_to_fill_it(srv, monkeypatch):
    """밭 정보에 없는 밭이면 「… 에서 넣습니다」 가 거짓이다 — 그 화면에 그 밭의 칸이 없다."""
    monkeypatch.setattr(parcels, "by_id", lambda pid, path=None: None)
    st, _, page = _get(srv, f"/c/{quote(SID)}")
    v = _visible(page)
    assert st == 200 and f"이 농사의 밭이 {labels.ME_SECTIONS['parcel']}에 없습니다" in v, v[:400]
    assert "에서 넣습니다" not in v and 'title="p001"' in page


def test_the_user_tab_counts_the_registry_not_a_saved_copy(srv, monkeypatch):
    """사용자 정보 파일이 없거나(새 PC) 옛 사본이어도 탭의 밭 수는 등록부와 같다 — 밭 정보 화면의 카드 수와 같다.
    [재검토 2026-10-13] 첫 판은 파일이 원래 없는 격리에서 지우기만 해 「옛 사본」 갈래를 한 번도 안 걸었다 — 등록부와 다른 수의 사본을 실제로 쓴다."""
    n = len(parcels.load())
    assert n >= 1 and not profile.path().exists()                                  # 갈래 ① 새 PC — 파일 없음
    stale = {"id": "u001", "kind": "user", "name": "검사", "role": "farmer", "parcels": ["p001", "p777", "p888"],
             "source": "publisher", "recorded_at": "2026-10-01T00:00:00+09:00"}
    for case in ("없음", "옛 사본"):
        if case == "옛 사본":                                                    # 갈래 ② 옛 사본 — 밭 셋이 찍힌 사용자 정보(등록부는 n)
            profile.path().parent.mkdir(parents=True, exist_ok=True)
            profile.path().write_text(json.dumps(stale, ensure_ascii=False), encoding="utf-8")
            assert len(profile.load()["parcels"]) != n
        for p in ("/me", f"/c/{quote(SID)}", "/judge"):
            st, _, page = _get(srv, p)
            v = _visible(page)
            assert st == 200 and f"{labels.ME_SECTIONS['parcel']} {n} · 메뉴" in v, (case, p, v[v.find("메뉴") - 40:][:60])
    st, _, page = _get(srv, "/me")
    sect = page[page.index('<h2 id="parcel"'):page.index('<h2 id="sync"')]
    assert sect.count('<div class="card"><b title="') == n                         # 밭 정보 화면의 밭 카드 수와 **같은** 셈


@pytest.mark.parametrize("doc", [{"parcels": "이건 목록이 아니다"}, [], {"parcels": None}, {"parcels": [{"id": ["p001"]}]}, {"parcels": [{"use": "자가"}]}])
def test_an_unreadable_registry_shows_a_question_mark_not_a_number(srv, monkeypatch, tmp_path, doc):
    """등록부 모양이 틀리면 수를 지어내지 않는다(?) — 새 채팅의 밭 칸도 고르는 칸 대신 적는 칸으로(이유는 title).
    [재검토 2026-10-13] id 가 글이 아닌 줄은 모양 검사를 지나 합치는 자리에서 TypeError — **모든 화면이 응답 없이** 끊겼다(404 · 500 화면까지)."""
    bad = tmp_path / "parcels_bad.json"
    bad.write_text(json.dumps(doc), encoding="utf-8")
    monkeypatch.setenv("AGRODSS_PARCELS_PATH", str(bad))
    with pytest.raises(ValueError):
        parcels.load()
    st, _, page = _get(srv, "/c/new")
    v = _visible(page)
    assert st == 200 and f"{labels.ME_SECTIONS['parcel']} ? · 메뉴" in v, v[v.find("메뉴") - 40:][:60]
    assert '<select name="parcel"' not in page and '<input name="parcel"' in page and 'placeholder="밭 정보를 못 읽었습니다' in page
    assert not labels.retired_in(page.split('<input name="parcel"', 1)[1].split(">", 1)[0])   # 대체 칸의 글(placeholder)에도 물러난 이름이 없다
    for p in ("/events", "/nope404"):                                             # 다른 화면은 응답한다(끊기지 않는다)
        st2, _, _ = _get(srv, p)
        assert st2 in (200, 404), (p, st2)
    # 비워 두고 만들면 이유가 오류 줄로 — 사람 말 · 안쪽 키 없이(고칠 파일 이름은 둔다)
    st, _, page = _post(srv, "/c/new", {"crop": "쪽파", "season": "2027 봄", "status": "계획", "parcel": ""})
    err = _visible(page.split('class="err"', 1)[1].split("</p>", 1)[0]) if 'class="err"' in page else ""
    assert "밭 정보를 읽지 못했습니다" in err and "(parcels)" not in err and not KEY_RE.search(err), err


def test_an_empty_registry_says_empty_not_unreadable(srv, monkeypatch, tmp_path):
    empty = tmp_path / "parcels_empty.json"
    empty.write_text(json.dumps({"parcels": []}), encoding="utf-8")
    monkeypatch.setenv("AGRODSS_PARCELS_PATH", str(empty))
    assert parcels.load() == []
    st, _, page = _get(srv, "/c/new")
    assert st == 200 and 'placeholder="밭 정보에 밭이 아직 없습니다"' in page and "못 읽었습니다" not in page


def test_the_new_chat_picks_the_field_by_its_name_and_sends_the_id(srv):
    st, _, page = _get(srv, "/c/new")
    assert st == 200 and '<select name="parcel" required>' in page and '<input name="parcel"' not in page
    for p in parcels.load():
        assert f'<option value="{p["id"]}" title="{p["id"]}"' in page and html.escape(words.parcel_label(p["id"])) in page, p["id"]
    if len(parcels.load()) == 1:                                                   # 하나면 이미 골라져 있다(빈 칸 없음)
        assert ' selected>' in page and '<option value=""' not in page
    assert "필지" not in _visible(page)


def test_two_fields_make_the_farmer_choose_instead_of_sending_the_first(srv, monkeypatch, tmp_path):
    """[재검토 2026-10-13] 아무것도 안 고른 목록은 브라우저가 **첫 밭을 보낸다** — 대표값을 대신 고르는 꼴(subjects.add 의 가드가 닿지 못했다)."""
    seed = json.loads(parcels.parcels_path().read_text(encoding="utf-8"))
    two = dict(seed, parcels=list(seed["parcels"]) + [dict(seed["parcels"][0], id="p002")])
    reg = tmp_path / "parcels_two.json"
    reg.write_text(json.dumps(two, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setenv("AGRODSS_PARCELS_PATH", str(reg))
    assert [p["id"] for p in parcels.load()] == ["p001", "p002"]
    st, _, page = _get(srv, "/c/new")
    sel = page.split('<select name="parcel" required>', 1)[1].split("</select>", 1)[0]
    assert sel.startswith('<option value="" selected>') and sel.count(" selected") == 1, sel     # 빈 칸이 먼저 · 그것만 골라져 있다
    assert "p002" not in _visible(sel)                                             # 작목 없는 둘째 밭도 번호가 글로 안 나간다
    st, _, page = _post(srv, "/c/new", {"crop": "쪽파", "season": "2027 봄", "status": "계획", "parcel": ""})
    assert "어느 밭인지 고릅니다" in _visible(page), _visible(page)[:300]          # 서버 가드도 그대로 선다


def test_the_save_sentence_names_the_field_not_the_registry_id(srv):
    st, _, page = _post(srv, "/me/parcel", {"id": "p001", "drainage": "좋음"})
    v = _visible(page)
    assert st == 200 and f"{labels.ME_SECTIONS['parcel']} 저장({words.parcel_label('p001')})" in v and "(p001)" not in v, v[:300]
    rec = parcels.by_id("p001")
    # 저장 줄의 셈도 이 화면에서 넣을 수 있는 것만 — 같은 응답의 밭 카드에도 「입력 대기 N」 이 있어 화면 전체에서 찾으면 그쪽에 걸린다(§7.1 4번 · 주입 K 실측) — 저장 줄만 잘라 본다
    said = v[v.index(f"{labels.ME_SECTIONS['parcel']} 저장("):]
    said = said[:said.index("입력 대기") + 20]
    assert re.search(r"· 입력 대기 (\d+)", said).group(1) == str(len(parcels.missing_words(rec, here=True))), said
    assert len(parcels.missing_words(rec, here=True)) != len(parcels.missing_words(rec))   # 두 셈이 갈리는 조건이어야 이 검사가 뜻이 있다
    assert words.parcel_label("없는밭") == words.NO_CROP_FIELD                     # 짓는 작목이 없으면 그 사실을 말한다(지어내지 않는다 · id 를 글로 안 낸다)


def test_parcel_label_drops_ended_crops_and_tells_same_named_fields_apart(monkeypatch):
    rows = [{"id": "a", "parcel": "p001", "crop": "쪽파", "status": "종료"}, {"id": "b", "parcel": "p001", "crop": "대파", "status": "재배 중"},
            {"id": "c", "parcel": "p002", "crop": "대파", "status": "재배 중"}, {"id": "d", "parcel": "p003", "crop": "마늘", "status": "종료"},
            {"id": "e", "parcel": "p004", "crop": "배추", "status": "계획"},
            {"id": "x", "parcel": ["p001"], "crop": 5, "status": "재배 중"}]          # 손으로 고친 덮개의 글 아닌 값 — 건너뛴다(화면이 죽지 않게)
    monkeypatch.setattr(media, "load_subjects", lambda path=None: rows)
    monkeypatch.setattr(parcels, "load", lambda path=None: [{"id": "p002"}, {"id": "p001"}, {"id": "p005"}, {"id": "p006"}])
    # 마친 쪽파는 빠지고 · 같은 이름은 **밭 정보의 순서**로 가른다(p002 가 먼저) — id 는 글에 없다
    assert words.parcel_label("p002") == "대파 밭 · 첫째" and words.parcel_label("p001") == "대파 밭 · 둘째"
    assert words.parcel_label("p003") == "마늘 밭" and words.parcel_label("p004") == "배추 밭"               # 다 마쳤어도 그 작목으로 · 계획도 짓는 농사
    assert words.parcel_label("p005") == f"{words.NO_CROP_FIELD} · 첫째" and words.parcel_label("p006") == f"{words.NO_CROP_FIELD} · 둘째"
    assert words.parcel_label("p009") == words.NO_CROP_FIELD and words.parcel_label("") == ""
    for pid in ("p001", "p002", "p005", "p006"):
        assert pid not in words.parcel_label(pid)

    def boom(path=None):
        raise ValueError("깨진 덮개")
    monkeypatch.setattr(media, "load_subjects", boom)
    assert words.parcel_label("p001") == words.UNREAD_FIELD                        # 못 읽으면 지어내지 않는다 — 못 읽었다고 말한다
    monkeypatch.setattr(media, "load_subjects", lambda path=None: rows)
    monkeypatch.setattr(parcels, "load", boom)
    assert words.parcel_label("p003") == "마늘 밭"                                 # 밭 정보를 못 읽어도 작목으로는 부른다


def test_the_missing_parcel_error_speaks_to_the_farmer(srv):
    st, _, page = _post(srv, "/me/parcel", {"drainage": "좋음"})
    v = _visible(page)
    assert "어느 밭의 정보인지 적혀 있지 않습니다" in v and "parcel id" not in v and "필지" not in v, v[:300]


@pytest.mark.parametrize("path", ["/", f"/c/{quote(SID)}", f"/diary/{quote(SID)}", "/judge", "/events", "/media", "/me", "/me/decisions",
                                  "/me/outlook", "/selfcheck", "/improve", "/c/new"])
def test_no_screen_says_the_retired_word_or_shows_a_raw_parcel_key(srv, path):
    """전수 — 화면 열둘. /changes 는 뺀다: 그 화면의 「읽다 버린 것」 은 원장 경로(예: risk_alert/drainage)를 정확한 값으로 싣는 개발 기록이다(등재 후보 — F29 와 같은 자리).
    [재검토 2026-10-13] 「/」 는 302 빈 본문이라 아무것도 안 봤다 — 넘겨주는 곳까지 따라가고, 빈 본문은 통과하지 못한다."""
    st, loc, page = _get(srv, path)
    if st == 302:
        st, _, page = _get(srv, loc)
    v = _visible(page)
    assert st == 200 and len(v) > 200, (path, st, len(v))
    assert "필지" not in v, (path, v[v.find("필지") - 60:][:120])
    assert not KEY_RE.search(v), (path, KEY_RE.findall(v)[:5])


def test_the_decision_asks_do_not_use_a_retired_screen_name():
    """H-후보㉣ 가 「재배 목록」(물러난 이름)으로 묻고 있었다 — 결정 화면의 물음도 농가 글이다."""
    from ingest import decisions
    bad = {d["id"]: labels.retired_in(d.get("ask", "") + " " + d.get("default", "")) for d in decisions.ITEMS}
    assert not {k: v for k, v in bad.items() if v}, {k: v for k, v in bad.items() if v}


# ── 대장 페이지 — 같은 회차의 내 문장 둘(F32 · F33) ───────────────────────────────────────
def _page(monkeypatch, today="2026-10-13"):
    monkeypatch.setenv("AGRODSS_TODAY", today)
    return importlib.reload(importlib.import_module("scripts.build_ledger_page"))


def test_the_page_does_not_send_the_publisher_down_a_path_the_screen_no_longer_has(monkeypatch):
    page = _page(monkeypatch)
    said = " ".join(h + " " + b for h, b in page.NEXT_PUBLISHER) + " " + " ".join(str(v) for v in page.BEST["do"].values())
    for old in ("필지 구역", "설정 → 필지", "지금 화면에선", "지금 바로는 맨 아래"):
        assert old not in said, old
    assert labels.PLACES["parcel"] in page.BEST["do"]["where"]                      # 길은 화면 이름 정본에서
    # 옛 길을 지운 자리에 옛 화면을 가르는 표지 — 자동 갱신이 안 돈 PC 는 그 단추가 없다. 한 문장을 BEST 와 ⓪ˢ 둘 다 쓴다
    # [재검토 2026-10-13] 표지는 **두 길 다** 앞에 — 채팅 카드 길의 셈 줄 안내도 10-13 커밋에서 생겼다(밭 정보 길에만 붙어 있었다)
    zs = next(h for h, b in page.NEXT_PUBLISHER if h.startswith("⓪ˢ"))
    assert page._ON_HEAD in page.BEST["do"]["where"] and "두 길 다" in page._ON_HEAD and "꼬리의 실행 중 커밋" in page._ON_HEAD
    assert page._ON_HEAD in zs and zs.index(page._ON_HEAD) < zs.index("채팅의") < zs.index(labels.PLACES["parcel"]), zs
    # [재검토] 「갱신 … → … — 새 코드로 다시 뜬다」 는 2초 남짓만 보인다(다시 뜨면 상태가 빈다) — 머무는 꼬리를 인용한다. 꼴은 화면 꼬리 정본과 같다
    from frontend import config as fconfig, serve
    tail, just = page.tail_after_pull(), page.tail_just_after()
    assert tail == f"실행 중 {page.head} · " + autopull.status_line(600, {"result": "최신", "at": "0000-00-00 HH:MM"})
    assert just == f"실행 중 {page.head} · " + autopull.status_line(600, None)
    assert f"실행 중 {serve.RUNNING_HEAD} · {autopull.status_line(fconfig.AUTO_PULL_SEC)}" in serve.footer_text()   # 인용한 꼴이 실제 꼬리의 꼴
    zero = next(b for h, b in page.NEXT_PUBLISHER if h.startswith("⓪ <b>update.bat"))
    assert f"「{tail}」" in zero and f"「{just}」" in zero and "9903974 →" not in zero and "새 코드로 다시 뜬다」" not in zero
    four = next(h for h, b in page.NEXT_PUBLISHER if h.startswith("④"))
    assert "둘 다 그 화면에 있다" in four and "열두 줄" not in four


def test_the_registry_question_counts_what_is_still_open_from_one_list(monkeypatch):
    """[재검토 2026-10-13 즉시] ⓪ᴿ 첫 판이 「농가 답을 틀리게 하는 것은 고쳤습니다」 라고 했다 — 즉시급 열둘이 남아 있었다(그 전제로 등재를 물으면 거짓 전제).
    남은 수는 목록(_WALK_OPEN)에서 세고, 그 목록은 핸드오버의 마지막 「남은 즉시급」 줄과 같다 — 두 기록이 갈리면 붉다."""
    page = _page(monkeypatch)
    body = next(b for h, b in page.NEXT_PUBLISHER if h.startswith("⓪ᴿ"))
    assert f"아직 {len(page._WALK_OPEN)} 이 남았습니다" in body and all(f in body for f in page._WALK_OPEN), body[:300]
    assert "고쳤습니다. 아래는" not in body and "지금 답은 그대로입니다" not in body             # 남은 것이 있는데 다 고쳤다고 하지 않는다
    hand = (ROOT / "docs" / "handover_20260919.md").read_text(encoding="utf-8")
    lines = re.findall(r"\*\*남은 즉시급[^*]*\*\*\(앞날 걷기 — 세션 몫\): ([^\n—]+)", hand)
    assert lines, "핸드오버에 「남은 즉시급」 줄이 없다 — 측정이 죽었다"
    assert tuple(re.findall(r"F\d+", lines[-1])) == page._WALK_OPEN, (lines[-1], page._WALK_OPEN)


def test_the_retired_check_reads_the_visible_text_and_covers_all_of_best(monkeypatch):
    """[재검토 2026-10-13] 원문에서 찾으면 꾸밈 태그가 이름을 쪼개 숨겼다(⑤ 「<b>설정</b>(<code>/me</code>)」) · BEST 의 「한 것」 은 검사 밖이었다."""
    page = _page(monkeypatch)
    assert page.check_retired([("t", "<b>설정</b>(<code>/me</code>)")]) and page.check_retired([("t", "밭 정보 화면")])
    keys = {k for k, _ in page.RETIRED_SCOPE}
    assert {"BEST.blocked", "BEST.did0"} <= keys and sum(k.startswith("BEST.did") for k in keys) == len(page.BEST["did"])
    five = next(b for h, b in page.NEXT_PUBLISHER if h.startswith("⑤"))
    assert f"「{labels.label('/me')}」 → 「장기 전망 등재 →」" in five
    # ⓪ʷ 의 메모 인용은 메모 정본 전체를 낱말 표에 통과시킨 그 글 — 뒷절반을 손으로 적어 화면과 달랐다
    from judge import risk_alert
    zw = next(b for h, b in page.NEXT_PUBLISHER if h.startswith("⓪ʷ"))
    assert f"「{words.plain(risk_alert.NO_DRAINAGE_NOTE)}」" in zw and "필지" not in zw


# [재검토 2026-10-13] 11 의 관형형 「열한」 이 빠져 있었다(「그 열한 줄」 이 지났다) — 열 · 스물 뒤 꼴을 규칙으로
NUM = "(열(?:하나|한|둘|두|셋|세|넷|네|다섯|여섯|일곱|여덟|아홉)|스물(?:하나|한|둘|두|셋|세|넷|네|다섯|여섯|일곱|여덟|아홉)?|스무)"


def _typed_blocks() -> dict[str, str]:
    src = (ROOT / "scripts" / "build_ledger_page.py").read_text(encoding="utf-8")
    out = {}
    for name, end in (("NEXT_PUBLISHER = [", "\n]\n"), ("NEXT_SESSION = [", "\n]\n"), ("\nBEST = {", "\nBEST_MAX_LINES")):
        a = src.index(name)
        out[name.strip(" =[{\n")] = re.sub(r"「[^」]*」", " ", src[a:src.index(end, a)])      # 인용은 보기다
    return out


def test_no_list_types_a_line_count_in_korean_numerals():
    """[F33] 「그 열두 줄에 있다」 — 결정 화면은 남은 14. 셈은 정본에서(decisions_count · probe_count) — 셈말로 박으면 하나 늘 때 거짓이 된다."""
    bad = {k: re.findall(NUM + r"\s?줄|종류\(" + NUM + r"\)", b) for k, b in _typed_blocks().items()}
    assert not any(bad.values()), bad
    assert re.search(NUM + r"\s?줄", "둘 다 그 열두 줄에 있다") and re.search(r"종류\(" + NUM + r"\)", "기대 종류(열넷)가 오면")   # 규칙이 살아 있다
    assert re.search(NUM + r"\s?줄", "그 열한 줄에 있다") and re.search(NUM + r"\s?줄", "스물한 줄") and not re.search(NUM + r"\s?줄", "열 줄")
