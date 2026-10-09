# -*- coding: utf-8 -*-
# FILE: scripts/verify_claims.py
# ROLE: [발행자 2026-10-05 "여기서 완료된 것을 확인하자"] 보고의 「세션이 한 것」 줄을 **하나씩 다시 걷는다**.
#   왜 — 관문이 초록인 것은 *"모순 미발견"* 이지 검증이 아니다(CLAUDE.md "0 failed ≠ 검증됨"). 그리고 그 줄은 회차마다 길어지는 **누적 문장**이라
#   한 번 적힌 주장이 그대로 실려 다닌다(U-19 계열: 낡은 주장은 없는 주장보다 나쁘다). 그래서 검사가 아니라 **실제 경로**로 다시 잰다.
#
#   쓰는 법   python -m scripts.verify_claims            (틀린 주장이 있으면 rc=1 · 줄마다 본 것을 적는다)
#            python -m scripts.verify_claims --no-http  (화면 걷기 없이 — 빠른 갈래만)
#
#   규율 셋:
#     읽기 전용   운영 data 에 아무것도 쓰지 않는다 — 모든 `AGRODSS_*` 경로를 tmp 로 돌린다(conftest·walk.sh 와 같은 목록 · 검사가 셋을 대조한다)
#     조건        주장마다 **그 주장이 성립하는 조건**을 먼저 세운다. 첫 판에 셋이 「틀림」 으로 나왔는데 셋 다 조건·도구가 틀렸다(아래 주석)
#     정직        못 세운 조건은 「못 잼」 으로 적는다 — 틀림으로도 확인으로도 적지 않는다
#
#   [2026-10-05 자기 도구 오류 셋 — 기록해 둔다] 첫 판 49줄 중 3줄이 「틀림」 이었고 **셋 다 측정 쪽**이었다:
#     ① 「무농약」 이 카드로 안 섰다 → 그 순간 **묻는 것이 배수**였다(인증 물음이 서야 그 답이 묶인다 · 배수 물음이 상한 3회에 닿은 뒤 인증이 선다 — 실측)
#     ② 왼쪽 메뉴 이름이 없다 → **페이지 제목**(`labels.ME_TITLE` = 사용자 정보)을 메뉴 이름으로 썼다(메뉴는 `labels.label("/me")` = 밭 정보 · 설정)
#     ③ 화면이 id 를 낸다 → **속성(href · value)까지 글로 셌다**. 글(태그를 걷어 낸 텍스트)만 보면 아홉 화면 전부 없다
#   세 번 다 *"한쪽으로 쏠린 결과는 도구 버그의 표지"* 가 맞았다.
from __future__ import annotations

import http.client
import json
import os
import pathlib
import re
import shutil
import sys
import tempfile
import threading
from datetime import date, datetime, timezone
from typing import Any

ROOT = pathlib.Path(__file__).resolve().parent.parent
SID = "p001-jjokpa-2026f"
T = date(2026, 10, 5)
NOW = datetime(2026, 10, 5, 9, 0, tzinfo=timezone.utc)
OK, NO, NA = "확인", "틀림", "못 잼"


def isolate() -> pathlib.Path:
    """운영 data 를 건드리지 않게 — conftest·walk.sh 와 **같은 목록**을 tmp 로(하나 빠지면 이 스크립트가 운영 원장에 쓴다)."""
    w = pathlib.Path(tempfile.mkdtemp(prefix="verify_claims_"))
    for name in ("chat", "events", "feedback", "media", "soil", "psis", "names"):
        (w / name).mkdir()
    shutil.copy(ROOT / "data" / "parcels_seed.json", w / "parcels.json")
    shutil.copy(ROOT / "data" / "subjects.json", w / "subjects.json")
    os.environ.update({
        "TZ": "Asia/Seoul", "AGRODSS_TODAY": T.isoformat(), "AGRODSS_AUTO_PULL_SEC": "0",
        "AGRODSS_MEDIA_DIR": str(w / "media"), "AGRODSS_EVENTS_DIR": str(w / "events"),
        "AGRODSS_FEEDBACK_DIR": str(w / "feedback"), "AGRODSS_CHAT_DIR": str(w / "chat"),
        "AGRODSS_SUBJECTS_PATH": str(w / "subjects.json"), "AGRODSS_SUBJECTS_LOCAL_PATH": str(w / "subjects_local.json"),
        "AGRODSS_SUBJECTS_BACKUP_PATH": str(w / "subjects_backup.json"),
        "AGRODSS_PARCELS_PATH": str(w / "parcels.json"), "AGRODSS_PARCELS_LOCAL_PATH": str(w / "parcels_local.json"),
        "AGRODSS_PARCELS_LEGACY_PATH": str(w / "none.json"), "AGRODSS_PROFILE_PATH": str(w / "profile.json"),
        "AGRODSS_SOIL_DIR": str(w / "soil"), "AGRODSS_PSIS_DIR": str(w / "psis"),
        "AGRODSS_NAMES_DIR": str(w / "names"), "AGRODSS_NAMES_CSV": str(w / "crop_names.csv"),
        "AGRODSS_NAMES_LOCAL_CSV": str(w / "crop_names_local.csv"), "AGRODSS_NAMES_BACKUP_CSV": str(w / "crop_names_backup.csv"),
        "AGRODSS_ORGANIC_PATH": str(w / "organic_materials_public.json"),
        "AGRODSS_OUTLOOK_PATH": str(w / "climate_outlook.json"), "AGRODSS_OUTLOOK_LOCAL_PATH": str(w / "climate_outlook_local.json"),
        "AGRODSS_ASKS_PATH": str(w / "chat" / "asks.json"), "AGRODSS_DECISIONS_LOCAL_PATH": str(w / "decisions_local.json"),
        "AGRODSS_PROBES_LOCAL_PATH": str(w / "utterance_probes_local.json"),      # [손 노릇 2026-10-07] 기대 덮개 — 보고 확인이 운영 덮개에 쓰지 않게(검사가 이 짝을 요구한다)
    })
    return w


class Sheet:
    """주장 한 줄 = (판정, 주장, 본 것). 판정은 셋뿐이다 — 확인 · 틀림 · 못 잼."""

    def __init__(self) -> None:
        self.rows: list[tuple[str, str, str]] = []

    def say(self, verdict: str, claim: str, seen: Any) -> None:
        assert verdict in (OK, NO, NA), verdict
        self.rows.append((verdict, claim, str(seen)[:160].replace("\n", " ⏎ ")))

    def check(self, ok: bool, claim: str, seen: Any) -> None:
        self.say(OK if ok else NO, claim, seen)

    @property
    def wrong(self) -> list[tuple[str, str, str]]:
        return [r for r in self.rows if r[0] == NO]


def check_classification(s: Sheet) -> None:
    """어미·어휘 주장들 — 분류기는 순수 함수라 원장을 안 건드린다."""
    from ingest import chat, subjects
    sub = subjects.by_id(SID)

    def first(text: str) -> str | None:
        drafts = chat.classify(text, T, subject=sub)
        return drafts[0]["kind"] if drafts else None

    for q in ("물 줘야 하나", "병충해 뭐 봐야 하나", "서리 오나", "관수가 필요한가", "흙이 마른가", "잎이 노란가"):
        s.check(first(q) == "question", f"물음으로 간다: 「{q}」", first(q))
    for d in ("오늘 할 일 다 했다", "무슨 일이 있었다"):
        s.check(first(d) != "question", f"물음이 아니다(일지로): 「{d}」", first(d))
    for done in ("물 한 번 줬네", "약 조금 쳤다", "풀 뽑음", "물 줌"):
        s.check(first(done) == "event", f"한 일로 간다: 「{done}」", first(done))
    for plan in ("내일 물 줄 것", "비료 줄게"):
        s.check(first(plan) == "plan.farmer", f"할 일로 간다: 「{plan}」", first(plan))
    for guess in ("비가 오겠다", "힘들겠다", "물이 부족할 것 같다", "비가 오려고 한다", "올해는 수확이 적겠다", "비료가 모자라겠다"):
        s.check(first(guess) not in ("plan.farmer", "event"), f"짐작은 할 일·한 일이 아니다: 「{guess}」", first(guess))
    for protest in ("왜 자꾸 같은 걸 묻지", "답이 이상한데"):
        s.check(first(protest) == "feedback.request", f"항의는 고쳐 달라는 말: 「{protest}」", first(protest))
    task = next((d.get("task") for d in chat.classify("약 쳐야겠다", T, subject=sub) if d["kind"] == "plan.farmer"), None)
    s.check(task == "방제", "할 일에 무슨 일인지가 붙는다: 「약 쳐야겠다」 → 방제", task)
    seed = chat.classify("종구 캘 것입니다", T, subject=sub)
    s.check(all(d["kind"] != "parcel.field" for d in seed) and any(d["kind"] == "plan.farmer" for d in seed),
            "「종구 캘 것입니다」 가 밭 용도를 바꾸지 않는다", [d["kind"] for d in seed])
    s.check(first("종구용이다") == "parcel.field", "용도를 말하는 말은 밭 정보로: 「종구용이다」", first("종구용이다"))
    s.check(all(d.get("anchor") is None for d in chat.classify("아직 안 심었어요", T, subject=sub)),
            "「아직 안 심었어요」 가 심은 날을 세우지 않는다", [d["kind"] for d in chat.classify("아직 안 심었어요", T, subject=sub)])


def check_people_words(s: Sheet) -> None:
    """사람이 쓴 글 · 붙일 묶음 · 낱말 표 주장들."""
    from frontend import chat_pages, render, words
    from ingest import decisions as dc
    from schema import records as sch
    long_line = "고랑 물 빠짐이 잘 되고 있고, 잎 끝 황화 현상은 더 진행이 되지 않는다. 다만 아래쪽 두 줄은 아직 물이 고인다"
    s.check(sch.quote(long_line, 30).endswith(sch.QUOTE_TAIL) and sch.quote("짧다", 30) == "짧다",
            "자른 인용에만 「…」 가 붙는다", sch.quote(long_line, 30))
    note = "격자가 아니라 원장을 본다 · 신뢰 등급 추정 · 기준점 칸 3"
    dc.answer("D-2", "다르다", note)
    page = chat_pages.decisions_main()
    s.check(note in page and "재배 달력" in page, "결정 메모가 쓴 그대로 돌아온다(시스템 문장만 쉬운 말)", note in page)
    s.check(render.PASTE_STYLE in page and "user-select:all" in render.PASTE_STYLE, "붙일 묶음은 한 번 눌러 전체가 잡힌다", render.PASTE_STYLE)
    s.check(words.plain("추론 초안") == "검토 전 추론" and words.plain("미확인 초안") == "아직 안 넣은 것",
            "「추론 적을 것」 · 「아직 모름 적을 것」 이 바로잡혔다", (words.plain("추론 초안"), words.plain("미확인 초안")))


def check_consumers(s: Sheet) -> None:
    """「넣으면 어느 판단이 읽습니다」 와 보이는 이름."""
    from frontend import words
    from ingest import parcels
    s.check(len(parcels.FIELD_CONSUMERS["use"]) == 5 and len(parcels.FIELD_CONSUMERS["drainage"]) == 2,
            "용도를 읽는 판단 다섯 · 배수 둘", (parcels.FIELD_CONSUMERS["use"], parcels.FIELD_CONSUMERS["drainage"]))
    s.check(words.plain(words.decision("drainage_alert")) == words.decision("drainage_alert") and "칸" not in words.decision("pest_alert"),
            "보이는 결정 이름에 안쪽 말이 없다", (words.decision("drainage_alert"), words.decision("pest_alert")))
    said = words.opened("use", "종구 생산")
    s.check(said.startswith("이것으로 수확 시기 · 위험 경보"), "넣은 직후 줄이 큰 판단부터 말한다", said[:60])


def check_alerts(s: Sheet) -> None:
    """10/07 경보 주장 — 날짜와 **등급**까지."""
    from judge import run as judge_run

    def alerts_on(day: str) -> list[tuple[str, str]]:
        out: list[tuple[str, str]] = []
        for _sub, envs, _info in judge_run.all_judgments(date.fromisoformat(day)):
            for e in envs:
                ed = e.to_dict()
                if ed["decision_id"] == "risk_alert":
                    out = [(str(a.get("level")), str(a.get("risk"))) for a in (ed.get("result") or {}).get("alerts") or []]
        return out
    a5, a7, a14 = alerts_on("2026-10-05"), alerts_on("2026-10-07"), alerts_on("2026-10-14")
    leaf = lambda rows: [lv for lv, risk in rows if "수확" in risk or "서리" in risk]      # noqa: E731
    s.check(len(a7) == len(a5) + 2, "10/07 부터 잎 기준 경보 둘이 더 선다", f"10/05 {len(a5)} · 10/07 {len(a7)}")
    s.check(leaf(a7) == ["예고", "예고"] and leaf(a14) == ["주의", "주의"],
            "10/07~10/13 은 「예고」 · 10/14 부터 「주의」", f"10/07 {leaf(a7)} · 10/14 {leaf(a14)}")
    # [앞날 걷기 2026-10-07] 달력이 끝난 뒤 — 「놓침 … 사유를 묻는다」 와 「수확 지연」 이 날마다 나가는 자리. 멎게 하는 길을 **답이** 말하는가
    from datetime import timedelta
    from frontend import words
    from grid import schema as grid_schema
    from ingest import chat as _chat, media
    sub = next(x for x in media.load_subjects() if x["id"] == SID)
    unit, _miss = grid_schema.load_unit(sub)
    last = int(grid_schema.last_day(unit or {}) or 0)
    anchor = date.fromisoformat(sub["anchor"])
    said_after = _chat.answer(sub, "오늘 뭐 해야 하나", anchor + timedelta(days=last + 17))
    said_last = _chat.answer(sub, "오늘 뭐 해야 하나", anchor + timedelta(days=last))
    want = words.season_over(last + 17, last, _chat.END_SAY)
    s.check(want in said_after and "재배 달력은 심은 날부터" not in said_last,
            "달력이 끝난 뒤 답이 마치는 길을 말한다(마지막 날에는 말하지 않는다)",
            f"달력 끝 {last}일 · +17일 {'말함' if want in said_after else '없음'} · 마지막 날 {'조용함' if '재배 달력은' not in said_last else '말함'}")
    closed = dict(sub, status="종료", ended_at=(anchor + timedelta(days=last + 17)).isoformat())
    s.check(want not in _chat.answer(closed, "오늘 뭐 해야 하나", anchor + timedelta(days=last + 17)),
            "닫은 뒤에는 그 말을 다시 하지 않는다", f"상태 {closed['status']} · 마친 날 {closed['ended_at']}")
    # [앞날 걷기 2026-10-09] 「약 뭐 쳐요」 가 「계열 1건 인용」 만 말해 웃거름용 비료가 약 목록으로 읽혔다 — 무엇을(계열) 어느 작업의 것으로(작업) 말하는지 라이브로
    cit = next(e for e in judge_run.judgments_for(SID, today=T) if e.decision_id == "material_citation")
    yak = _chat.answer(sub, "약 뭐 쳐요", T)
    pairs = [(g.get("task"), g.get("family")) for g in (cit.result or {}).get("groups") or []]
    s.check(bool(pairs) and all(t and f and t in yak and f in yak for t, f in pairs) and "/judge" not in yak and "효능 보증은 아닙니다" in yak,
            "자재 인용 답이 인용한 계열과 그 작업을 말한다(주소가 아니라 메뉴 이름 · 보증 아님은 남는다)",
            f"{' · '.join(f'{t}: {f}' for t, f in pairs) or '없음'}")
    # [둘째 작목 걷기 2026-10-07] 「지금 답할 수 있는 것」 은 손으로 적던 넷이었고 실제로는 다섯이 선다 — 세어서 말하는지 라이브로 본다
    stands = [e.decision_id for e in judge_run.judgments_for(SID, today=T) if e.kind in _chat.STANDS]
    line = _chat.can_say_line(sub, T)
    missing = [words.decision(d) for d in stands if words.decision(d) not in line]
    extra = [words.decision(e.decision_id) for e in judge_run.judgments_for(SID, today=T)
             if e.kind not in _chat.STANDS and words.decision(e.decision_id) in line]
    s.check(not missing and not extra and len(stands) >= 5,
            "「지금 답할 수 있는 것」 은 서는 봉투를 세어 말한다(못 하는 것은 안 넣는다)",
            f"서는 것 {len(stands)} · 빠진 이름 {missing or 0} · 잘못 든 이름 {extra or 0}")


def check_asking(s: Sheet) -> None:
    """묻기·초안 주장들 — **조건을 먼저 세운다**(첫 판의 ① 이 그래서 틀렸다). 원장은 tmp 에만 쓴다."""
    from ingest import asks, chat, events as ev, known, parcels, subjects
    m, _r = chat.send(SID, "풀 뽑았다", today=T, now=NOW)
    pend = asks.pending(SID)
    s.check(bool(pend) and pend.get("fields") == ["drainage"], "값이 없으면 그 값을 묻는다(배수)", pend and (pend.get("axes"), pend.get("fields")))
    m2, _ = chat.send(SID, "배수는 좋아요", today=T, now=NOW)
    cards = [(d["kind"], d.get("field"), d.get("value")) for d in m2["drafts"]]
    s.check(("parcel.field", "drainage", "좋음") in cards, "한 낱말·한 토막 답이 그 값의 카드로 선다: 「배수는 좋아요」", cards)
    # 인증 답(「무농약」)은 **인증 물음이 선 뒤**에만 묶인다. 그 조건(인증을 아직 모르는 농사)은 이 과정의 격리와 다르므로 **따로 돌린다**(--cert-probe) —
    # 같은 과정에서 인증을 지우면 뒤따르는 화면 주장들이 다른 조건에서 측정된다(조건 오염 · J6 게스트 프로브의 그 형태).
    import subprocess
    out = subprocess.run([sys.executable, "-B", str(pathlib.Path(__file__).resolve()), "--cert-probe"],
                         capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=600)
    tail = (out.stdout or out.stderr).strip().splitlines()[-1:] or [""]
    s.check("CERT_CARD_OK" in out.stdout, "인증 답(「무농약」)이 그 값의 카드로 선다(인증 물음이 선 뒤 — 따로 돌린 조건)", tail[0])
    ev.add_observation(SID, "종구생산을 위한 목적이다", "2026-10-04")
    ev.add_observation(SID, "고랑 물 빠짐이 잘 되고 있다", "2026-10-03")
    m4, _ = chat.send(SID, "풀 뽑았다", today=T, now=NOW)
    props = [(d.get("field"), d.get("value")) for d in m4["drafts"] if d["kind"] == "parcel.field"]
    s.check(("use", "종구 생산") in props, "일지의 용도 선언을 읽어 밭 정보 카드로 올린다(묻지 않는다)", props)
    k = known.known_field(subjects.by_id(SID), "use")
    s.check(bool(k) and k.get("from") in ("attribute", "observation"), "묻기 전에 속성 → 일지 순으로 읽는다", k)
    idx = next(i for i, d in enumerate(m4["drafts"]) if d["kind"] == "parcel.field" and d.get("field") == "use")
    rec = chat.confirm(m4["id"], idx, now=NOW)
    s.check(rec.get("opens") == list(parcels.FIELD_CONSUMERS["use"]), "확인 직후 줄이 여는 판단 전부를 말한다", (rec.get("field"), rec.get("opens")))


def _text(body: str) -> str:
    """태그를 걷어 낸 **글**만 — 속성(href · value)은 글이 아니다(첫 판의 ③ 이 그래서 틀렸다)."""
    return re.sub(r"<[^>]*>", " ", re.sub(r"<(script|style)[^>]*>.*?</\1>", " ", body, flags=re.S))


def check_screens(s: Sheet) -> None:
    """화면 주장들 — HTTP 로 실제 쪽을 받는다."""
    from frontend import config, render, selfcheck, serve
    from schema import labels
    config.PORT = 0
    srv = serve.make_server()
    threading.Thread(target=srv.serve_forever, daemon=True).start()

    def get(path: str) -> tuple[int, str]:
        c = http.client.HTTPConnection("127.0.0.1", srv.server_address[1], timeout=120)
        c.request("GET", path)
        res = c.getresponse()
        return res.status, res.read().decode("utf-8", "replace")

    try:
        st, me = get("/me")
        s.check(st == 200 and labels.label("/me") in me and labels.ME_SECTIONS["parcel"] in me,
                "화면 이름이 한 목록에서 온다(왼쪽 메뉴 · 구역)", (labels.label("/me"), labels.ME_SECTIONS["parcel"]))
        st, jd = get("/judge")
        s.check(st == 200 and "재배 달력가" not in jd and "일지은" not in jd, "판단 화면에 조사 어긋남이 없다", st)
        st, sc = get("/selfcheck")
        u = selfcheck.utterances(T, selfcheck.subject())
        s.check(st == 200 and u["with_expected"] >= 6 and u["differ"] == 0 and render.PASTE_STYLE in sc,
                "문장 형태 점검 — 기대 붙은 줄은 전부 맞고 복사 묶음이 있다",
                f"기대 {u['with_expected']} · 맞음 {u['ok']} · 다름 {u['differ']} · 전체 {sum(len(g['rows']) for g in u['groups'])}")
        st, dec = get("/me/decisions")
        s.check(st == 200 and "세션에 보낼 것" in dec, "결정 화면이 선다", st)
        # [낡음 대조 2026-10-06] 「답 0/15」 는 그 15 안에 폼 없는 결정됨 카드(D-22)가 있어 **닿을 수 없는 셈**이었다 — 셋으로 갈랐고 폼 수가 남은 수와 같은지까지 본다
        from ingest import decisions as _dc
        sm = _dc.summary(_dc.load())
        # [손 노릇 2026-10-07] 저장 폼은 하나(열넷 → 1)이고 줄마다 **칸**이 있다 — 셈과 맞춰 보는 것은 그 칸 수다
        groups = len(re.findall(r'name="v:[^"]+"\s+value="맞다"', dec))
        forms = dec.count('action="/me/decisions"')
        shown = f"남은 {sm['open']}" in _text(dec) and f"결정됨 {sm['decided']}" in _text(dec)
        s.check(st == 200 and shown and groups == sm["open"] and forms == 1 and sm["open"] + sm["decided"] + sm["answered"] == sm["total"],
                "결정 화면의 셈이 결정됨을 갈라 센다(답 칸 수 = 남은 수 · 저장은 한 폼)",
                f"남은 {sm['open']} · 답 {sm['answered']} · 결정됨 {sm['decided']} · 전체 {sm['total']} · 칸 {groups} · 저장 폼 {forms}")
        seen = []
        for p in (f"/c/{SID}", "/judge", "/me", "/events", "/media", "/improve", f"/mall/{SID}", f"/diary/{SID}"):
            st, body = get(p)
            if st != 200 or SID in _text(body):
                seen.append((p, st))
        s.check(not seen, "화면의 **글**에 재배 단위 id 가 없다(속성에는 그대로 — 정확함을 안 버린다)", seen or "여덟 화면 전부")
        # [목록 전수 2026-10-07] 일지에 **줄이 있는 상태**로 — 줄머리가 원장의 이름(사건 · 관찰 · 계획 · 불이행 사유)이면 농가가 그것을 읽는다
        from ingest import chat as _c2, events as _ev2
        _ev2.add_event(SID, "관수", T.isoformat(), note="물 줬다")
        _ev2.add_farmer_plan(SID, "웃거름", T.isoformat(), note="모레")
        st, body = get(f"/diary/{SID}")
        text = _text(body)
        rows = _c2.diary(SID)
        exact = sorted({_c2.KIND_LABEL[k] for k in _c2.DIARY_SHOWS if _c2.KIND_LABEL[k] != _c2.KIND_PLAIN[k]} & set(re.findall(r"[가-힣 ]+", text)))
        s.check(st == 200 and len(rows) >= 2 and not exact and _c2.KIND_PLAIN["event"] in text,
                "일지에 줄이 있을 때 줄머리가 사람 말이다(원장의 이름은 글에 없다)",
                f"줄 {len(rows)} · 원장 이름 {exact or 0} · 「{_c2.KIND_PLAIN['event']}」 {'있음' if _c2.KIND_PLAIN['event'] in text else '없음'}")
        # [내부 값 전수 2026-10-07] 점 찍힌 내부 이름(kind 꼴) · 영문 역할이 농가 화면의 **글**에 남아 있나 — 기록이 있는 상태로 전수
        # 파일 이름(`…json` · `…bat`)은 **일부러 둔다** — 발행자 몫 문장은 고칠 파일을 짚어야 한다(judge.need.DEV_TOKENS 의 기록된 결정 · test_grid_unit_miss 가 그것을 지킨다)
        dotted = re.compile(r"(?<![\w/.])[a-z][a-z_]{2,}\.(?!json|jsonl|bat|py|md|csv|env|html|js|cjs|txt|yml|toml)[a-z][a-z_]{2,}(?![\w/])")
        code = re.compile(r"<code>.*?</code>", re.S)
        leaks: dict[str, list[str]] = {}
        for p in (f"/c/{SID}", f"/diary/{SID}", "/judge", "/me", "/events", "/media", "/improve", "/changes", f"/mall/{SID}"):
            st2, b2 = get(p)
            t2 = _text(code.sub(" ", b2))
            hits = sorted(set(dotted.findall(t2)) | {w for w in ("farmer", "publisher") if re.search(rf"(?<![A-Za-z_]){w}(?![A-Za-z_])", t2)})
            if st2 != 200 or hits:
                leaks[p] = hits or [str(st2)]
        s.check(not leaks, "농가 화면의 글에 내부 이름(점 찍힌 종류 · 영문 역할)이 없다", leaks or "아홉 화면 전부")
    finally:
        srv.shutdown()
        srv.server_close()


GROUPS = (("분류", check_classification), ("사람 글", check_people_words), ("소비자", check_consumers),
          ("경보", check_alerts), ("묻기", check_asking), ("화면", check_screens))


def run(http_too: bool = True) -> Sheet:
    s = Sheet()
    for name, fn in GROUPS:
        if name == "화면" and not http_too:
            s.say(NA, "화면 주장들 — --no-http 로 건너뜀", "HTTP 없음")
            continue
        fn(s)
    return s


def cert_probe() -> int:
    """인증을 **아직 모르는** 조건을 세우고 인증 물음이 설 때까지 보낸 뒤 「무농약」 으로 답한다(배수 물음이 반복 상한 3회에 닿으면 인증이 선다 — 실측 2026-10-05)."""
    w = isolate()
    for path, key in ((w / "subjects.json", "cert"), (w / "parcels.json", "cert_claimed")):
        doc = json.loads(path.read_text(encoding="utf-8"))
        rows = next((v for v in doc.values() if isinstance(v, list)), doc) if isinstance(doc, dict) else doc
        rows[0].pop(key, None)
        path.write_text(json.dumps(doc, ensure_ascii=False), encoding="utf-8")
    sys.path.insert(0, str(ROOT))
    from ingest import asks, chat
    for _ in range(8):
        chat.send(SID, "풀 뽑았다", today=T, now=NOW)
        p = asks.pending(SID)
        if p and "cert" in (p.get("axes") or []):
            m, _r = chat.send(SID, "무농약", today=T, now=NOW)
            cards = [(d["kind"], d.get("axis") or d.get("field"), d.get("value")) for d in m["drafts"]]
            ok = any(k == "subject.field" and f == "cert" and v == "무농약" for k, f, v in cards)
            print(f"{'CERT_CARD_OK' if ok else 'CERT_CARD_NO'} {cards}")
            return 0 if ok else 1
    print("CERT_ASK_NONE — 인증 물음이 서지 않았다(조건을 못 만들었다)")
    return 1


def main(argv: list[str]) -> int:
    if "--cert-probe" in argv:
        return cert_probe()
    w = isolate()
    sys.path.insert(0, str(ROOT))
    sheet = run(http_too="--no-http" not in argv)
    head = os.popen(f"cd {ROOT} && git rev-parse --short HEAD").read().strip()
    n = {v: sum(1 for x, _, _ in sheet.rows if x == v) for v in (OK, NO, NA)}
    print(f"검증 커밋 {head} · 오늘 {T.isoformat()} · 작업 경로 {w}")
    print(f"줄 {len(sheet.rows)} — 확인 {n[OK]} · 틀림 {n[NO]} · 못 잼 {n[NA]}\n")
    for verdict, claim, seen in sheet.rows:
        mark = {OK: "  ", NO: "!!", NA: "??"}[verdict]
        print(f"{mark} [{verdict}] {claim}\n      본 것: {seen}")
    return 1 if sheet.wrong else 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
