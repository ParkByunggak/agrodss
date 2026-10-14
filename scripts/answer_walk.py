# -*- coding: utf-8 -*-
# FILE: scripts/answer_walk.py
# ROLE: 앞날 걷기(답) — 지정한 날짜들에 **농가가 채팅에서 받을 답**을 미리 받아 본다. 읽기 전용 측정 도구(격리 사본에서만 돈다).
#
#   [2026-10-14 · 앞날 걷기 목록을 잃었다] 10-13 의 앞날 걷기(발견 47 · 즉시급 22)는 스크래치패드의 측정 스크립트로 쟀고, 결과 표도 거기 있었다.
#   세션 컨테이너가 회수되며 **둘 다 사라졌고**, 대장 페이지와 핸드오버에는 「F8 · F10 …」 번호만 남았다 — 아무도 풀 수 없는 번호다.
#   time_walk.py 가 같은 이유로 섰다(U-35: "세션이 끝나면 사라지므로 여기 둔다") — 그때는 **판정**을 걷는 도구였고 **답**을 걷는 도구는 저장소에 없었다.
#   그래서 여기 둔다. 판정 표는 time_walk 가, 화면 한 날은 walk.sh 가, **날짜를 가로지르는 답**은 이것이 본다. 발견의 목록은 docs/walk_findings.md 가 든다.
#
#   쓰는 법   python -m scripts.answer_walk [YYYY-MM-DD ...]   날짜가 없으면 오늘(서울 — 화면의 「오늘」 정본 config.today)
#            --only <재배 단위 id> · --use <용도>(그 밭의 용도를 격리 사본에 넣고 걷는다 — 「종구 생산」 을 넣은 뒤의 답) ·
#            --ask <물음>(여러 번 · 없으면 QUESTIONS) · --add <작목:작기[:심은 날]>(여러 번 — 격리 사본에 재배 단위를 세우고 걷는다)
#   [재검토 WF-2 · 2026-10-14] 씨앗 등록부에는 쪽파 하나뿐이라 발견 목록의 대파 행(W-08 · W-12 · W-29)을 그 「어디서」 로 다시 잴 수 없었다 — 걷기 때는
#   채팅으로 대파를 세웠다. 그 차림을 --add 로 둔다(예: --add "대파:2026 가을:2026-09-01"). 없는 --only 는 빈 출력 · rc 0 이 아니라 이유와 rc 2 다
#   [재재검토] 화면 행(W-12 · W-29 …)은 답이 아니라 **화면**이라 같은 차림으로 화면을 볼 길이 없었다 — --screen <경로>(여러 번)가 그 격리 사본에 화면을 띄워
#   날짜마다 **보이는 글**을 낸다(예: --add "대파:2026 가을:2026-09-01" --screen "/c/p001-대파-2026가을" --ask 없이)
#   [W-14 · W-15 2026-10-14] 「카드」 렌즈의 행(채팅에 적고 → 넣고 → 며칠 뒤 답)을 이 도구로 다시 잴 길이 없었다 — 재현이 스크래치 스크립트에만 있었다(목록을
#   잃은 그 꼴). --say "<날짜>:<문장>"(여러 번)이 그 날 채팅에 그 말을 적고 **초안을 다 넣은 뒤** 걷는다(예: --say "2026-10-14:비 때문에 수확 못 했다" 2026-10-24)
#   규율     운영 data 를 건드리지 않는다(scripts.verify_claims.isolate — conftest · walk.sh 와 같은 격리 목록 하나를 쓴다) ·
#            값을 제안하지 않는다 — 답을 그대로 보일 뿐이다
from __future__ import annotations

import argparse
import os
import sys
from datetime import date
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
# [재검토 F3 · 2026-10-14] 여기 있던 os.environ.setdefault("TZ", …) 는 time 이 이미 적재된 뒤라 효과가 없었다 — 밭의 시각은 이제 정본(config.today · FARM_TZ)이 센다

# 농가가 실제로 묻는 꼴 — 판단마다 하나 이상(물음 · 할 일 · 위험 · 자재 · 날씨 · 수확). 정답을 적지 않는다(측정 도구다)
QUESTIONS: tuple[str, ...] = (
    "수확 언제 해요", "오늘 뭐 해야 하나", "위험한 거 있나", "서리 오나", "약 뭐 쳐요", "웃거름 언제 줘요",
    "물 줘야 하나", "배수 괜찮나", "병충해 뭐 봐야 하나", "내일 날씨 어때",
)


def add_spec(text: str) -> dict[str, str]:
    """「작목:작기[:심은 날]」 → ingest.subjects.add 인자. 심은 날이 있으면 재배 중 · 없으면 계획."""
    parts = [p.strip() for p in text.split(":")]
    if len(parts) not in (2, 3) or not all(parts):
        raise ValueError(f"--add 는 「작목:작기[:심은 날]」 꼴이다(예: 대파:2026 가을:2026-09-01) — 받은 것: {text!r}")
    spec = {"crop": parts[0], "season": parts[1], "status": "계획"}
    if len(parts) == 3:
        date.fromisoformat(parts[2])
        spec.update(anchor=parts[2], status="재배 중")
    return spec


def say_spec(text: str) -> tuple[date, str]:
    """「날짜:문장」 → (그 날, 문장). 문장 안의 쌍점은 그대로 둔다(첫 쌍점에서만 가른다)."""
    day, sep, said = text.partition(":")
    if not sep or not said.strip():
        raise ValueError(f"--say 는 「날짜:문장」 꼴이다(예: 2026-10-14:비 때문에 수확 못 했다) — 받은 것: {text!r}")
    return date.fromisoformat(day.strip()), said.strip()


def _say(subject_id: str, says: tuple[tuple[date, str], ...]) -> list[dict[str, Any]]:
    """그 날 채팅에 적고 초안을 **다** 넣는다(날짜가 비어 있으면 그 날로) — 넣은 것을 줄로 돌려준다(걷기 출력의 머리에 보인다)."""
    from ingest import chat
    rows: list[dict[str, Any]] = []
    for day, said in says:
        os.environ["AGRODSS_TODAY"] = day.isoformat()
        m, _r = chat.send(subject_id, said, today=day)
        for i, d in enumerate(m.get("drafts") or []):
            if d.get("kind") == "question":
                continue
            rec = chat.confirm(m["id"], i, day=day.isoformat() if d.get("needs") else None)
            rows.append({"date": day.isoformat(), "day": None, "subject": subject_id, "use": "", "ask": f"적고 넣음: {said}",
                         "answer": f"{chat.KIND_PLAIN.get(d.get('kind'), d.get('kind'))} · {rec.get('observed_at', '')} · {chat.plain_why(d)}"})
    return rows


def _visible(page: str) -> str:
    """화면의 보이는 글 — 꾸밈 · 스크립트 · 스타일을 걷고 공백을 한 칸으로."""
    import html
    import re
    page = re.sub(r"(?is)<(script|style)\b.*?</\1>", " ", page)
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", page))).strip()


def _screens(days: list[date], paths: tuple[str, ...]) -> list[dict[str, Any]]:
    """격리 사본 위에 화면을 띄워 날짜마다 그 경로의 보이는 글을 받는다(루프백 · 빈 포트 · 끝나면 내린다)."""
    import http.client
    import threading
    from urllib.parse import quote
    from frontend import config, serve
    config.PORT = 0
    srv = serve.make_server()
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    rows: list[dict[str, Any]] = []
    try:
        for today in days:
            os.environ["AGRODSS_TODAY"] = today.isoformat()
            for path in paths:
                c = http.client.HTTPConnection("127.0.0.1", srv.server_address[1], timeout=30)
                c.request("GET", quote(path, safe="/?=&"))
                r = c.getresponse()
                rows.append({"date": today.isoformat(), "day": None, "subject": f"화면 {path}", "use": "", "ask": f"HTTP {r.status}",
                             "answer": _visible(r.read().decode("utf-8", "replace"))})
    finally:
        srv.shutdown()
        srv.server_close()
    return rows


def walk(days: list[date], only: str | None = None, use: str | None = None, asks: tuple[str, ...] = QUESTIONS,
         add: tuple[dict[str, str], ...] = (), screens: tuple[str, ...] = (), says: tuple[tuple[date, str], ...] = ()) -> list[dict[str, Any]]:
    """날짜 × 재배 단위 × 물음 → 답(+ 화면). 격리 사본을 먼저 세운다(부르는 쪽이 따로 세우지 않아도 운영 data 에 닿지 않게)."""
    from scripts import verify_claims
    verify_claims.isolate()
    from ingest import chat, media, parcels, subjects
    for spec in add:
        subjects.add(**spec)                                           # 격리 사본의 덮개에만 쓴다
    rows: list[dict[str, Any]] = []
    every = media.load_subjects()
    subs = [s for s in every if not only or s.get("id") == only]
    if not subs:
        raise ValueError(f"걸을 재배 단위가 없다(--only {only!r}) — 있는 것: {' · '.join(str(s.get('id')) for s in every) or '없음'}")
    if use:
        for pid in dict.fromkeys(s.get("parcel") for s in subs if s.get("parcel")):
            parcels.set_fields(pid, use=use, overwrite=True)          # 격리 사본의 덮개에만 쓴다
    # 격리 사본의 원장에만 — --only 가 있으면 그 재배 단위, 없으면 첫 단위. [검토 2026-10-14] 말한 날 **이전**의 답은 그 기록을 몰라야 한다 —
    # 처음에는 다 넣고 걸어서 10-14 의 답이 10-16 에 넣은 수확을 이미 읽었다(앞날 기록). 날 순서대로 걷고, 그 날까지 말한 것만 넣는다
    pending = sorted(says)
    for today in sorted(days):
        now_said = tuple(x for x in pending if x[0] <= today)
        pending = [x for x in pending if x[0] > today]
        rows += _say(str(subs[0].get("id")), now_said)
        os.environ["AGRODSS_TODAY"] = today.isoformat()
        for s in subs:
            anchor = s.get("anchor")
            day = (today - date.fromisoformat(anchor)).days if anchor else None
            for q in asks:
                rows.append({"date": today.isoformat(), "day": day, "subject": s.get("id"), "use": use or "", "ask": q,
                             "answer": chat.answer(s, q, today)})
        if screens:
            rows += _screens([today], screens)                         # 화면도 그 날까지 말한 것만 안다(검토 — 처음엔 다 넣은 뒤에 화면을 받았다)
    rows += _say(str(subs[0].get("id")), tuple(pending))              # 걷는 날보다 뒤에 말한 것 — 넣은 줄은 보이되 답에는 안 닿는다
    return rows


def render(rows: list[dict[str, Any]]) -> str:
    out: list[str] = []
    last = None
    for r in rows:
        key = (r["date"], r["subject"])
        if key != last:
            out.append(f"\n===== {r['date']} · {r['subject']}" + (f" · 심은 뒤 {r['day']}일" if r["day"] is not None else "")
                       + (f" · 용도 {r['use']}" if r["use"] else "") + " =====")
            last = key
        out.append(f"-- {r['ask']}\n{r['answer']}")
    return "\n".join(out)


def main(argv: list[str] | None = None) -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    ap = argparse.ArgumentParser(description="앞날 걷기(답) — 읽기 전용")
    ap.add_argument("days", nargs="*")
    ap.add_argument("--only")
    ap.add_argument("--use")
    ap.add_argument("--ask", action="append")
    ap.add_argument("--add", action="append", default=[])
    ap.add_argument("--screen", action="append", default=[])
    ap.add_argument("--say", action="append", default=[])
    a = ap.parse_args(argv)
    from frontend import config
    try:
        days = [date.fromisoformat(d) for d in a.days] or [config.today()]
        asks = tuple(a.ask) if a.ask else (() if a.screen else QUESTIONS)          # 화면만 볼 때는 물음을 안 돌린다
        rows = walk(days, a.only, a.use, asks, tuple(add_spec(t) for t in a.add), tuple(a.screen), tuple(say_spec(t) for t in a.say))
    except ValueError as e:
        print(f"!! {e}", file=sys.stderr)
        return 2
    print(render(rows))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
