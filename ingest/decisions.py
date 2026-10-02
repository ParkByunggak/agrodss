# -*- coding: utf-8 -*-
# FILE: ingest/decisions.py
# ROLE: [WO-PB-01 다음 한 수 · 발행자 승인 2026-09-29] 일괄 결정 자리 — 발행자만 답할 수 있는 것(P1)을 제안값과 함께 한 화면에 놓고
#   줄마다 「맞다 / 다르다(→ 무엇) / 모르겠다」 만 찍게 한다. 검토지(파일 · 09-18)는 11일째 답 칸이 비어 있었다 — 자리가 없어서가 아니라
#   **파일이라 화면에서 안 보였다**(D-20 임계도 폼이 생긴 뒤에야 채워질 자리가 됐다). 이 모듈이 그 자리의 정본이다.
#   발행자 셋(2026-09-29): ① 「모르겠다」 는 1급 선택지 — 두 단추만 있으면 모르는 항목이 다시 비어 남고, 모르겠다가 쌓이면 그것이
#   P1 이 아니라 P4 였다는 신호다(갈래 판정을 사후에 교정하는 유일한 경로) ② 제안값의 출처가 추론이면 그 표시가 붙어야 한다 — 안 붙으면
#   「맞다」 가 눌리며 추론이 정본으로 승격된다 ③ 맨 위는 D-2(다섯이 매달린다).
#   답은 git 밖 덮개(data/decisions_local.json)에만 — 추적 파일에 쓰면 update.bat 이 되돌린다(순서 함정). 작업 기록의 상태 열은 세션이
#   발행자 답을 받아 커밋으로만 고친다 — 이 화면은 답을 **모으고 보이게** 할 뿐 항목을 닫지 않는다(WO-PB-01 §7).
from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ingest import dropped

ROOT = Path(__file__).resolve().parent.parent
LOCAL_PATH = ROOT / "data" / "decisions_local.json"
DROP_WHERE = "결정 답"      # /changes 「읽다 버린 것」 의 '어디' 열 — 화면에 실리는 말
VERDICTS = ("맞다", "다르다", "모르겠다")
UNKNOWN = "모르겠다"
# 제안값의 출처 종류 — 화면이 이 이름을 그대로 단다. 「추론」 은 세션이 미룬 값이라 맞다를 눌러도 표시가 남는다(승격 금지).
BASIS_RECOMMENDED = "권고"      # 작업 기록·핸드오버에 권고로 적혀 있던 것
BASIS_INFERRED = "추론"         # 세션이 앞뒤 사정에서 미룬 값 — 정본이 아니다
BASIS_KINDS = (BASIS_RECOMMENDED, BASIS_INFERRED)
BASIS_SAID = {BASIS_RECOMMENDED: "권고 — 작업 기록에 권고로 적혀 있던 값", BASIS_INFERRED: "추론 — 세션이 앞뒤 사정에서 미룬 값(확정된 값이 아님 · 맞다를 눌러도 이 표시는 남는다)"}

# 항목 — 순서가 화면 순서다(맨 위 D-2). id 는 작업 기록·측정(scripts/measure_publisher_bottleneck) 의 P1 판정과 같아야 한다(검사가 대조).
# basis_from 은 제안값이 **어디 적힌 것**인지 — 그 문면이 저장소 문서에 실제로 있어야 한다(검사가 찾는다 · 지어낸 출처를 막는다).
ITEMS: tuple[dict[str, Any], ...] = (
    {"id": "D-2", "ask": "판정을 소비자에게 보일 것인가", "default": "첫 시즌은 보이지 않는다 — 판정 3회 재현 확인 뒤 다시 정한다",
     "basis": BASIS_RECOMMENDED, "basis_from": "첫 시즌 비노출", "unblocks": "D-3 · D-7 · D-19 · M-11 (다섯이 이 답에 매달린다)"},
    {"id": "D-3", "ask": "예약 판매를 도입할 것인가", "default": "지금은 안 한다 — 수량 예측과 수확 실패 환불 규칙이 먼저인데 둘 다 보류다",
     "basis": BASIS_INFERRED, "basis_from": "수량 예측(U-7) · 수확 실패 환불 규칙(U-8)이 선행", "unblocks": "M-11 몰 예약 자리"},
    {"id": "D-7", "ask": "몰 화면을 어떤 기술로 만들 것인가", "default": "지금은 목업 그대로 — D-2 · D-3 답이 선 뒤에 정한다",
     "basis": BASIS_INFERRED, "basis_from": "영상 상세페이지·주문 흐름은 별도 스택 결정이 필요", "unblocks": "M-11"},
    {"id": "D-19", "ask": "검색엔진에 어느 화면을 언제 공개할 것인가 · 호스팅", "default": "몰 상세페이지만 · 첫 수확 뒤 · 호스팅은 그때 정한다",
     "basis": BASIS_INFERRED, "basis_from": "공개는 몰 상세페이지만 · 첫 수확 뒤 · 호스팅은 그때 정한다", "unblocks": "공개 화면의 제목·설명·robots 작업"},
    {"id": "D-16", "ask": "휴대폰 동기화(같은 Wi-Fi)를 켤 것인가", "default": "켠다 — 같은 Wi-Fi 에서 토큰으로",
     "basis": BASIS_RECOMMENDED, "basis_from": "D-16** 휴대폰 동기화(권고 켠다)", "unblocks": "휴대폰에서 사진·글 반입"},
    {"id": "D-17", "ask": "사진의 찍은 때를 파일 이름에서도 읽을 것인가", "default": "둔다 — 「파일 이름의 때 — 저장·전송 시각일 수 있습니다」 라벨을 유지한 채",
     "basis": BASIS_RECOMMENDED, "basis_from": "① 이 칸을 둔다(권고", "unblocks": "촬영 기록 문서(I-7) 문면"},
    {"id": "D-4", "ask": "몰 바깥 계약(결제 · 택배 · 본인확인)을 언제 맺을 것인가", "default": "지금은 정하지 않는다 — 판매 작기가 생기면",
     "basis": BASIS_INFERRED, "basis_from": "자체 구축 금지 영역. 시스템 밖", "unblocks": "—"},
    {"id": "R-W", "ask": "쪽파 수확 시기 50~70일(10/14~11/3)이 이 밭 경험과 맞는가", "default": "지금 값 50~70일(±10일) 그대로",
     "basis": BASIS_INFERRED, "basis_from": "격자 초안 50~70 · 오차 ±10일", "unblocks": "수확 시기 판정 · 수확 지연 경보 날짜 — 처음 지으신 밭이면 「모르겠다」 가 맞는 답이다"},
    {"id": "H-⑦", "ask": "날씨·예찰 호출 상한과 예보 메모를 항목으로 올릴 것인가", "default": "올린다 — 회수 대기(지금은 안 나지만 원천이 느리면 난다)",
     "basis": BASIS_INFERRED, "basis_from": "등재 후보(칸 2 · 발행자 판단 — 다리 B)", "unblocks": "예보 호출 상한 처방"},
    {"id": "H-후보㉠", "ask": "예찰 마감을 넘긴 닫힌 칸의 회복 불가 위험(고자리파리)을 다음 칸에서도 「지켜볼 것」 에 남길 것인가", "default": "올린다 — 경보 규칙에 한 줄",
     "basis": BASIS_INFERRED, "basis_from": "닫힌 칸 회복 불가 위험 잔류", "unblocks": "위험 경보 규칙 한 줄"},
    {"id": "H-후보㉡", "ask": "배수 물음(고랑 · 물 빠짐)을 칸 카드에서 풀어 위험 경보처럼 답하게 할 것인가", "default": "올린다 — 병충해 물음과 같은 길로",
     "basis": BASIS_INFERRED, "basis_from": "배수 물음의 칸 묶임", "unblocks": "배수 물음의 길"},
    {"id": "H-후보㉢", "ask": "평년값(기상청 평년)을 날씨 답에 인용할 것인가", "default": "올린다 — 「평년보다 N℃ 높다」 한 줄",
     "basis": BASIS_INFERRED, "basis_from": "평년값 인용", "unblocks": "날씨 답의 평년 비교 줄"},
    {"id": "H-후보㉣", "ask": "재배 목록·필지·사용자 정보 덮개 파일이 깨졌을 때 — 씨앗으로 화면을 내되 그 사실을 말할 것인가(지금은 모든 화면이 오류)", "default": "씨앗으로 내되 그 사실을 말한다 — 화면 전체가 죽는 것보다 낫고 「버린 것을 말한다」 와 같은 형태",
     "basis": BASIS_RECOMMENDED, "basis_from": "씨앗으로 내되 그 사실을 말하는 쪽", "unblocks": "세 로더의 손상 파일 처방(결정 화면과 같은 형태)"},
    # [발행자 2026-10-03 "수확 칸(10/15~) 임계 물음은 없어도 되는 쪽입니다 … 제 추론이니 결정 화면에 그렇게 표시된 채로 두시면 됩니다"] — 추론 표시 그대로
    {"id": "D-22", "ask": "수확 칸(10/14~11/3)에도 가뭄 임계(비 안 온 지 7일)를 둘 것인가", "default": "두지 않는다 — 수확 칸은 수분 요구 낮음 · 결핍 민감 낮음이라 가뭄 답을 「이 칸에는 가뭄 판단이 없다」 로 닫는다",
     "basis": BASIS_INFERRED, "basis_from": "수확 칸(10/15~) 임계 물음은 없어도 되는 쪽", "unblocks": "10-15 부터의 가뭄 답(지금은 「기준이 없습니다」) — 맞다 한 번이면 재배 달력 수확 칸에 N/A 로 적는다"},
)
IDS = tuple(i["id"] for i in ITEMS)


def local_path() -> Path:
    """답이 쌓이는 덮개(git 밖). 추적 파일에 쓰면 update.bat 이 _local_backup 으로 치우고 되돌린다 — 값이 화면에서 사라진다."""
    return Path(os.environ.get("AGRODSS_DECISIONS_LOCAL_PATH") or LOCAL_PATH)


def item(id_: str) -> dict[str, Any]:
    for i in ITEMS:
        if i["id"] == id_:
            return i
    raise ValueError(f"없는 항목: {id_!r}")


def _read(p: Path) -> dict[str, Any]:
    if not p.exists():
        return {"answers": {}}
    try:
        doc = json.loads(p.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        raise ValueError(f"{p.name} 을 못 읽었다: {e}")
    if not isinstance(doc, dict) or not isinstance(doc.get("answers"), dict):
        raise ValueError(f"{p.name} 의 모양이 다르다 — {{\"answers\": {{…}}}} 여야 한다")
    return doc


def _write(p: Path, doc: dict[str, Any]) -> None:
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "w", encoding="utf-8") as f:
        json.dump(doc, f, ensure_ascii=False, indent=2)


def load(p: Path | None = None) -> dict[str, dict[str, Any]]:
    """{id: {verdict, note, at}} — 없는 항목의 답은 버리지 않고 그대로 둔다(항목이 바뀌어도 답이 사라지지 않게) · 화면은 IDS 만 보인다."""
    return dict(_read(p or local_path())["answers"])


def read_for_screen(p: Path | None = None) -> tuple[dict[str, dict[str, Any]], str | None]:
    """화면용 읽기(U-21 형태) — 못 읽으면 (빈 답, 이유). 화면은 이유를 말하고 폼은 그대로 낸다 · 저장은 answer() 가 같은 이유로 거부한다(파일을 덮어쓰지 않는다).
    [2026-09-30 실측] 손상 JSON 에 load() 가 예외를 던져 /me/decisions 가 통째로 500 이었다 — 서버의 마지막 방어선이 오류 페이지로 바꾸지만 폼도 이유도 없다."""
    p = p or local_path()
    try:
        return load(p), None
    except ValueError as e:
        why = str(e)
        dropped.note(DROP_WHERE, p.name, why)      # /changes 에도 뜬다(조용한 실패 금지)
        return {}, why


def answer(id_: str, verdict: str, note: str = "", p: Path | None = None, now: datetime | None = None) -> dict[str, Any]:
    """답 하나 — 먼저 검증(틀리면 ValueError · 아무것도 안 쓴다). 「다르다」 는 무엇이 다른지가 있어야 한다. 같은 답이면 다시 안 쓴다(멱등)."""
    it = item(id_)
    v = (verdict or "").strip()
    if v not in VERDICTS:
        raise ValueError(f"{it['id']}: 답은 {' / '.join(VERDICTS)} 중 하나여야 한다 — {verdict!r}")
    n = (note or "").strip()
    if v == "다르다" and len(n) < 2:
        raise ValueError(f"{it['id']}: 「다르다」 는 무엇이 다른지(→ 무엇)를 함께 적는다 — 빈 「다르다」 는 답이 아니다")
    p = p or local_path()
    doc = _read(p)
    prev = doc["answers"].get(it["id"])
    if prev and prev.get("verdict") == v and (prev.get("note") or "") == n:
        return prev
    rec = {"verdict": v, "note": n, "at": (now or datetime.now(timezone.utc)).isoformat(timespec="seconds")}
    doc["answers"][it["id"]] = rec
    _write(p, doc)
    return rec


def remove(id_: str, p: Path | None = None) -> dict[str, Any]:
    it = item(id_)
    p = p or local_path()
    doc = _read(p)
    if it["id"] not in doc["answers"]:
        raise ValueError(f"{it['id']}: 지울 답이 없다")
    gone = doc["answers"].pop(it["id"])
    _write(p, doc)
    return gone


def summary(answers: dict[str, dict[str, Any]]) -> dict[str, Any]:
    """답 수 · 모르겠다 목록(= P4 신호 — 갈래 판정을 사후에 교정하는 유일한 경로)."""
    mine = {k: v for k, v in answers.items() if k in IDS}
    counts = {v: sum(1 for a in mine.values() if a.get("verdict") == v) for v in VERDICTS}
    return {"answered": len(mine), "total": len(IDS), "counts": counts,
            "unknown_ids": [i for i in IDS if mine.get(i, {}).get("verdict") == UNKNOWN]}


def to_session_text(answers: dict[str, dict[str, Any]]) -> str:
    """세션에 붙일 한 덩어리 — 답한 것만 · 항목 순서 · 한 줄씩. 답이 PC 덮개에만 있어 세션은 이 글로만 안다."""
    lines = []
    for i in IDS:
        a = answers.get(i)
        if not a:
            continue
        line = f"{i} {a.get('verdict', '')}"
        if a.get("note"):
            line += f" — {a['note']}"
        lines.append(line)
    return "\n".join(lines)
