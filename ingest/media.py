# -*- coding: utf-8 -*-
# FILE: ingest/media.py
# ROLE: [I-7 · 몰-C · I-3 §3] 현장 영상 반입 — inbox 의 파일을 1층 관찰(영상) 레코드로 등록한다.
#
# 규칙:
#   · 1층 3요건(관측 시각 · 출처 · 해상도). 찍은 때는 **사다리**로 정하고 어디서 얻었는지를 함께 적는다 —
#     사람이 적은 날짜 → 메타(EXIF · mvhd) → 파일 이름 → 올린 때(`observed_ladder`).
#     [발행자 2026-09-23] 전에는 앞 둘이 없으면 **거부**했다. 카카오톡이 EXIF 를 지우므로 밭 사진이 언제나
#     거절당했다 — 규칙이 옳아도 아무도 통과 못 하면 기능을 없앤 것이다. 지어내지 않되 거절도 하지 않는다:
#     마지막 칸은 *"언제 찍었는지는 모르고 이때 받았다"* 는 **참인 사실**이고, 화면이 그렇게 말한다.
#   · 파일은 git 에 넣지 않는다(data/media/ 는 .gitignore). 레코드는 index.jsonl(원장)에 append.
#   · 원장 격리: 경로는 AGRODSS_MEDIA_DIR 로 바꿀 수 있다 — 테스트는 tmp 를 쓴다(conftest).
#   · 위치(GPS)는 있으면 레코드에 두되 화면에는 '있음/없음'만 낸다(PII, I-5 §1-2).
#   · 판단하지 않는다 — 영상에서 무엇이 보이는지는 2층(추정)이고 여기 없다.
from __future__ import annotations

import hashlib
import json
import os
import re
import shutil
import struct
from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Iterator

from schema import records as sch

ROOT = Path(__file__).resolve().parent.parent
SUBJECTS_PATH = ROOT / "data" / "subjects.json"
VIDEO_EXT = {".mp4", ".mov", ".m4v", ".3gp"}
IMAGE_EXT = {".jpg", ".jpeg", ".png", ".webp", ".heic"}     # [M-13 2026-09-19] 채팅 입력창 사진 반입 — 촬영 시각은 EXIF(JPEG)에서
MEDIA_EXT = VIDEO_EXT | IMAGE_EXT
SOURCE = "farmer"
RESOLUTION = "parcel"
KIND = "observation.video"
KIND_IMAGE = "observation.image"
_QT_EPOCH = datetime(1904, 1, 1, tzinfo=timezone.utc)
_CONTAINERS = {b"moov", b"trak", b"mdia", b"udta", b"meta", b"ilst"}


def media_dir() -> Path:
    return Path(os.environ.get("AGRODSS_MEDIA_DIR") or (ROOT / "data" / "media"))


def inbox_dir() -> Path:
    return media_dir() / "inbox"


def index_path() -> Path:
    return media_dir() / "index.jsonl"


def seen_path() -> Path:
    return media_dir() / "seen.json"


def watch_dirs() -> list[Path]:
    """[동기화 — 발행자 2026-09-18] 휴대폰 카메라 폴더가 PC 로 동기화되는 폴더들(OneDrive · 구글 드라이브 ·
    iCloud 사진 · Syncthing). 앱은 이 폴더를 **읽기만** 하고 등록 시 **복사**한다 — 옮기면 폰에서도 지워진다.
    AGRODSS_WATCH_DIRS = "C:\\Users\\me\\OneDrive\\사진\\카메라 앨범;D:\\sync\\phone"  (; 구분)"""
    raw = os.environ.get("AGRODSS_WATCH_DIRS", "")
    out = []
    for part in raw.split(";"):
        part = part.strip().strip('"')
        if part:
            out.append(Path(part))
    return out


WATCH_LIST_LIMIT = 50


# ── 재배 단위(subject) 등록부 ────────────────────────────────────────────────────
def subjects_path() -> Path:
    """등록부 경로 — AGRODSS_SUBJECTS_PATH 로 바꿀 수 있다(테스트는 tmp 사본 — conftest). 호출 시점에 푼다(기본 인자에 묶지 않는다)."""
    return Path(os.environ.get("AGRODSS_SUBJECTS_PATH") or SUBJECTS_PATH)


def load_subjects(path: Path | None = None) -> list[dict[str, Any]]:
    path = path or subjects_path()
    if not path.exists():
        return []
    return [sch.validate(s, kind="subject") for s in json.loads(path.read_text(encoding="utf-8")).get("subjects", [])]


def subject_ids() -> set[str]:
    return {s["id"] for s in load_subjects()}


# ── MP4/MOV 메타 (표준 라이브러리, 앞부분만 읽는다) ─────────────────────────────────
@dataclass
class Probe:
    creation_time: str | None = None   # ISO 8601 UTC — mvhd. 0 이면 None
    width: int | None = None
    height: int | None = None
    duration_sec: float | None = None
    gps: tuple[float, float] | None = None
    error: str | None = None


def _atoms(buf: bytes, start: int, end: int) -> Iterator[tuple[bytes, int, int]]:
    """(type, payload_start, payload_end) — buf[start:end] 안의 형제 아톰."""
    pos = start
    while pos + 8 <= end:
        size, typ = struct.unpack(">I4s", buf[pos:pos + 8])
        hdr = 8
        if size == 1:
            if pos + 16 > end:
                return
            size = struct.unpack(">Q", buf[pos + 8:pos + 16])[0]
            hdr = 16
        elif size == 0:
            size = end - pos
        if size < hdr:
            return
        yield typ, pos + hdr, min(pos + size, end)
        pos += size


def _walk(buf: bytes, start: int, end: int, found: dict[bytes, list[tuple[int, int]]]) -> None:
    for typ, a, b in _atoms(buf, start, end):
        found.setdefault(typ, []).append((a, b))
        if typ in _CONTAINERS:
            inner = a + 4 if typ == b"meta" else a   # ISO 'meta' 는 version/flags 4바이트가 앞에 온다
            _walk(buf, inner, b, found)


_ISO6709 = re.compile(r"([+-]\d+(?:\.\d+)?)([+-]\d+(?:\.\d+)?)")


def probe_mp4(path: Path, max_bytes: int = 64 * 1024 * 1024) -> Probe:
    """moov 가 앞에 있는 파일(휴대폰 기본)은 첫 64MB 안에서 읽힌다. 뒤에 있으면 못 읽고 error 로 남긴다."""
    p = Probe()
    try:
        with path.open("rb") as f:
            buf = f.read(max_bytes)
    except OSError as e:
        p.error = f"읽기 실패: {e}"
        return p
    found: dict[bytes, list[tuple[int, int]]] = {}
    try:
        _walk(buf, 0, len(buf), found)
    except (struct.error, ValueError) as e:
        p.error = f"아톰 파싱 실패: {e}"
        return p
    if b"moov" not in found:
        p.error = "moov 없음(파일 뒤쪽에 있을 수 있음) — 촬영 시각·해상도 자동 판독 불가"
        return p
    # [코드 평가 C9] 잘린 mvhd/tkhd 페이로드 — buf[a] IndexError 가 try 밖이라 파일 하나가 list_inbox 전체(/media 화면)를 죽였다
    try:
        for a, b in found.get(b"mvhd", []):
            v = buf[a]
            if v == 1:
                ct, _mt, ts, du = struct.unpack(">QQIQ", buf[a + 4:a + 32])
            else:
                ct, _mt, ts, du = struct.unpack(">IIII", buf[a + 4:a + 20])
            if ct:
                p.creation_time = (_QT_EPOCH + timedelta(seconds=ct)).isoformat(timespec="seconds")
            if ts:
                p.duration_sec = round(du / ts, 2)
            break
        for a, b in found.get(b"tkhd", []):
            v = buf[a]
            off = a + (96 if v == 1 else 84)
            if off + 8 <= b:
                w, h = struct.unpack(">II", buf[off:off + 8])
                w, h = w >> 16, h >> 16
                if w and h:
                    p.width, p.height = w, h
                    break
    except (IndexError, struct.error, ZeroDivisionError) as e:
        p.error = f"mvhd/tkhd 판독 실패(잘린 페이로드): {type(e).__name__}"
        return p
    for key in (b"\xa9xyz", b"loci"):
        for a, b in found.get(key, []):
            text = buf[a:b].decode("latin-1", errors="ignore")
            m = _ISO6709.search(text)
            if m:
                p.gps = (float(m.group(1)), float(m.group(2)))
                break
        if p.gps:
            break
    return p


_EXIF_TAGS = {0x9003: "DateTimeOriginal", 0x0132: "DateTime"}


def probe_image(path: Path) -> Probe:
    """JPEG EXIF 에서 촬영 시각(DateTimeOriginal)만 읽는다 — 표준 라이브러리로 TIFF IFD 를 걷는다. 없으면 None(메우지 않는다).
    PNG·WEBP·HEIC 는 시각을 안 읽는다(입력 필요)."""
    p = Probe()
    try:
        with path.open("rb") as f:
            buf = f.read(1 << 20)
    except OSError as e:
        p.error = str(e)
        return p
    if buf[:2] != b"\xff\xd8":
        p.error = "JPEG 아님 — 촬영 시각 자동 판독 불가(입력 필요)"
        return p
    i = 2
    while i + 4 <= len(buf) and buf[i] == 0xFF:
        marker, seg_len = buf[i + 1], struct.unpack(">H", buf[i + 2:i + 4])[0]
        if marker == 0xE1 and buf[i + 4:i + 10] == b"Exif\x00\x00":
            tiff = i + 10
            endian = "<" if buf[tiff:tiff + 2] == b"II" else ">"
            found: dict[str, str] = {}

            def walk(ifd_off: int, depth: int = 0) -> None:
                if depth > 2 or tiff + ifd_off + 2 > len(buf):
                    return
                n = struct.unpack(endian + "H", buf[tiff + ifd_off:tiff + ifd_off + 2])[0]
                for k in range(min(n, 200)):
                    e = tiff + ifd_off + 2 + 12 * k
                    if e + 12 > len(buf):
                        return
                    tag, typ, cnt, val = struct.unpack(endian + "HHII", buf[e:e + 12])
                    if tag == 0x8769:                      # Exif IFD 포인터
                        walk(val, depth + 1)
                    elif tag in _EXIF_TAGS and typ == 2 and cnt >= 19:
                        s = buf[tiff + val:tiff + val + cnt].split(b"\x00")[0].decode("ascii", errors="ignore")
                        found[_EXIF_TAGS[tag]] = s

            first = struct.unpack(endian + "I", buf[tiff + 4:tiff + 8])[0]
            walk(first)
            raw = found.get("DateTimeOriginal") or found.get("DateTime")
            if raw and len(raw) >= 19:
                try:
                    p.creation_time = datetime.strptime(raw[:19], "%Y:%m:%d %H:%M:%S").isoformat(timespec="seconds")
                except ValueError:
                    p.error = f"EXIF 시각 형식 아님: {raw!r}"
            break
        i += 2 + seg_len
    if not p.creation_time and not p.error:
        p.error = "EXIF 촬영 시각 없음 — 입력 필요"
    return p


def probe(path: Path) -> Probe:
    return probe_image(path) if path.suffix.lower() in IMAGE_EXT else probe_mp4(path)


def save_upload(filename: str, data: bytes) -> str:
    """[M-13 채팅 반입] 업로드된 바이트를 inbox 에 둔다 → 'inbox:<name>' 키. 등록(register)은 따로 — 시각 없으면 거기서 거부된다."""
    name = _safe(Path(filename or "upload").name)
    ext = Path(name).suffix.lower()
    if ext not in MEDIA_EXT:
        raise RegisterError(f"영상·사진 파일이 아니다: {ext!r} ({', '.join(sorted(MEDIA_EXT))})")
    if not data:
        raise RegisterError("빈 파일")
    d = inbox_dir()
    d.mkdir(parents=True, exist_ok=True)
    dest = d / name
    k = 1
    while dest.exists():
        dest = d / f"{Path(name).stem}_{k}{ext}"
        k += 1
    dest.write_bytes(data)
    return f"inbox:{dest.name}"


def sha256_of(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


# ── 원장 ──────────────────────────────────────────────────────────────────────────
def list_records(subject: str | None = None) -> list[dict[str, Any]]:
    p = index_path()
    if not p.exists():
        return []
    out = []
    for line in p.read_text(encoding="utf-8").splitlines():
        if line.strip():
            r = json.loads(line)
            if subject is None or r.get("subject") == subject:
                out.append(r)
    return out


class RegisterError(ValueError):
    pass


def _load_seen() -> dict[str, str]:
    p = seen_path()
    if not p.exists():
        return {}
    try:
        return json.loads(p.read_text(encoding="utf-8"))
    except ValueError:
        return {}


def _mark_seen(key: str, digest: str) -> None:
    seen = _load_seen()
    seen[key] = digest
    seen_path().parent.mkdir(parents=True, exist_ok=True)
    seen_path().write_text(json.dumps(seen, ensure_ascii=False, indent=0), encoding="utf-8")


def _fingerprint(f: Path) -> str:
    st = f.stat()
    return f"{f.name}|{st.st_size}|{int(st.st_mtime)}"


def _candidates() -> list[tuple[str, str, Path]]:
    """(key, origin, path). key = 'inbox:<name>' | 'watch:<i>:<name>'. 등록된 것(seen)은 뺀다."""
    seen = _load_seen()
    out: list[tuple[str, str, Path]] = []
    d = inbox_dir()
    d.mkdir(parents=True, exist_ok=True)
    for f in sorted(d.iterdir()):
        if f.is_file() and f.suffix.lower() in MEDIA_EXT:
            out.append((f"inbox:{f.name}", "inbox", f))
    for i, w in enumerate(watch_dirs()):
        if not w.is_dir():
            continue
        files = [f for f in w.iterdir() if f.is_file() and f.suffix.lower() in MEDIA_EXT]
        files.sort(key=lambda f: f.stat().st_mtime, reverse=True)
        for f in files[:WATCH_LIST_LIMIT]:
            key = f"watch:{i}:{f.name}"
            if seen.get(key) == _fingerprint(f) or seen.get(_fingerprint(f)):
                continue
            out.append((key, str(w), f))
    return out


def _resolve_key(key: str) -> tuple[str, Path]:
    if "/" in key or "\\" in key or ".." in key:
        raise RegisterError(f"잘못된 키: {key!r}")
    if key.startswith("inbox:"):
        return "inbox", inbox_dir() / key[len("inbox:"):]
    if key.startswith("watch:"):
        _, idx, name = key.split(":", 2)
        dirs = watch_dirs()
        try:
            w = dirs[int(idx)]
        except (ValueError, IndexError):
            raise RegisterError(f"감시 폴더 번호가 없다: {key!r}")
        return "watch", w / name
    # 키 접두가 없으면 inbox 파일명으로 본다(하위 호환)
    return "inbox", inbox_dir() / key


def list_inbox() -> list[dict[str, Any]]:
    items = []
    for key, origin, f in _candidates():
        pr = probe(f)
        items.append({"key": key, "name": f.name, "origin": origin, "bytes": f.stat().st_size, "probe": asdict(pr)})
    return items


def _safe(s: str) -> str:
    return re.sub(r"[^0-9A-Za-z가-힣._-]+", "_", s)[:80]


# ── 찍은 때를 정하는 사다리 ────────────────────────────────────────────────────────────
# [발행자 실사용 2026-09-23] 카카오톡으로 받은 사진 넉 장이 전부 거절당했다:
#   "촬영 시각이 없다 — 메타에서 못 읽었고 입력도 없다. 시각 없는 영상은 1층에 들어가지 않는다"
# 발행자: *"이 방법은 농업인들에게 **무리한 요구**다. 올린 날과 그 시각을 활용해야 한다."* ·
#         *"`KakaoTalk_20260923_074025068_04` 여기에 **07:40분임을 알 수도 있다**."*
#
# 맞다. 카카오톡·메신저는 EXIF 를 지운다 — 그러면 밭에서 찍은 사진은 **언제나** 거절당한다. 규칙이 옳아도
# 아무도 통과 못 하면 그 규칙은 기능을 없앤 것이다. 그런데 **아무 시각이나 지어내는 것**(대리값)도 안 된다.
#
# 그래서 사다리로 만든다 — **지어내지 않고, 어디서 얻었는지를 함께 적는다.**
#
#   manual      사람이 올릴 때 적은 촬영일          가장 세다 — 본인이 아는 사실이다
#   file_meta   EXIF · mvhd                        기계가 잰 값
#   file_name   파일 이름 안의 날짜·시각            KakaoTalk_20260923_074025 · IMG_20260923_074025 · PXL_…
#   upload_time 그 파일을 받은 때                   마지막 — *"언제 찍었는지는 모른다"* 를 이 말로 적는다
#
# 마지막 칸이 있으므로 **이제 거절하지 않는다**. 대신 출처가 `upload_time` 이면 화면이 그렇게 말한다 —
# 라벨 없는 대리값은 금지지만, **라벨 붙은 사실**은 사실이다(그 파일을 그때 받은 것은 참이다).
#   마지막 `(?:\d{1,3})?` 가 **밀리초**다. 발행자 파일이 `KakaoTalk_20260923_074025068` 인데 첫 판은 이것 때문에
#   시각을 통째로 놓치고 날짜만 읽었다(`07:40` 이 있다고 발행자가 짚어 준 바로 그 자리다).
_NAME_TIME = (
    re.compile(r"(?<!\d)(20\d{2})(\d{2})(\d{2})[_\-T ]?(\d{2})(\d{2})(\d{2})(?:\d{1,3})?(?!\d)"),  # 20260923_074025068
    re.compile(r"(?<!\d)(20\d{2})[-.](\d{2})[-.](\d{2})[_ ](\d{2})[.:](\d{2})[.:](\d{2})"),        # 2026-09-23 07.40.25
    re.compile(r"(?<!\d)(20\d{2})(\d{2})(\d{2})(?!\d)()()()"),                                     # 20260923 (시각 없음)
)


def time_from_name(name: str, today: date | None = None) -> str | None:
    """파일 이름에서 찍은 때. 없으면 None — **지어내지 않는다**.

    걸러야 할 것이 둘이다: ① 해상도·일련번호가 날짜처럼 보이는 것(`20261332` 같은 불가능한 달·일)
    ② **앞날**(카메라 시계가 미래면 격자 칸 대조가 통째로 어긋난다). 둘 다 여기서 막는다.
    """
    today = today or date.today()
    for rx in _NAME_TIME:
        for m in rx.finditer(name):
            y, mo, d, hh, mm, ss = (g or "" for g in m.groups())
            try:
                # [발행자 실측 2026-09-24] 첫 판은 이 시각을 **UTC** 로 찍었다 — 휴대폰 파일명은 **현지 시각**이라 아홉 시간 어긋난다.
                # 이 PC 의 시간대로 읽는다(휴대폰과 PC 가 같은 곳에 있다는 가정 — 그 가정도 라벨에 적힌다).
                when = datetime(int(y), int(mo), int(d), int(hh or 0), int(mm or 0), int(ss or 0), tzinfo=datetime.now().astimezone().tzinfo)
            except ValueError:
                continue                       # 20261332 같은 것 — 날짜가 아니다
            if when.date() > today:
                continue                       # 앞날은 안 쓴다
            return when.isoformat(timespec="seconds")
    return None


def observed_ladder(src: Path, typed: str | None, pr: Any, now: datetime,
                    today: date | None = None) -> tuple[str, str]:
    """(찍은 때, 출처) — 네 칸을 순서대로. **마지막 칸이 있으므로 언제나 답이 있다.**"""
    typed = (typed or "").strip()
    if typed:
        return typed, "manual"
    if getattr(pr, "creation_time", None):
        return pr.creation_time, "file_meta"
    by_name = time_from_name(src.name, today)
    if by_name:
        return by_name, "file_name"
    return now.isoformat(timespec="seconds"), "upload_time"


def register(key: str, subject: str, observed_at: str | None = None, note: str = "",
             now: datetime | None = None) -> dict[str, Any]:
    """inbox(옮김) 또는 감시 폴더(복사) → media/<subject>/<observed_at>_<sha8>.<ext> + index.jsonl 레코드.
    [C17] sha 중복 거부가 읽고-검사하고-쓰는 꼴이라 동시 등록 둘이 둘 다 통과한다 — 한 덩이로(파일 이동까지)."""
    with sch.ledger_lock:
        return _register_locked(key, subject, observed_at, note, now)


def _register_locked(key: str, subject: str, observed_at: str | None, note: str,
                     now: datetime | None) -> dict[str, Any]:
    origin, src = _resolve_key(key)
    if not src.is_file():
        raise RegisterError(f"그런 파일이 없다: {key!r}")
    if subject not in subject_ids():
        raise RegisterError(f"등록되지 않은 재배 단위: {subject!r} (data/subjects.json)")
    if src.suffix.lower() not in MEDIA_EXT:
        raise RegisterError(f"영상·사진 파일이 아니다: {src.suffix!r} ({', '.join(sorted(MEDIA_EXT))})")
    pr = probe(src)
    now = now or datetime.now(timezone.utc)
    # [발행자 2026-09-23] 여기서 거절하던 자리. 이제 사다리가 언제나 답을 내고 **출처를 함께** 돌려준다.
    observed, observed_source = observed_ladder(src, observed_at, pr, now)
    try:
        datetime.fromisoformat(observed.replace("Z", "+00:00"))
    except ValueError:
        raise RegisterError(f"촬영 시각 형식이 아니다: {observed!r} (예 2026-09-18T15:30:00+09:00)")
    digest = sha256_of(src)
    if any(r.get("sha256") == digest for r in list_records()):
        raise RegisterError("같은 파일(sha256)이 이미 등록돼 있다")
    dest_dir = media_dir() / _safe(subject)
    dest_dir.mkdir(parents=True, exist_ok=True)
    stamp = re.sub(r"[^0-9T]", "", observed)[:15]
    dest = dest_dir / f"{stamp}_{digest[:8]}{src.suffix.lower()}"
    # [코드 평가 C8] 레코드 조립 · stamp(스키마 검증) → 파일 이동 → 원장 append. 전에는 옮긴 뒤 stamp 라 검증이 실패하면 파일은 media/ 로
    # 옮겨졌는데 원장 줄이 없는 고아가 남았다(inbox 후보에서도 사라짐). 바이트 수는 이동 전 원본에서 잰다(같은 바이트).
    rec = {
        "id": f"{'img' if src.suffix.lower() in IMAGE_EXT else 'vid'}_{digest[:12]}",
        "kind": KIND_IMAGE if src.suffix.lower() in IMAGE_EXT else KIND,
        "subject": subject,
        "observed_at": observed,
        "observed_at_source": observed_source,
        "recorded_at": now.isoformat(timespec="seconds"),
        "source": SOURCE,
        "resolution": RESOLUTION,
        "origin": origin,
        "file": str(dest.relative_to(media_dir())).replace("\\", "/"),
        "sha256": digest,
        "bytes": src.stat().st_size,
        "width": pr.width, "height": pr.height, "duration_sec": pr.duration_sec,
        "gps": list(pr.gps) if pr.gps else None,
        "note": note.strip()[:500],
    }
    rec = sch.stamp(rec)                      # [M-6] 원장에 쓰는 직전 한 번 — 스키마 밖 레코드는 여기서 죽는다(파일은 아직 제자리)
    if origin == "watch":
        fp = _fingerprint(src)
        shutil.copy2(str(src), str(dest))      # 동기화 폴더는 건드리지 않는다 — 옮기면 폰에서도 지워진다
        _mark_seen(key, fp)
        _mark_seen(fp, digest)
    else:
        shutil.move(str(src), str(dest))
    with index_path().open("a", encoding="utf-8") as f:
        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
    return rec


def public_view(rec: dict[str, Any]) -> dict[str, Any]:
    """화면·몰용 — PII 는 정본 sch.strip_pii(kind 가 선언한 pii)로 빼고, 위치 좌표는 '있음/없음'으로만."""
    v = sch.strip_pii({**rec, "kind": rec.get("kind") or KIND})
    v["gps"] = "있음" if rec.get("gps") else "없음"
    return v
