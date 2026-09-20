# -*- coding: utf-8 -*-
# FILE: ingest/parcels.py
# ROLE: [M-6 · I-3 §1 · I-6] 필지 등록부 — 필지 고정 정보의 자리. 주소·PNU·좌표는 여기 있고 화면·봉투·몰에는 안 나간다(I-5 §1-2).
#       값이 없으면 키가 없다(대리값 금지). 3층에는 PARCEL_FIELDS_TO_LAYER3 만 붙여 준다.
from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from schema import records as sch

ROOT = Path(__file__).resolve().parent.parent
PARCELS_PATH = ROOT / "data" / "parcels.json"


# [U-18 · 발행자 2026-09-20 "저장소 안 필지 주소는 오늘이다"] 원격이 **공개** 저장소(실측 visibility=public)인데 등록부 파일이 git 추적이라
# 지번 주소가 밖에 있었다. 그리고 런타임 기록(지오코딩 좌표 · PNU · 되물은 재배환경)이 그 추적 파일에 써져 발행자 PC 의 pull 이 충돌할 형태였다.
# 이제 등록부는 두 겹이다 — 추적 파일(data/parcels.json)은 PII 없는 **씨앗**, 이 PC 의 값(주소 · PNU · 좌표 · 런타임 기록 전부)은
# gitignore 된 **덮개**(data/parcels_local.json)에만. 읽을 때 덮개가 씨앗을 덮고, 쓸 때는 덮개에만 쓴다. 씨앗은 사람이 커밋으로만 고친다.
LOCAL_PATH = ROOT / "data" / "parcels_local.json"
SEED_PATH = ROOT / "data" / "parcels_seed.json"
PRIVATE_FIELDS = ("address", "pnu", "lat", "lon")     # 씨앗에 있으면 안 되는 필드 — ensure_local 이 덮개로 옮긴다
# 옛 추적 파일(data/parcels.json)은 여기서 **읽기만** 한다(덮개가 없을 때 이주 원천). 실측(2026-09-20): 로컬에서 수정된 추적 파일은
# upstream 이 지우거나 고치면 pull 이 "commit or stash" 로 멈춘다 — 발행자 PC 의 등록부는 2회차가 좌표를 써 넣어 수정돼 있을 수 있다.
# 그래서 이 파일은 코드가 갈아탄 뒤(덮개가 생긴 뒤) 별도 커밋으로 git 에서 뺀다. 그때까지 upstream 은 이 경로를 건드리지 않는다.


def parcels_path() -> Path:
    """씨앗(추적 파일 · PII 없음). [R-4 · 코드 평가 C4] 경로는 호출 시점에 env 로 푼다 — 기본 인자에 묶으면 conftest 격리가 안 닿는다."""
    return Path(os.environ.get("AGRODSS_PARCELS_PATH") or SEED_PATH)


def local_path() -> Path:
    return Path(os.environ.get("AGRODSS_PARCELS_LOCAL_PATH") or LOCAL_PATH)


def legacy_path() -> Path:
    return Path(os.environ.get("AGRODSS_PARCELS_LEGACY_PATH") or PARCELS_PATH)


def _read(p: Path) -> list[dict[str, Any]]:
    if not p.exists():
        return []
    return list(json.loads(p.read_text(encoding="utf-8")).get("parcels", []))


def _backfill_local(lp: Path) -> Path:
    """덮개에 **빠진** 값만 옛 파일에서 채운다. 있는 값은 건드리지 않고, 채울 것이 없으면 파일도 안 쓴다.

    무엇을 옮기는지는 `ensure_local` 과 **같은 규칙**이다 — PII 필드와 *씨앗에 없는* 런타임 기록만. 첫 판은 옛 파일의
    모든 키를 옮겨 `source` · `recorded_at` 같은 장부 필드까지 덮개로 끌어왔고, 그래서 기동마다 덮개를 다시 썼다
    (직접 쓴 검사가 잡았다). 규칙이 두 벌이면 어긋난다 — 한 벌로 둔다.
    """
    legacy = {r.get("id"): r for r in _read(legacy_path())}
    if not legacy:
        return lp
    seed = {r.get("id"): r for r in _read(parcels_path())}
    doc = json.loads(lp.read_text(encoding="utf-8")) if lp.exists() else {"parcels": []}
    rows = doc.get("parcels") or []
    by_id = {r.get("id"): r for r in rows}
    added = 0
    for pid, lg in legacy.items():
        cur, s = by_id.get(pid), seed.get(pid, {})
        if cur is None:
            cur = {"id": pid}
            rows.append(cur)
            by_id[pid] = cur
        for k, v in lg.items():
            if k == "id" or v is None or k in cur:
                continue                       # 덮개에 이미 있으면 그것이 이긴다 — 덧붙이기만 한다
            if k not in PRIVATE_FIELDS and k in s:
                continue                       # 씨앗에 있는 값은 씨앗이 정본 — 덮개로 끌어오지 않는다(ensure_local 과 같은 규칙)
            cur[k] = v
            added += 1
    if not added:
        return lp
    doc["parcels"] = rows
    lp.write_text(json.dumps(doc, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return lp


def ensure_local() -> Path:
    """씨앗(추적 파일)에 PII 필드가 남아 있고 덮개가 없으면 덮개를 만들어 옮겨 둔다 — 발행자 PC 에서 pull 뒤 첫 기동에 자동으로 일어난다.
    씨앗은 여기서 건드리지 않는다(추적 파일 쓰기 금지 — 씨앗에서 PII 를 빼는 것은 커밋으로).

    [복구 절차 미리 걷기 2026-09-21] 덮개가 있으면 그냥 돌아가던 것이 **순서 함정**이었다. 발행자 PC 의 실제 복구는
    ① 옛 파일 사본 ② 추적 파일 되돌리기(pull 이 지나가게) ③ pull ④ 사본 제자리 인데, ③ 과 ④ 사이에 서버가 뜨면
    (HEAD 가 바뀌면 스스로 다시 뜬다) 덮개가 **좌표 없는 커밋본으로** 만들어지고, 그 뒤 사본을 되돌려도 이주가 다시
    일어나지 않는다. 실측: 좌표·PNU 는 커밋된 적이 없는 런타임 값이라 그대로 **사라진다**.
    그래서 덮개가 있어도 **옛 파일에만 있는 값은 채워 넣는다** — 덧붙이기만 하고 덮개의 기존 값은 절대 안 건드린다
    (되돌릴 수 있는 쪽 · 값을 잃지 않는 쪽). 순서를 사람이 지켜야 하는 절차는 언젠가 어긋난다.
    """
    lp = local_path()
    if lp.exists():
        return _backfill_local(lp)
    seed = {r.get("id"): r for r in _read(parcels_path())}
    legacy = {r.get("id"): r for r in _read(legacy_path())}       # 옛 추적 파일 — 발행자 PC 에는 런타임이 써 넣은 좌표·PNU 도 여기 있다
    moved: list[dict[str, Any]] = []
    for pid in list(seed) + [k for k in legacy if k not in seed]:
        s, lg = seed.get(pid, {}), legacy.get(pid, {})
        priv = {k: lg[k] for k in PRIVATE_FIELDS if k in lg}
        priv.update({k: s[k] for k in PRIVATE_FIELDS if k in s})
        extra = {k: v for k, v in lg.items() if k not in s and k not in PRIVATE_FIELDS and k != "id"}   # 옛 파일에만 있는 런타임 기록
        if priv or extra:
            moved.append({"id": pid, **priv, **extra})
    lp.parent.mkdir(parents=True, exist_ok=True)
    lp.write_text(json.dumps({"_note": "이 PC 의 필지 값(PII · 런타임 기록) — git 밖. 씨앗은 data/parcels.json", "parcels": moved},
                             ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return lp


def load(path: Path | None = None) -> list[dict[str, Any]]:
    """씨앗 + 덮개(같은 id 는 덮개 값이 이긴다). path 를 주면 그 파일 하나만(옛 호출 호환)."""
    if path is not None:
        return [sch.validate(r, kind="parcel") for r in _read(path)]
    rows = _read(parcels_path())
    over = {r.get("id"): r for r in _read(local_path())}
    out = []
    for r in rows:
        merged = {**r, **{k: v for k, v in over.get(r.get("id"), {}).items() if k != "id"}}
        merged = {k: v for k, v in merged.items() if v is not None}   # 덮개의 None = 그 키 없음(대리값 금지 — 키를 두지 않는다)
        out.append(sch.validate(merged, kind="parcel"))
    return out


def by_id(pid: str, path: Path | None = None) -> dict[str, Any] | None:
    for r in load(path):
        if r.get("id") == pid:
            return r
    return None


def public_view(rec: dict[str, Any]) -> dict[str, Any]:
    """화면용 — PII 를 뺀다(정본 sch.strip_pii · kind 가 선언한 pii). 있음/없음만 남긴다."""
    out = sch.strip_pii({**rec, "kind": rec.get("kind") or "parcel"})
    out["location"] = "있음" if any(rec.get(k) is not None for k in ("address", "pnu", "lat", "lon")) else "없음"
    return out


def enrich_subject(subject: dict[str, Any], parcel: dict[str, Any] | None) -> dict[str, Any]:
    """재배 단위에 필지의 3층 허용 필드만 붙인다. 주소·PNU 는 붙지 않는다. 없는 값은 안 붙는다."""
    s = dict(subject)
    if not parcel:
        return s
    for k in sch.PARCEL_FIELDS_TO_LAYER3:
        if k in parcel and k not in s:
            s[k] = parcel[k]
    return s


def missing_inputs(parcel: dict[str, Any] | None) -> list[str]:
    """I-6 입력 대기 — 필지 레코드에 아직 없는 키(화면에 '입력 대기'로)."""
    want = ("lat", "lon", "area_m2", "use", "environment", "soil_texture", "slope", "drainage", "irrigation",
            "microclimate", "night_light", "cert_legal", "seed_source", "soil_exam_ref")
    have = set(parcel or {})
    return [k for k in want if k not in have]


# [발행자 2026-09-21 "필지 3문항과 토성·경사가 비어 있다 — 나가서 보면 답이 나오는 것들"] 밭에서 받아 온 답이 들어갈 자리를
# 화면에 만들면서, 고를 말(어휘)을 **여기 한 곳**에 둔다. 화면과 CLI 가 각자 목록을 들면 두 벌이 되고 어긋난다
# (재배환경이 그럴 뻔했다 — ingest.fertilizer.ENVIRONMENTS 가 먼저 있었고, 이제 그것이 이 정본을 가리킨다).
FIELD_CHOICES: dict[str, tuple[str, ...]] = {
    "environment": ("노지", "시설"),          # 작물코드가 갈린다(fertilizer.CROP_CODES) — 이 어휘는 API 코드표와 맞물려 있다
    "soil_texture": ("사토", "사양토", "양토", "식양토", "식토"),
    "slope": ("평지", "완경사", "급경사"),
    "drainage": ("좋음", "보통", "나쁨"),
    "irrigation": ("없음", "점적", "스프링클러", "관수 호스", "수동"),
    "night_light": ("없음", "약함", "강함"),
}
FIELD_LABELS: tuple[tuple[str, str], ...] = (        # 고르는 것이 아니라 적는 값 — 순서가 화면 순서다
    ("area_m2", "면적(㎡ — 지적 면적이나 걸음 측정)"),
    ("use", "용도(자가 · 판매 · 몰 납품)"),
    ("microclimate", "미기상 3문항 — 주변 개방도 · 안개 빈도 · 바람길(본 대로 짧게)"),
    ("seed_source", "종구 출처"),
    ("cert_legal", "인증 근거(인증서 번호 · 기관)"),
)
NUMERIC_FIELDS = ("area_m2",)

# [G1 전수 2026-09-21 — 처방 직후 그 자리에서 셌다] 입력 자리를 만들면서 **그 값을 읽는 쪽**을 전수로 셌다. 입력 대기 필드 중
# 판정·수집이 실제로 값을 읽는 것은 **둘뿐**이다. 나머지는 등록부에 쌓이기만 한다 — 값이 흐르는데 소비자가 없는 G1 형태.
#
#   use          judge.stage_decisions.judge_ship_or_store  — '자가 · 시험' 이면 해당 없음(D-8)
#   environment  ingest.fertilizer.crop_code                — 노지/시설로 작물코드가 갈린다
#   microclimate **선언만 있다** — 격자 칸 3 required_axes 와 pest_alert optional_axes 에 이름이 있고
#                docs/i4_axes_minimal.md 는 "병해충 칸 필지 보정 ②" 라고 적었는데, 값을 읽는 코드가 없다(실측 소비자 0).
#   soil_texture · slope · drainage · irrigation · night_light · area_m2 · seed_source · cert_legal · soil_exam_ref  소비자 0
#
# 그래서 화면은 이 사실을 **말한다** — "채우면 판정이 열린다" 고 하면 밭에 헛걸음을 시킨다(조건 없는 안내는 다른 사실이다).
# 보정 규칙 자체는 여기서 짓지 않는다: 임계가 정본에 미채움이고(격자 '고자리파리 유충' = NCPMS 대조 대기 · M-15 ②)
# 없는 임계를 지어내는 것이 대리값이다. 대장에 등재하고 정본이 도착하면 잇는다.
FIELDS_READ_BY_JUDGMENT = ("use", "environment")


class ParcelError(ValueError):
    pass


def check_vocab(key: str, value: Any) -> Any:
    """어휘가 선언된 필드면 그 어휘 안인지 본다. 숫자 필드는 숫자로 바꾼다(빈 값은 여기 오지 않는다 — 호출부가 거른다).

    [§7.5 관문의 입력] 어휘 검사가 fertilizer 쪽에만 있었다(재배환경). 화면이 생기면서 두 번째 입력 경로가 열리므로
    검사를 **값이 등록부에 닿는 자리**(set_fields)로 내린다 — 경로가 늘어도 같은 관문을 지난다.
    """
    if key in NUMERIC_FIELDS:
        try:
            n = float(value)
        except (TypeError, ValueError):
            raise ParcelError(f"{key} 는 숫자여야 한다: {value!r}") from None
        if n <= 0:
            raise ParcelError(f"{key} 는 0 보다 커야 한다: {value!r}")
        return int(n) if n.is_integer() else n
    opts = FIELD_CHOICES.get(key)
    if opts and value not in opts:
        raise ParcelError(f"{key} 어휘 밖: {value!r} — {' | '.join(opts)}")
    return value


def set_fields(pid: str, **fields: Any) -> dict[str, Any]:
    """[I-6 · 발행자 라이브 2026-09-19 21:34] 필지 등록부에 값을 넣는다 — 지오코딩이 얻은 좌표·PNU, 되물은 재배환경.
    스키마(kind=parcel)가 허용하는 필드만, 값이 None 이면 키를 지운다(대리값 금지). 이미 있는 값은 덮지 않는다(overwrite=True 로만)."""
    overwrite = bool(fields.pop("overwrite", False))
    rec = by_id(pid)                                          # 씨앗 + 덮개가 합쳐진 현재 값
    if rec is None:
        raise ParcelError(f"없는 필지: {pid}")
    allowed = sch.KINDS["parcel"].fields
    lp = ensure_local()
    data = json.loads(lp.read_text(encoding="utf-8"))
    rows = data.setdefault("parcels", [])
    over = next((r for r in rows if r.get("id") == pid), None)
    if over is None:
        over = {"id": pid}
        rows.append(over)
    for k, v in fields.items():
        if k not in allowed:
            raise ParcelError(f"필지 등록부에 없는 필드: {k}")
        if v is None:
            over[k] = None                                    # 덮개의 None = 씨앗 값도 가린다(키 삭제와 같은 뜻)
        elif k not in rec or rec.get(k) is None or overwrite:
            over[k] = check_vocab(k, v)                       # 어휘·형 관문은 여기 하나 — 화면이든 CLI 든 같은 자리를 지난다
    merged = {**rec, **{k: v for k, v in over.items() if k != "id"}}
    merged = {k: v for k, v in merged.items() if v is not None}
    sch.validate(merged, kind="parcel")
    lp.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")   # 추적 파일(씨앗)에는 쓰지 않는다
    return merged
