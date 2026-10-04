# -*- coding: utf-8 -*-
# [내부 값 전수 2026-10-04 ④] 앞 칸(재배 단위 id · 대상 어휘 · 역할)을 덮은 뒤 **같은 형태를 전수로** 재니 네 번째 갈래가 남아 있었다 —
# **기록 id**(obs_… · vid_…)가 화면의 **제 문장 안**에 있었다. 세 자리다:
#   ① 채팅 카드 「일지에 넣었습니다 본 것 · obs_cad6ffa21a01」 — 발행자가 실사용에서 집어 온 바로 그 꼴(10-04 문장 목록 여섯째 줄에 그 id 가 들어 있다)
#   ② /judge 「읽은 관찰: obs_… · obs_…」 — 사람이 알고 싶은 것은 몇 건을 읽었나다
#   ③ /judge 계획 표 근거 칸 「영상 vid_… (2026-10-03)」 — 판정기가 id 를 **사람 문장에 구워 넣어** 화면이 떼어낼 수 없었다
# 처방은 두 겹 — 판정기는 문장과 id 를 나눠 두고(`evidence_ref`) 화면은 그 id 를 `title` 로 내린다(정확함을 안 버린다 — 앞 칸과 같은 가름).
# 가름의 정본: **사람이 쓴 글 안의 id 는 인용된 기록**이다(/selfcheck 의 발행자 문장에 obs_93e9b4b67856 이 들어 있고 그것은 결함이 아니다) —
# 그래서 래칫은 id 를 금지하지 않고 **사람이 쓴 글 밖에 있는 id** 를 센다(/changes 가 커밋 제목을 걷는 것과 같은 축).
from __future__ import annotations

import re
from datetime import date, datetime, timezone
from urllib.parse import quote

from ingest import chat, events as ev, feedback as fb, media, probes, subjects
from tests.test_media import make_mp4
from tests.test_screen_speaks_plainly import FARMER_PAGES, _get, _visible, srv  # noqa: F401

T = date(2026, 9, 19)           # srv 픽스처가 화면의 오늘을 이 날로 고정한다 — 창 안이라 판정과 카드가 다 선다(시점 축)
NOW = datetime(2026, 9, 19, 9, 0, tzinfo=timezone.utc)
SID = "p001-jjokpa-2026f"
REC_ID_RE = re.compile(r"\b[a-z]{3}_[0-9a-f]{12}\b")       # 기록 id 꼴 — 접두를 목록으로 박지 않는다(새 갈래가 늘어도 그대로 걸린다)
CODE_RE = re.compile(r"<code>.*?</code>", re.S)            # 경로 · 파일 이름은 인용된 기록(실제 저장 경로가 media/<작목>/… 다)


def _said(body: str) -> str:
    """화면이 **제 문장으로** 낸 글 — 태그·속성(title 포함)과 기계 문자열을 걷는다."""
    return _visible(CODE_RE.sub(" ", body))


def _human_texts() -> str:
    """**사람이 쓴 글** 전부 — 농가·발행자가 보낸 말 · 고쳐 달라는 말과 그 답 · 일지에 적힌 글 · 문장 목록.
    여기 들어 있는 id 는 인용이라 걷지 않는다(발행자 문장 안의 obs_… 를 결함으로 읽으면 정직한 인용을 고치게 된다)."""
    out: list[str] = []
    for g in probes.load().get("groups", []):
        out += [str(r.get("text") or "") for r in g.get("rows", [])]
    for s in subjects.load():
        out += [str(m.get("text") or "") for m in chat.list_messages(s["id"]) if m.get("role") != "system"]
    for r in fb.list_records("feedback.request"):
        out += [str(r.get("text") or ""), str(r.get("response") or "")]
    for r in ev.list_records():
        out += [str(r.get(k) or "") for k in ("text", "reason", "task", "note")]
    return " ".join(out)


def _fill() -> None:
    """세 자리가 **실제로 서는** 자료 — 증상 관찰(읽은 관찰) · 창 안 영상(근거 칸) · 들어간 초안(채팅 카드).
    자료가 없으면 표 머리만 보고 칸은 안 보인다(빈 표로 영상 표 머리를 놓쳤던 전례)."""
    m, _ = chat.send(SID, "잎 끝이 노랗다", today=T, now=NOW)
    chat.confirm(m["id"], 0, now=NOW)
    media.register(media.save_upload("c.mp4", make_mp4(datetime(2026, 9, 18, 1, 0, tzinfo=timezone.utc))), SID, note="두둑")


def test_no_screen_shows_a_record_id_in_its_own_sentence(srv):
    _fill()
    human = _human_texts()
    bad = {}
    for tmpl in list(FARMER_PAGES) + ["/changes"]:
        p = tmpl.format(sid=quote(SID))
        st, body = _get(srv, p)
        assert st == 200, p
        hits = sorted({h for h in REC_ID_RE.findall(_said(body)) if h not in human})
        if hits:
            bad[p] = hits
    assert bad == {}, f"화면이 기록 id 를 제 문장에 낸다(사람이 쓴 글 안의 인용이 아니다): {bad}"


def test_the_quoted_id_inside_a_persons_sentence_is_left_alone(srv):
    """발행자가 쓴 문장에 든 id 는 **그대로 보인다** — 인용을 고치면 그 사람이 쓴 글이 아니게 된다."""
    _, body = _get(srv, "/selfcheck")
    seen = _said(body)
    quoted = sorted(set(REC_ID_RE.findall(seen)))
    assert quoted, "발행자 문장의 id 가 화면에서 사라졌다 — 인용을 걷어 내면 안 된다"
    assert all(q in _human_texts() for q in quoted)


def test_the_ids_are_still_there_exactly_in_the_title(srv):
    """정확함을 **버리지 않는다** — 세 자리 모두 id 가 `title` 에 그대로 있다."""
    _fill()
    _, body = _get(srv, f"/c/{quote(SID)}")
    assert re.search(r'class="draft" title="obs_[0-9a-f]{12}"', body), "들어간 카드가 원장 id 를 어디에도 안 남겼다"
    _, body = _get(srv, f"/judge?s={quote(SID)}")
    assert re.search(r'title="obs_[0-9a-f]{12}[^"]*">읽은 관찰 \d+건', body), "읽은 관찰 건수 줄이 id 를 안 남겼다"
    assert re.search(r'title="vid_[0-9a-f]{12}">영상 \(', body), "계획 표 근거 칸이 영상 id 를 안 남겼다"


def test_the_plan_row_keeps_the_reference_in_its_own_field():
    """판정기 층의 짝 — 사람이 읽는 문장과 id 를 **나눠서** 낸다(화면이 떼어낼 수 있어야 title 로 내릴 수 있다)."""
    from judge import plan_vs_actual as PVA
    subj = subjects.by_id(SID)
    vids = [{"id": "vid_zz", "observed_at": "2026-09-18T06:30:00+00:00", "kind": media.KIND_IMAGE}]
    rows = PVA.judge(subj, today=date(2026, 9, 19), videos=vids).result["rows"]
    done = [r for r in rows if r["kind"] == "plan.capture" and r["status"] == "이행"]
    assert done and done[0]["evidence_ref"] == "vid_zz"
    assert done[0]["evidence"].startswith("사진 (") and "vid_zz" not in done[0]["evidence"]
    assert all(not REC_ID_RE.search(r["evidence"] or "") for r in rows)       # 다른 상태의 근거 줄에도 id 가 없다


def test_the_consumer_links_on_the_field_not_on_the_sentence():
    """처방 직후 전수에서 나온 **소비자**(§7.5) — 반입 답의 「촬영 칸으로 이어졌다」 줄이 영상 id 를 **근거 문장 안에서** 찾고 있었다.
    문장에 기대는 이음은 문장이 바뀌면 조용히 0건이 된다(아무 검사도 안 깨지고 말만 사라진다). 이음은 제 칸으로만 간다."""
    import inspect
    body = inspect.getsource(chat._capture_landed)
    assert 'r.get("evidence_ref")' in body
    assert 'r.get("evidence")' not in body, "이음이 사람 말 문장으로 되돌아갔다 — 문장이 바뀌면 끊긴다"
    from tests.test_chat_upload_voice_lan import make_jpeg_with_exif
    key = media.save_upload("IMG_20260918_101010.jpg", make_jpeg_with_exif(None))
    rec = media.register(key, SID, now=NOW)
    _, r = chat.send(SID, "", media_refs=[rec], today=date(2026, 9, 19), now=NOW)
    assert "한 것으로 잡혔습니다" in r["text"] and "단계" in r["text"], r["text"]      # 배선이 실제로 돈다(함수만 보면 호출부가 빠진다)
