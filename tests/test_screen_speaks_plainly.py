# -*- coding: utf-8 -*-
# [§7.5 처방 직후 전수 2026-09-21] 앞 회차에 발행자 지적을 **채팅 카드 한 곳**에서만 고쳤다. 화면 전체를 재니 이랬다.
#
#   /judge   76    /c/…  34    /diary  7    /me  9    /improve 12    /changes 9    /new 5     = 152
#
# 메뉴·탭 이름이 **모든 페이지**에 같은 말을 싣고 있었던 것이 큰 몫이었다(재배 단위 · 불이행 · 개선 요구 · 대장).
# 처방은 앞 회차와 같은 형태다 — 안쪽 이름(봉투 8종 · 등급 3분류)은 그대로 두고 4층에서만 옮긴다(`frontend/words.py`).
#
# **급을 가른다**(§7.5 같은 형태 ≠ 같은 급).
#
#   농가 화면   /c/ · /diary/ · /me      **0 이어야 한다** — 농가가 밭일을 적고 판단을 읽는 자리
#   점검 화면   /judge · /improve · /changes   안쪽 말이 남아 있다 — U-26 으로 등재(회수 대기)
#
# 점검 화면까지 한 묶음에 넣으면 판정 문장(3층)을 손대야 하고, 그건 다른 계약이다. 섞으면 둘 다 흐려진다.
from __future__ import annotations

import http.client
import re
import threading
from urllib.parse import quote

import pytest

from frontend import chat_pages, config, serve, words
from ingest import chat, media
from judge import envelope as env

# 농가가 모르는 **안쪽 말**. 작업 이름(관수 · 방제)은 농가의 말이므로 여기 없다.
JARGON = ("원장", "초안", "서술문", "봉투", "격자", "재배 단위", "판단 불가", "해당 없음", "예측 불가",
          "답하지 않음", "사실 인용", "선택지+대가", "상한 제약", "대장", "래칫", "정본",
          "불이행", "개선 요구", "작기 종료", "스키마", "레코드", "분류", "기준점", "미확인")
# [U-26 회수 2026-09-26] /judge 를 더한다 — 발행자가 *"확인하실 곳은 /judge 의 계획 대 실제"* 라고 스스로 그 화면으로
# 갔다. 들여다보는 화면이라고 미뤄 둔 것이 틀렸다: 농가가 답을 찾으러 가는 곳이면 농가 화면이다.
FARMER_PAGES = ("/c/{sid}", "/diary/{sid}", "/me", "/judge")
TODAY = "2026-09-19"      # 화면의 오늘을 고정 — 실제 날짜로 걸으면 창 밖이 되어 문장이 달라진다(시점 축)


@pytest.fixture
def srv(monkeypatch):
    monkeypatch.setattr(config, "PORT", 0)
    monkeypatch.setenv(config.TODAY_ENV, TODAY)
    s = serve.make_server()
    threading.Thread(target=s.serve_forever, daemon=True).start()
    yield s.server_address[1]
    s.shutdown()
    s.server_close()


def _visible(html: str) -> str:
    """사람이 **보는** 글자만 — 태그와 속성(`title=` 포함)을 걷는다. 정확한 말은 title 에 일부러 남겨 두었다."""
    html = re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", html, flags=re.S)
    return re.sub(r"\s+", " ", re.sub(r"<[^>]*>", " ", html))


def _get(port: int, path: str) -> tuple[int, str]:
    c = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
    c.request("GET", path)
    r = c.getresponse()
    return r.status, r.read().decode("utf-8", "replace")


@pytest.mark.parametrize("tmpl", FARMER_PAGES)
def test_a_farmer_page_says_nothing_only_a_developer_would_know(srv, tmpl):
    """**화면을 실제로 걸어서** 센다 — 소스에서 세면 주석·독스트링이 걸리고(§7.1 4번), 함수만 보면 배선이 빠진다."""
    sid = media.load_subjects()[0]["id"]
    status, body = _get(srv, tmpl.format(sid=quote(sid)))
    assert status == 200, tmpl
    seen = _visible(body)
    found = sorted({w for w in JARGON if w in seen})
    assert found == [], f"{tmpl}: 농가 화면이 안쪽 말을 한다 — {found}"


def test_the_words_are_kept_where_they_belong(srv):
    """정확함을 **버리지 않는다** — 종류와 사유는 `title` 에 그대로 있다(걷어 낸 자리에 남아 있어야 한다)."""
    sid = media.load_subjects()[0]["id"]
    _, body = _get(srv, f"/c/{quote(sid)}")
    assert 'title="해당 없음' in body or 'title="판단' in body, "정확한 종류가 어디에도 안 남았다"


def test_every_envelope_kind_has_a_word_a_farmer_uses():
    """봉투 종류가 늘면 사람 말도 함께 는다 — 한쪽만 늘면 화면이 안쪽 이름을 낸다(대리값 금지와 같은 축)."""
    assert set(words.KIND_SAID) == set(env.KINDS)
    for k, said in words.KIND_SAID.items():
        assert k not in said, f"{k}: 사람 말이 안쪽 이름을 그대로 담고 있다 — {said}"
    assert set(words.GRADE_SAID) == set(env.GRADES)


def test_the_judgement_card_leads_with_the_plain_word_not_the_kind():
    """카드 첫 글자가 `해당 없음` 이던 자리 — 배선 래칫(호출형만 본다 · 인자 표현식은 고정하지 않는다)."""
    src = (chat_pages.__file__ and open(chat_pages.__file__, encoding="utf-8").read())
    card = src[src.index("def _env_card"):src.index("def thread_panel")]
    assert "words.said(" in card, "카드가 종류를 사람 말로 옮기지 않는다"
    assert "title=" in card, "정확한 종류를 남길 자리가 없다"


def test_the_plain_layer_never_touches_what_the_farmer_wrote():
    """**농가가 쓴 글에는 대지 않는다** — 자기가 쓴 말이 바뀌어 돌아오면 그게 더 나쁘다.

    [주입이 드러낸 허점 2026-09-21] 첫 판은 `diary_main` **한 함수만** 봤고, 주입은 패널의 일지 줄에 댔다 —
    통과했다. 가드가 좁으면 같은 결함이 옆 함수로 옮겨 간다(§7.5 지점 축이 검사 안에서 일어난 꼴).
    계약은 자리(함수)가 아니라 **인자**다: 낱말 표는 농가가 쓴 필드에 닿으면 안 된다.
    """
    mine = "격자 옆 기준점 근처에 원장을 두었다"          # 농가가 이런 말을 쓸 수도 있다
    assert words.plain(mine) != mine                     # (시스템 문장에 쓰면 바뀐다 — 그래서 쓰는 자리를 가른다)
    src = open(chat_pages.__file__, encoding="utf-8").read()
    calls = re.findall(r"words\.plain\(([^)]*)\)", src)
    bad = [a for a in calls if '["text"]' in a or '.get("text"' in a or '["note"]' in a or '["reason"]' in a]
    assert bad == [], f"낱말 표가 농가가 쓴 글에 닿는다: {bad}"


def test_the_kind_word_survives_a_round_trip_through_the_summary():
    """요약 줄은 사람 말로 나오되 **원래 종류로 되돌릴 수 있어야** 한다 — 기록과 화면이 갈리면 안 된다."""
    e = env.Envelope("해당 없음", "replant", "s", "now", result={"why": "보식 창(1~14일) 밖", "summary": "창 밖"})
    said = chat.summarize_envelope(e)
    assert words.said("해당 없음") in said and "해당 없음" not in said
    assert chat.summarize_envelope(e, plain=False).startswith("[해당 없음]")


def test_judge_names_the_data_it_used_in_plain_words_and_keeps_the_ids(srv):
    """[U-26] 쓴 자료 표가 `anchor` · `soil_chem` 같은 안쪽 id 를 냈다. 사람 말로 내되 id 는 title 에 남긴다."""
    status, body = _get(srv, "/judge")
    assert status == 200
    seen = _visible(body)
    assert words.axis("anchor") in seen, "쓴 자료가 사람 말로 안 나온다"
    assert 'title="anchor"' in body, "정확한 id 가 어디에도 안 남았다"
    # [주입 D 가 드러낸 겹침 2026-09-26 · §7.1 4번] 표에서 'anchor' 가 빠지면 `words.axis` 는 id 를 그대로 돌려주고, 그 id 가
    # 화면에도 있어 위 검사가 통과했다 — 기대 문자열이 원 결함 문면과 같았다. 그래서 **id 자체가 안 보이는가**를 따로 본다.
    for raw in ("anchor", "soil_chem", "pest_regional"):
        assert raw not in seen, f"안쪽 id '{raw}' 가 화면에 그대로 나온다"


def test_every_axis_the_judgement_can_use_has_a_plain_word():
    """자료(축) 정본은 `grid.schema.AXES` 다 — 축이 늘면 사람 말도 함께 는다(봉투 종류 검사와 같은 형태)."""
    from grid import schema as grid_schema
    missing = sorted(a for a in grid_schema.AXES if a not in words.AXIS_SAID)
    assert missing == [], f"사람 말이 없는 자료: {missing}"
    for a, said in words.AXIS_SAID.items():
        assert a not in said and said.strip(), f"{a}: 사람 말이 id 를 담고 있다 — {said}"


def test_judge_badge_is_the_plain_kind_with_the_exact_kind_kept(srv):
    _, body = _get(srv, "/judge")
    assert words.said("판단함") in _visible(body)
    assert 'title="판단함"' in body or 'title="해당 없음"' in body
