# -*- coding: utf-8 -*-
# [손 노릇 2026-10-07] 결정 화면은 발행자의 **다음 할 일**이고(D-2 한 줄에 다섯 항목이 매달려 있다) 지금까지 그 화면은 줄마다 폼이 따로였다.
# 측정 2026-10-05: 답 없는 줄 14 · 저장 폼도 **14** — 열넷을 답하려면 열네 번 누르고, 누를 때마다 30KB 쪽이 위에서 다시 그려지고 돌아갈 자리(앵커)가 없어
# 마지막 카드는 28,753번째 글자였다. **판단은 발행자 몫 그대로**이고 손 노릇만 줄인다(세션이 답을 고르는 것이 아니다 — 그러면 채점자와 응시자가 같아진다).
#
# 처방: 칸들을 `form=` 로 **맨 아래 저장 하나**에 붙인다(폼을 겹쳐 넣을 수 없어서 — 답한 줄의 「지우기」 폼이 그 안에 들어가면 안 된다).
#   측정 2026-10-07(그 처방 뒤): 저장 폼 **1** · `required` **0** · 미리 고른 것 **0** · 줄마다 칸 14 · 쪽 13,848 → 12,434 바이트
#
# 이 검사가 고정하는 것 여섯:
#   ① 저장 폼은 하나 · 칸은 남은 줄마다(결정된 줄에는 칸이 없다 — 양방향)
#   ② **미리 고른 것 0 · `required` 0** — 열넷 중 셋만 답해도 저장된다(그 전제가 이 처방이다)
#   ③ 한 번에 여러 줄이 저장된다(쓰기 길은 `answer_all` 하나 · 옛 한 줄 꼴도 같은 길로)
#   ④ 한 줄이 틀리면 **아무것도 안 쓴다**(검증이 먼저 · 부분 저장은 발행자가 무엇이 들어갔는지 모른다)
#   ⑤ 고르지 않은 줄은 저장되지 않는다(빈 저장은 거부 · 안 고른 것은 답이 아니다)
#   ⑥ 틀려서 돌아올 때 **고른 것과 친 글이 남는다**(틀린 줄을 다시 치게 하지 않는다)
from __future__ import annotations

import http.client
import re
from urllib.parse import urlencode

import pytest

from frontend import chat_pages
from ingest import decisions as dc
from schema import labels
from tests.test_brand_home import srv  # noqa: F401 — 화면을 실제로 띄운다(배선까지 본다)


def _post(port, data: dict[str, str]) -> tuple[int, str]:
    c = http.client.HTTPConnection("127.0.0.1", port, timeout=10)
    c.request("POST", "/me/decisions", body=urlencode(data), headers={"Content-Type": "application/x-www-form-urlencoded"})
    r = c.getresponse()
    return r.status, r.read().decode("utf-8")


def _html() -> str:
    return chat_pages.decisions_main()


def test_one_save_form_and_one_field_group_per_open_row():
    html = _html()
    sm = dc.summary(dc.load())
    assert html.count(f'id="{chat_pages.BATCH_FORM}"') == 1 and html.count('action="/me/decisions"') == 1
    assert len(re.findall(r'name="v:[^"]+"\s+value="맞다"', html)) == sm["open"]
    assert len(re.findall(r'name="n:[^"]+"', html)) == sm["open"]
    assert html.count(f'form="{chat_pages.BATCH_FORM}"') == sm["open"] * (len(dc.VERDICTS) + 1)      # 라디오 셋 + 메모 칸이 다 그 폼에 붙는다
    for i in dc.DECIDED:                                                                            # 반대편 — 결정된 줄에는 칸이 없다
        assert f'name="v:{i}"' not in html and f'name="n:{i}"' not in html, i
    assert labels.DECISIONS_SAVE in html


def test_nothing_is_pre_picked_and_nothing_is_required():
    """[②] 미리 고르면 채점자와 응시자가 같아진다 · `required` 가 있으면 열넷을 **다** 답해야 저장된다(그게 옛 상태였다)."""
    html = _html()
    assert "checked" not in html and "required" not in html, html[:200]


def test_several_rows_are_saved_in_one_press():
    r = dc.answer_all([("D-2", "맞다", ""), ("D-3", "다르다", "예약은 봄부터"), ("D-4", "모르겠다", "")])
    assert r["written"] == ["D-2", "D-3", "D-4"] and r["counts"] == {"맞다": 1, "다르다": 1, "모르겠다": 1}
    sm = dc.summary(dc.load())
    assert sm["answered"] == 3 and sm["open"] == len(dc.IDS) - len(dc.DECIDED) - 3
    text = dc.to_session_text(dc.load())
    assert "D-2 맞다" in text and "D-3 다르다 — 예약은 봄부터" in text and "D-4 모르겠다" in text
    assert dc.answer_all([("D-2", "맞다", "")])["counts"]["맞다"] == 1                               # 같은 답을 다시 보내도 멱등(한 줄만 센다)


@pytest.mark.parametrize("rows,why", [
    ([("D-7", "다르다", "")], "빈 「다르다」"),
    ([("D-7", "맞다", ""), ("없는-id", "맞다", "")], "없는 줄"),
    ([("D-7", "맞다", ""), ("D-7", "모르겠다", "")], "같은 줄 두 번"),
    ([("D-7", "틀렸다", "")], "없는 답"),
    ([], "고른 줄 없음"),
])
def test_a_bad_row_writes_nothing_at_all(rows, why):
    """[④] 검증이 먼저다 — 좋은 줄이 섞여 있어도 쓰지 않는다. 부분 저장은 발행자가 무엇이 들어갔는지 모르게 만든다."""
    before = dc.load()
    with pytest.raises(ValueError):
        dc.answer_all(rows)
    assert dc.load() == before, why


def test_rows_left_blank_are_not_answers():
    """[⑤] 안 고른 줄은 답이 아니다 — 빈 값은 건너뛰고, 전부 비면 거부한다(화면이 `required` 없이 보내므로 이것이 그 짝이다)."""
    r = dc.answer_all([("D-2", "맞다", ""), ("D-3", "", ""), ("D-4", "", "메모만 적었다")])
    assert r["written"] == ["D-2"]
    assert "D-3" not in dc.load() and "D-4" not in dc.load()
    with pytest.raises(ValueError):
        dc.answer_all([("D-3", "", ""), ("D-4", "", "")])


def test_the_screen_really_sends_several_rows_in_one_press(srv):  # noqa: F811
    """[③ 배선] 화면이 `v:<id>` 로 보내도 **서버가 그 꼴을 안 보면** 아무 일도 안 생긴다 — 주입 D 가 그래서 통과했다(단위 검사는 쓰기 함수만 봤다).
    그래서 실제로 띄워 POST 한다: 두 줄을 한 번에 보내고 원장에 둘이 들어갔는지 본다."""
    status, body = _post(srv, {"v:D-2": "맞다", "n:D-2": "", "v:D-4": "모르겠다", "n:D-4": "", "v:D-7": ""})
    assert status == 200 and "적었다 — 2줄" in body, body[body.find("적었다") - 80:][:200]
    answers = dc.load()
    assert answers["D-2"]["verdict"] == "맞다" and answers["D-4"]["verdict"] == "모르겠다" and "D-7" not in answers
    status, body = _post(srv, {"v:D-3": "다르다", "n:D-3": ""})                    # 틀린 줄이면 아무것도 안 쓴다(그 줄만 되돌려 준다)
    err = re.search(r"저장하지 않았다[^<]*", body)
    assert status == 400 and err and "무엇" in err.group(0), err                   # 오류 **그 줄**에서 본다(쪽 어디에나 있는 「다르다면 → 무엇」 에 걸리지 않게)
    assert "D-3" not in dc.load()


def test_what_was_typed_comes_back_when_the_save_is_refused():
    """[⑥] 틀린 저장에서 돌아올 때 고른 것과 친 글이 그 줄에 남는다 — 쓴 글은 **쓴 그대로**(낱말 표를 대지 않는다)."""
    said = "격자가 아니라 원장을 본다"
    html = chat_pages.decisions_main(error="저장하지 않았다 — 무엇", form={"v:D-3": "다르다", "n:D-3": said})
    assert 'name="v:D-3" value="다르다" checked' in html
    assert said in html, html[html.index("D-3"):][:400]                                             # 낱말 표를 거치면 「재배 달력」 으로 바뀐다
    assert 'name="v:D-2" value="다르다" checked' not in html                                         # 다른 줄에는 안 남는다
