# -*- coding: utf-8 -*-
# FILE: scripts/build_grid_doc.py
# ROLE: data/grid/*.json(정본) → docs/grid_<id>.md(렌더). 문서를 손으로 고치지 않는다.
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from grid import schema  # noqa: E402

ROOT = Path(__file__).resolve().parent.parent
NA = schema.NA


def _lvl(v):
    return "—(미채움)" if v is None else ("해당없음" if v == NA else str(v))


def build(unit: dict) -> str:
    u = unit["unit"]
    rep = schema.validate(unit)
    out = [f"# 격자 — {u['crop']} × {u.get('season') or u.get('variety')} (정본: `data/grid/{u['id'].replace('-', '_')}.json`)\n"]
    out.append("**이 문서는 생성물이다.** 고치려면 JSON 을 고치고 `python scripts/build_grid_doc.py` 를 돌린다.\n")
    out.append(f"- 기준점: **{u['anchor_kind']}** (0일) · 작형 결정권: {u['kind']} · 출처: {u['source']} · 확신 {u.get('confidence', '—')}")
    out.append(f"- 검증: {'통과' if rep.ok else '실패 ' + str(rep.errors)} · 완성도: 값 {rep.filled} · 해당없음 {rep.na} · 미채움 {rep.unfilled}")
    if u.get("note"):
        out.append(f"- {u['note']}")
    vc = unit.get("variety_correction", {})
    out.append(f"- 품종 보정: 시간 이동 {_lvl(vc.get('time_shift_days'))} · 칸 덮어쓰기 {len(vc.get('cell_overrides', {}))}건 · {vc.get('note', '')}\n")
    out.append("## 회복 불가 위험 (경보: 오경보 감수)\n")
    out.append("| 단계 | 위험 | 트리거 | 축 |\n|---|---|---|---|")
    for s in unit["stages"]:
        for r in (s.get("risks") or []) if s.get("risks") != NA else []:
            if r.get("recoverable") is False:
                out.append(f"| {s['order']} {s['name']} | **{r['name']}** | {r.get('trigger', '')} | {' '.join(r.get('axes', []))} |")
    out.append("\n## 단계별 칸\n")
    for s in unit["stages"]:
        w = s.get("window")
        win = f"{w['from_day']}~{w['to_day']}일({w['basis']})" if isinstance(w, dict) else _lvl(w)
        out.append(f"### {s['order']}. {s['name']} — {win} · 확신 {s.get('confidence', '—')}\n")
        out.append(f"- 판정 축: {' '.join(s.get('required_axes', []) or []) if s.get('required_axes') != NA else '해당없음'} · "
                   f"금지 축: {' '.join(s.get('forbidden_axes', []) or []) if s.get('forbidden_axes') != NA else '해당없음'}")
        wt = s.get("water")
        if isinstance(wt, dict):
            out.append(f"- 수분: 요구 {wt['demand']} · 결핍 민감 {wt['deficit_sensitivity']} · 과습 민감 {wt['excess_sensitivity']}")
        else:
            out.append(f"- 수분: {_lvl(wt)}")
        out.append(f"- 품종 의존 {_lvl(s.get('variety_dependence'))} · 적용 단위 {_lvl(s.get('unit_scope'))} · 품종 미확인 시 {_lvl(s.get('judge_without_variety'))}")
        cap = s.get("capture")
        if isinstance(cap, dict):
            out.append(f"- 촬영: {'**찍는다** — ' + cap['scene'] if cap.get('shoot') else '안 찍음'}")
        out.append(f"- 결정: {', '.join(s.get('decisions', []) or []) or '—'}")
        risks = s.get("risks")
        if risks == NA:
            out.append("- 위험: 해당없음")
        elif risks:
            out.append("\n| 위험 | 회복 | 경보 | 축 | 필지 보정 | 출처 |\n|---|---|---|---|---|---|")
            for r in risks:
                rec = "가능" + (f"(마감 {r['deadline_day']}일)" if r.get("deadline_day") is not None else "") if r["recoverable"] else "**불가**"
                out.append(f"| {r['name']} | {rec} | {r['alert']} | {' '.join(r.get('axes', []))} | {'예' if r.get('parcel_correction') else '—'} | {r.get('source', '')} |")
        tasks = s.get("tasks")
        if tasks == NA:
            out.append("- 작업: 해당없음")
        elif tasks:
            out.append("\n| 작업 | 작업일 | 준비(자가/임대) | 도구 | 자재(관행) | 자재(유기) | 재시도 | 출처 |\n|---|---|---|---|---|---|---|---|")
            for t in tasks:
                m = t.get("materials")
                mk = "해당없음" if m == NA else " · ".join(m.get("관행", [])) or "—"
                mo = "해당없음" if m == NA else " · ".join(m.get("유기", [])) or "—"
                ld = t["lead_days"]
                rt = t["retry"]
                out.append(f"| {t['name']} | {t['work_day']} | {t['work_day'] - ld['own']}/{t['work_day'] - ld['rental']} | {' · '.join(t.get('tools', [])) or '—'} | {mk} | {mo} | "
                           f"{'가능 ~' + str(rt.get('deadline_day')) + '일' if rt['possible'] else '불가'} | {t.get('source', '')} |")
        out.append("")
    return "\n".join(out) + "\n"


if __name__ == "__main__":
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    for stem, unit in schema.load_all().items():
        p = ROOT / "docs" / f"grid_{stem}.md"
        p.write_text(build(unit), encoding="utf-8")
        print("written", p)
