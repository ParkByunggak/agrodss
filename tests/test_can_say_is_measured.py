# -*- coding: utf-8 -*-
# [둘째 작목 걷기 2026-10-07] 발행자 PC 에는 작목이 둘이다 — 쪽파(재배 달력 있음)와 대파(**없음** · 심은 지 며칠). 그 둘째 상태를 격리로 만들어 물음 여섯을 걸으니
# 답이 **한 글자도 다르지 않은** 175자 하나였고(정직한 사유다 — 달력이 없으면 판정이 없다), 라우팅이 없는 물음에는 그 끝에 이 줄이 붙었다.
#
#     지금 답할 수 있는 것: 수확 시기 · 위험 경보 · 약제와 자재 · 할 일
#
# 그 작목은 **그 넷 다 못 답한다**(봉투 15 전부 판단 불가(지식) · 서는 것 0). 손으로 적은 목록이라 작목이 둘이 되는 날 거짓이 됐다 — 흐르는 숫자의 **목록 판**.
# 쪽파 쪽도 틀려 있었다: 실제로 서는 것은 **다섯**(수확 시기 · 위험 경보 · 자재 인용 · 계획 대 실제 · **배수 경보**)인데 넷만 적혀 있었다.
# 그리고 세면서 **표가 두 벌**인 것이 나왔다 — 화면 표(`chat_pages.DECISION_LABEL`)에는 네 자리만 있어 배수·병해충이 등록부 이름으로 떨어졌고,
# 화면은 「배수 경보(칸 4)」 · 답은 「배수 경보(4단계)」 였다(2026-10-05 에 고친 그 자리가 한 곳뿐이었다 · §7.5 지점).
#
# 고정하는 것 일곱:
#   ① 목록은 **세어서** 나온다 — 봉투에서 서는 것과 이름이 같다(리터럴을 박지 않는다)
#   ② 서는 것이 없으면 **그렇게 말한다** — 없는 넷을 말하지 않는다(거짓 약속 금지)
#   ③ 대조군 — 재료를 빼면 목록이 줄어든다(줄지 않으면 세는 도구가 죽은 것이다)
#   ④ 「답할 수 있다」 는 판단함 · 사실 인용 **둘뿐**(판단 불가는 못 하는 사유다)
#   ⑤ 이름 표는 **하나** — 화면과 답이 같은 표를 쓰고, 저장소에 사본 리터럴이 없다
#   ⑥ 안쪽 말이 이름에 없다(「(칸 4)」 꼴) · 되읽어도 안 바뀐다
#   ⑦ 그 줄이 서는 자리 **셋 다** 세어 말한다(한 분기만 고치면 다음 분기가 거짓을 말한다)
from __future__ import annotations

import json
import re
from datetime import date
from pathlib import Path

import pytest

from frontend import chat_pages, words
from ingest import chat, media
from judge import run as judge_run
from tests.test_screen_speaks_plainly import JARGON

ROOT = Path(chat.__file__).resolve().parent.parent
T = date(2026, 10, 7)
SID = "p001-jjokpa-2026f"
NO_GRID = "p001-daepa-2026f"
NO_ANCHOR = "p001-jjokpa-2026f-noanchor"


@pytest.fixture()
def two_crops(tmp_path, monkeypatch):
    """발행자 PC 의 실제 상태 — 작목 둘, 둘째는 **재배 달력 없음**(저장소 등록부에는 쪽파뿐이라 그 조건을 만든다)."""
    doc = json.loads((ROOT / "data" / "subjects.json").read_text(encoding="utf-8"))
    rows = doc["subjects"] if isinstance(doc, dict) and "subjects" in doc else doc
    second = {k: v for k, v in dict(rows[0]).items() if k != "grid_unit"}
    second.update({"id": NO_GRID, "label": "둘째 작목 · 대파 · 2026 가을", "crop": "대파", "anchor": "2026-10-01"})
    rows.append(second)
    # 대조군 — 달력은 같은데 **심은 날이 없는** 목록. 세는 도구가 살아있으면 이쪽 목록이 짧다(값을 바꿔 봉투를 다시 돌리는 그 꼴)
    bare = {k: v for k, v in dict(rows[0]).items() if k != "anchor"}
    bare.update({"id": NO_ANCHOR, "label": "대조군 · 쪽파 · 심은 날 없음"})
    rows.append(bare)
    p = tmp_path / "subjects.json"
    p.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
    monkeypatch.setenv("AGRODSS_SUBJECTS_PATH", str(p))
    monkeypatch.setenv("AGRODSS_SUBJECTS_LOCAL_PATH", str(tmp_path / "local.json"))
    return tmp_path


def _stands(sid: str, today: date = T) -> list[str]:
    return [e.decision_id for e in judge_run.judgments_for(sid, today=today) if e.kind in chat.STANDS]


def test_the_list_is_counted_from_the_envelopes(two_crops):
    """[①] 서는 봉투를 세어 그 이름을 말한다 — 손으로 적은 목록이 넷이었고 실제는 다섯이었다."""
    ids = _stands(SID)
    assert len(ids) >= 5, ids                                            # 조건부터 — 쪽파는 여럿이 선다(이 수가 1이면 아래 대조가 뜻이 없다)
    said = chat.can_say_line(media.load_subjects()[0], T)
    for did in ids:
        assert words.decision(did) in said, (did, said)
    assert "배수 경보" in said, said                                      # 손 목록이 빠뜨린 그 이름
    # 서지 않는 것은 **말하지 않는다**(판단 불가를 답할 수 있다고 하면 그쪽이 더 나쁘다)
    for e in judge_run.judgments_for(SID, today=T):
        if e.kind not in chat.STANDS:
            assert words.decision(e.decision_id) not in said, (e.decision_id, e.kind, said)


def test_when_nothing_stands_it_says_so(two_crops):
    """[②] 둘째 작목 — 서는 것이 0 이면 그 사실을 말하고 없는 넷을 말하지 않는다."""
    second = next(x for x in media.load_subjects() if x["id"] == NO_GRID)
    assert _stands(NO_GRID) == [], _stands(NO_GRID)                      # 조건 — 달력이 없으면 서는 것이 없다
    said = chat.can_say_line(second, T)
    assert said == words.can_say([]), said
    for name in ("수확 시기", "위험 경보", "약제와 자재", "할 일", "자재 인용", "계획 대 실제"):
        assert name not in said, (name, said)
    assert "재배 달력" in said, said                                      # 무엇이 열면 열리는지는 말한다(막힌 채 침묵하지 않는다)
    # 그리고 답 여섯이 그 줄을 **같이** 낸다 — 물음마다 다른 사유를 지어내지 않는다
    for q in ("이거 값이 얼마예요", "트랙터 어디서 빌려요"):
        assert said in chat.answer(second, q, T), q


def test_removing_the_material_shrinks_the_list(two_crops):
    """[③] 대조군 — 달력은 같고 **심은 날만 없는** 목록은 답할 수 있는 것이 적다(안 줄면 세는 도구가 죽은 것이다).

    [자기 도구 오류 2026-10-07] 첫 판은 사전에서 `anchor` 를 지워 넘겼는데 **아무것도 안 바뀌었다** — 이 함수는 id 만 쓰고 봉투는 등록부에서 다시 읽는다.
    대조군은 **등록부에** 세운다(`two_crops` 픽스처). 넘긴 사전이 조건을 바꾼다고 믿은 것이 틀렸다.
    """
    full_ids, bare_ids = _stands(SID), _stands(NO_ANCHOR)
    assert len(bare_ids) < len(full_ids), (full_ids, bare_ids)
    full = chat.can_say_line(next(x for x in media.load_subjects() if x["id"] == SID), T)
    bare = chat.can_say_line(next(x for x in media.load_subjects() if x["id"] == NO_ANCHOR), T)
    assert bare != full, (full, bare)
    for did in set(full_ids) - set(bare_ids):
        assert words.decision(did) in full and words.decision(did) not in bare, (did, full, bare)


def test_only_a_judgement_or_a_citation_counts_as_an_answer():
    """[④] 「답할 수 있다」 는 둘뿐 — 판단 불가·해당 없음은 **못 하는 사유**다."""
    assert chat.STANDS == ("판단함", "사실 인용"), chat.STANDS
    kinds = {e.kind for e in judge_run.judgments_for(SID, today=T)}
    assert kinds - set(chat.STANDS), "이 농사에 못 하는 봉투가 있어야 이 가름이 뜻을 갖는다"
    assert words.can_say([]) != words.can_say(["수확 시기"])


def test_the_name_table_is_one():
    """[⑤] 화면과 답이 **같은 표**를 쓴다 — 두 벌이었을 때 배수·병해충이 어긋났다."""
    table = chat_pages.DECISION_LABEL
    assert table == {k: words.decision(k) for k in table}, [k for k in table if table[k] != words.decision(k)]
    assert set(words.DECISION_SAID) <= set(table), sorted(set(words.DECISION_SAID) - set(table))
    assert table.get("drainage_alert") == words.decision("drainage_alert")
    # 저장소에 **사본 리터럴**이 없다 — 「수확 시기」 를 키에 매단 사전이 낱말 정본 밖에 또 있으면 다시 갈라진다
    copies = []
    for d in ("frontend", "ingest", "judge", "scripts"):
        for f in sorted((ROOT / d).glob("*.py")):
            if f.name == "words.py":
                continue
            for m in re.finditer(r'\{[^{}\n]*"harvest_timing"\s*:\s*"수확 시기"', f.read_text(encoding="utf-8")):
                copies.append(f"{f.name}: {m.group(0)[:50]}")
    assert copies == [], copies


def test_the_names_are_in_people_words(two_crops):
    """[⑥] 이름에 안쪽 말이 없고(「(칸 4)」 꼴) 되읽어도 안 바뀐다."""
    said = chat.can_say_line(media.load_subjects()[0], T)
    assert words.plain(said) == said, said
    assert "(칸 " not in said, said
    for bad in (*JARGON, "_", "harvest_timing"):
        assert bad not in said, (bad, said)
    for did, name in chat_pages.DECISION_LABEL.items():
        assert "(칸 " not in name, (did, name)
        assert words.plain(name) == name, (did, name)


def test_an_answered_question_gets_no_menu(two_crops):
    """[⑧] **답했으면** 「지금 답할 수 있는 것」 을 붙이지 않는다 — 답을 받은 사람에게 읽힐 말이 아니다.

    [충돌 2026-10-07] 목록을 세기 시작하자 증상 물음의 답(원인 후보가 나온 답)에 그 메뉴가 길게 붙어 2026-09-26 가드(「증상 물음에 계획표를 꺼내지
    않는다」)가 그 이름을 보고 터졌다. 가드가 맞다 — 답한 자리에 메뉴는 군더더기다(손 목록일 때도 이미 그랬다). 못 했을 때만 말한다.
    """
    from ingest import events as ev
    from judge import run as judge_run
    s = media.load_subjects()[0]
    q = "잎 끝이 노랗다 어떻게 해요"
    said = chat.answer(s, q, T)
    # 조건을 **답과 같은 입력**으로 세운다 — 물으신 말을 관찰 초안으로 넘기는 그 길(said 를 비우면 다른 봉투가 나와 판정이 뒤집힌다 · 조건 오염)
    e = next((x for x in judge_run.judgments_for(SID, today=T, said=[ev.said_observation(SID, q, T.isoformat())])
              if x.decision_id == "symptom_triage"), None)
    assert e is not None
    if e.kind in chat.STANDS:                                            # 지금 격자로는 답한다 — 그러면 메뉴가 없어야 한다
        assert "답할 수 있는" not in said, said
        assert "계획 대 실제" not in said, said                            # 2026-09-26 가드와 같은 자리(그 이름이 메뉴로도 안 들어온다)
    else:                                                                # 지식이 비면 메뉴가 쓸모 있다(막힌 채 침묵하지 않는다)
        assert chat.can_say_line(s, T) in said, said


def test_all_three_places_count_instead_of_typing(two_crops):
    """[⑦] 그 줄이 서는 자리 셋 다 — 증상 물음(재료 없음) · 라우팅 없음 · 봉투 없음. 한 분기만 고치면 다음 분기가 거짓을 말한다."""
    second = next(x for x in media.load_subjects() if x["id"] == NO_GRID)
    want = words.can_say([])
    seen = 0
    for q in ("잎이 노랗다 어떻게 해요", "이거 값이 얼마예요", "트랙터 어디서 빌려요"):
        said = chat.answer(second, q, T)
        if "답할 수 있" in said:
            assert want in said, (q, said)
            seen += 1
    assert seen >= 2, seen
    # 소스 쪽 판정은 **문자열 상수만** 본다 — 주석에 적힌 그 말(이 고침의 기록)이 걸리면 검사가 헛돈다(§7.1 4번 · 같은 함정을 이 트랙에서 여섯 번 봤다)
    import ast
    fn = next(n for n in ast.walk(ast.parse((ROOT / "ingest" / "chat.py").read_text(encoding="utf-8")))
              if isinstance(n, ast.FunctionDef) and n.name == "answer_with_asks")
    said_in_source = [s.value for s in ast.walk(fn) if isinstance(s, ast.Constant) and isinstance(s.value, str) and "답할 수 있는" in s.value]
    assert said_in_source == [], f"분기가 목록을 다시 적고 있다 — 문장은 4층 정본 하나: {said_in_source}"
    names = [n.id for n in ast.walk(fn) if isinstance(n, ast.Name)]
    assert names.count("can") >= 3, names.count("can")                  # 세 자리가 **그 값**을 쓴다(한 분기만 고치면 다음 분기가 거짓을 말한다)
    assert any(isinstance(c, ast.Call) and getattr(c.func, "id", "") == "can_say_line" for c in ast.walk(fn))
