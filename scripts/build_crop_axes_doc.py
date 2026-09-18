# -*- coding: utf-8 -*-
# FILE: scripts/build_crop_axes_doc.py
# ROLE: data/crop_axes.csv(정본) → docs/crop_axes.md(렌더). 정본은 CSV 하나다 — 문서를 손으로 고치지 않는다.
#       tests/test_crop_axes.py 가 "문서가 정본과 같은가"를 래칫으로 본다.
from __future__ import annotations

import collections
import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CSV_PATH = ROOT / "data" / "crop_axes.csv"
DOC_PATH = ROOT / "docs" / "crop_axes.md"

AXES = ["범위", "생애주기", "수확형태", "재배환경", "번식방식", "품종의존", "수확단위", "품종불명",
        "저장성", "수분구조", "품종다양성", "확신"]


def load_rows(path: Path = CSV_PATH) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as f:
        return list(csv.DictReader(f))


def dist(rows: list[dict[str, str]], key: str) -> str:
    c = collections.Counter(r[key] for r in rows)
    return " · ".join(f"{k} {n}" for k, n in c.most_common())


def build(rows: list[dict[str, str]]) -> str:
    crops = [r for r in rows if r["범위"] == "작목"]
    out: list[str] = []
    out.append("# 작목 분류 마킹 — VELA 등록 작목 전수 (정본: `data/crop_axes.csv`)\n")
    out.append("**이 문서는 생성물이다.** 고치려면 CSV 를 고치고 `python scripts/build_crop_axes_doc.py` 를 돌린다.\n")
    out.append("**값은 전부 추론이다**(2026-09-18, 발행자 검토 대기). 작목마다 `확신` 열이 있다 — `하` 는 특히 검토 대상.\n")
    out.append("## 축 정의 (발행자 기준 ①~⑥ + 트리 C 범위)\n")
    out.append("| 축 | 값 | 뜻 |\n|---|---|---|")
    out.append("| 범위 | 작목 · 버섯 · 채취·부산물 · 관상 | 격자 대상인가. 버섯은 별도 구조(트리 C), 채취·부산물·관상은 격자 대상 아님 |")
    out.append("| ① 생애주기 | 일년생 · 다년생초본 · 목본 · 해당없음 | 관리 방식과 되먹임 주기의 기본 축. '재배상 일년생'은 일년생 |")
    out.append("| ② 수확형태 | 일시 · 연속 · 혼합 · 해당없음 | '수확 적기' 개념 성립 여부. 혼합 = 용도·유형에 따라 갈림 |")
    out.append("| ③ 재배환경 | 노지 · 시설 · 양쪽 | **주류 관행**만 — 실제는 필지 속성(트리 C)이라 필지 정보가 우선 |")
    out.append("| ④ 번식방식 | 직파 · 육묘정식 · 영양번식 (`+` 로 병기, 앞이 주류) | 초기 단계 관리 구조 |")
    out.append("| ⑤ 품종의존 | 시간축 · 성질까지 · 미상 | 품종 보정이 시간 이동만인지 칸 덮어쓰기까지인지(트리 D 보정 2종) |")
    out.append("| ⑤ 수확단위 | 필지 · 품종 · 해당없음 | 수확·출하 판단이 필지 단위인지 품종 단위인지 |")
    out.append("| ⑤ 품종불명 | 영향미미 · 범위제시 · 판단불가 · 미상 | 품종을 모를 때 판단 가능한가 |")
    out.append("| ⑥ 저장성 | 낮음 · 중간 · 높음 · 해당없음 | 저장 가능 기간 — 몰-B 예약·출하 창 |")
    out.append("| ⑥ 수분구조 | 자가 · 타가 · 부분자가 · 해당없음 | 해당없음 = 영양기관 수확(잎·뿌리)이라 수분이 수확에 무관 |")
    out.append("| ⑥ 품종다양성 | 낮음 · 중간 · 높음 · 해당없음 | 품종별로 수확기·성질이 크게 갈리는가 |")
    out.append("| 확신 | 상 · 중 · 하 | 마킹한 쪽의 확신도 — 검토 우선순위 |\n")
    out.append("## 분포\n")
    out.append(f"- 전체 {len(rows)} · 범위: {dist(rows, '범위')}")
    for ax in AXES[1:-1]:
        out.append(f"- {ax} (작목 {len(crops)}만): {dist(crops, ax)}")
    out.append(f"- 확신 (전체): {dist(rows, '확신')}\n")
    dups = [r for r in rows if "같은 종" in r["비고"] or "중복 등재" in r["비고"]]
    out.append("## 목록 성격 (M-7 확인 사항)\n")
    out.append(f"- 같은 종이 두 번 등재된 것 {len(dups)}건 — 비고에 '같은 종' 표시. 농산물/임산물 양쪽 등재가 원인.")
    out.append("- 트리가 말한 '180종'은 실제 202종이고, 격자 대상(작목)은 " + str(len(crops)) + "종.")
    out.append("- 버섯 12 중 채취만 가능한 것 4(능이·석이·송이·싸리). 나머지 8이 트리 C 별도 구조의 대상.")
    out.append("- 축이 늘지 않았다 — 202종을 훑어도 ①~⑥ 밖의 축은 필요하지 않았다(U-6 축 수렴의 방증).\n")
    out.append("## 전수 표\n")
    cols = ["작목", "VELA분류"] + AXES + ["비고"]
    out.append("| " + " | ".join(cols) + " |")
    out.append("|" + "---|" * len(cols))
    for r in rows:
        out.append("| " + " | ".join(r[c].replace("|", "/") for c in cols) + " |")
    return "\n".join(out) + "\n"


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    rows = load_rows()
    DOC_PATH.write_text(build(rows), encoding="utf-8")
    print(f"written {DOC_PATH} ({len(rows)} rows)")
