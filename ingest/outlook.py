# -*- coding: utf-8 -*-
# FILE: ingest/outlook.py
# ROLE: [D-21 장기 · 발행자 ⓐ 2026-09-28] 기상청 1·3개월 전망의 **수동 정본** 읽기 — 발행자가 발표문 수치를 출처와 함께 등재한 것만 1층 레코드로.
#   오픈 API 가 없다(VELA 실측 2026-08-05 — 인용). 그래서 이 파일은 원천을 부르지 않는다 · 값을 지어내지 않는다 · 비어 있으면 비었다고 말한다.
#   [D-9 인용] VELA core/climate_outlook · routers/admin_climate_outlook — 출처 URL 필수 · 3분위 확률 합≈100(±5) · 기간 형식 검증.
#   읽힌 것과 **못 읽은 것**을 함께 돌려준다(U-21 형태) — 형식이 틀린 항목은 조용히 빠지지 않고 이유가 화면까지 간다.
from __future__ import annotations

import json
import os
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any

from ingest import dropped

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_PATH = ROOT / "data" / "kma" / "climate_outlook.json"                 # 씨앗 — 커밋으로만(세션이 발행자 값을 받아 적을 때)
LOCAL_PATH = ROOT / "data" / "kma" / "climate_outlook_local.json"           # 덮개 — 발행자가 손으로 넣는 곳(git 밖 · update.bat 이 안 건드린다)
SRC = "publisher:kma_outlook"
DROP_WHERE = "장기 전망 등재분"      # /changes 의 '어디' 열 — 화면에 실리는 말이라 안쪽 말(정본)을 쓰지 않는다(test_screen_speaks_plainly 가 잡았다)
PERIOD_TYPES = ("1개월", "3개월")
ENTRY_KEYS = frozenset({"period_type", "issued_on", "target_from", "target_to", "region", "temp", "precip", "source_title", "source_url", "note"})
TERCILE_KEYS = ("above", "normal", "below")
SUM_TOLERANCE = 5


def path() -> Path:
    return Path(os.environ.get("AGRODSS_OUTLOOK_PATH") or DEFAULT_PATH)


def local_path() -> Path:
    """[순서 함정 2026-09-28] 추적 파일(씨앗)에 값을 넣으면 `update.bat` 이 그 수정을 `data/_local_backup/` 으로 치우고 `git checkout` 으로 되돌린다 —
    값이 화면에서 **사라진다**(parcels 가 겪은 그 형태). 그래서 발행자가 넣는 곳은 gitignore 된 덮개다. 씨앗은 세션이 커밋으로만 고친다."""
    return Path(os.environ.get("AGRODSS_OUTLOOK_LOCAL_PATH") or LOCAL_PATH)


def _day(s: Any, what: str) -> str:
    try:
        d = date.fromisoformat(str(s))
    except (TypeError, ValueError):
        raise ValueError(f"{what} 은 YYYY-MM-DD 여야 한다: {s!r}")
    if len(str(s)) != 10:
        raise ValueError(f"{what} 은 YYYY-MM-DD 여야 한다: {s!r}")
    return d.isoformat()


def _tercile(v: Any, what: str) -> dict[str, float] | None:
    if v is None:
        return None
    if not isinstance(v, dict) or set(v) != set(TERCILE_KEYS):
        raise ValueError(f"{what} 은 {{above, normal, below}} 셋이어야 한다: {v!r}")
    out: dict[str, float] = {}
    for k in TERCILE_KEYS:
        try:
            f = float(v[k])
        except (TypeError, ValueError):
            raise ValueError(f"{what}.{k} 가 숫자가 아니다: {v[k]!r}")
        if not 0 <= f <= 100:
            raise ValueError(f"{what}.{k} 가 0~100 밖: {f}")
        out[k] = f
    total = sum(out.values())
    if abs(total - 100) > SUM_TOLERANCE:
        raise ValueError(f"{what} 확률 합 {total:g} — 100±{SUM_TOLERANCE} 밖(발표문 수치를 그대로 옮겼는지 본다)")
    return out


def entry_to_record(e: dict[str, Any], fetched_at: str | None = None) -> dict[str, Any]:
    """등재 항목 하나 → 1층 레코드. 틀리면 ValueError(이유 문장) — 호출자가 '못 읽음' 으로 남긴다."""
    if not isinstance(e, dict):
        raise ValueError("항목이 객체가 아니다")
    extra = set(e) - ENTRY_KEYS
    if extra:
        raise ValueError(f"모르는 키 {sorted(extra)} — 정해진 열 밖의 값은 싣지 않는다")
    if e.get("period_type") not in PERIOD_TYPES:
        raise ValueError(f"period_type 은 {' · '.join(PERIOD_TYPES)} 중 하나: {e.get('period_type')!r}")
    issued, frm, to = _day(e.get("issued_on"), "issued_on"), _day(e.get("target_from"), "target_from"), _day(e.get("target_to"), "target_to")
    if frm > to:
        raise ValueError(f"target_from({frm}) 이 target_to({to}) 뒤다")
    region = str(e.get("region") or "").strip()
    if not region:
        raise ValueError("region 이 비었다 — 발표문의 권역 표기를 그대로")
    temp, precip = _tercile(e.get("temp"), "temp"), _tercile(e.get("precip"), "precip")
    if temp is None and precip is None:
        raise ValueError("temp · precip 둘 다 없다 — 하나는 있어야 한다")
    title, url = str(e.get("source_title") or "").strip(), str(e.get("source_url") or "").strip()
    if len(title) < 2:
        raise ValueError("source_title 이 비었다")
    if not (url.startswith("https://") or url.startswith("http://")):
        raise ValueError(f"source_url 은 발표문 주소(http…)여야 한다: {url!r} — 출처 없는 전망은 싣지 않는다")
    return {
        "kind": "reference.climate_outlook", "axis": ["forecast"], "observed_at": issued,
        "fetched_at": fetched_at or datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "source": SRC, "resolution": f"region:{region}", "period_type": e["period_type"], "period_from": frm, "period_to": to, "region": region,
        "values": {"temp": temp, "precip": precip}, "citation": {"title": title, "url": url}, "note": (str(e.get("note")).strip() or None) if e.get("note") else None,
    }


def _load_one(p: Path, out: list[dict[str, Any]], bad: list[str]) -> None:
    if not p.exists():
        return
    try:
        doc = json.loads(p.read_text(encoding="utf-8"))
    except ValueError as e:
        why = f"{p.name}: JSON 아님: {e}"
        dropped.note(DROP_WHERE, p.name, why)
        bad.append(why)
        return
    entries = doc.get("entries") if isinstance(doc, dict) else None
    if not isinstance(entries, list):
        why = f"{p.name}: entries 목록이 없다"
        dropped.note(DROP_WHERE, p.name, why)
        bad.append(why)
        return
    for i, e in enumerate(entries):
        try:
            out.append(entry_to_record(e))
        except ValueError as err:
            why = f"{p.name} entries[{i}]: {err}"
            dropped.note(DROP_WHERE, f"{p.name}#{i}", why)
            bad.append(why)


def load(p: Path | None = None, lp: Path | None = None) -> tuple[list[dict[str, Any]], list[str]]:
    """(읽힌 레코드, 못 읽은 항목의 이유) — 씨앗(추적 · 세션 커밋)과 덮개(git 밖 · 발행자 손) 둘 다에서. 파일이 없거나 entries 가 비면 ([], [])
    — 그것은 결함이 아니라 '아직 등재 없음' 이다. 못 읽은 이유는 어느 파일의 몇째 항목인지를 말한다."""
    out: list[dict[str, Any]] = []
    bad: list[str] = []
    _load_one(p or path(), out, bad)
    _load_one(lp or local_path(), out, bad)
    out.sort(key=lambda r: (r["period_from"], r["period_to"], r["region"]))
    return out, bad


TEMPLATE: dict[str, Any] = {
    "_source": "발행자 등재 덮개 — 기상청 1·3개월 전망 발표문 수치(화면 /me/outlook 또는 손). git 밖 · update.bat 이 안 건드린다 · 씨앗 climate_outlook.json 과 함께 읽힌다",
    "entries": [],
}


def _read_local_doc(p: Path) -> dict[str, Any]:
    if not p.exists():
        return {k: (list(v) if isinstance(v, list) else v) for k, v in TEMPLATE.items()}
    doc = json.loads(p.read_text(encoding="utf-8"))
    if not isinstance(doc, dict) or not isinstance(doc.get("entries"), list):
        raise ValueError(f"{p.name}: entries 목록이 없다 — 파일을 손으로 고친 뒤 다시")
    return doc


def _write_local_doc(p: Path, doc: dict[str, Any]) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    with p.open("w", encoding="utf-8") as f:                   # 완전성 래칫(test_runtime_state_files)이 open(…,"w") 를 세어 이 모듈을 '쓰는 모듈' 로 잡는다
        json.dump(doc, f, ensure_ascii=False, indent=2)
        f.write("\n")


def local_entries(p: Path | None = None) -> list[dict[str, Any]]:
    """덮개의 등재 항목 원문(순서 = 파일 순서 = 지울 때 쓰는 번호)."""
    try:
        return list(_read_local_doc(p or local_path())["entries"])
    except (ValueError, OSError):
        return []


def append_local(entry: dict[str, Any], p: Path | None = None) -> dict[str, Any]:
    """[⑤b 입력 폼 2026-09-28] 항목 하나를 덮개에 더한다 — **먼저 검증**(틀리면 ValueError · 아무것도 안 쓴다) · 같은 항목이 이미 있으면 다시 안 쓴다
    (확인 더블탭이 원장에 두 줄을 낸 전례 — 멱등). 돌려주는 것은 그 항목의 레코드."""
    rec = entry_to_record(entry)
    p = p or local_path()
    doc = _read_local_doc(p)
    clean = {k: entry[k] for k in ENTRY_KEYS if k in entry and entry[k] not in (None, "")}
    if clean in doc["entries"]:
        return rec
    doc["entries"].append(clean)
    _write_local_doc(p, doc)
    return rec


def remove_local(index: int, p: Path | None = None) -> dict[str, Any]:
    """덮개의 index 번째 항목을 지운다(씨앗은 못 지운다 — 세션 커밋). 없으면 ValueError."""
    p = p or local_path()
    doc = _read_local_doc(p)
    if not 0 <= index < len(doc["entries"]):
        raise ValueError(f"지울 항목이 없다: {index} (덮개 항목 {len(doc['entries'])}개)")
    gone = doc["entries"].pop(index)
    _write_local_doc(p, doc)
    return gone


def covering(records: list[dict[str, Any]], today: date) -> list[dict[str, Any]]:
    """오늘 뒤를 덮는 항목만(끝난 기간은 낸 적 없는 것처럼 — 낡은 전망은 전망이 아니다)."""
    t = today.isoformat()
    return [r for r in records if r["period_to"] >= t]
