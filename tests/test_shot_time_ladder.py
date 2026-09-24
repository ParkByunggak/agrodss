# -*- coding: utf-8 -*-
# [발행자 실사용 2026-09-23] 카카오톡으로 받은 사진 넉 장이 전부 거절당했다.
#
#   KakaoTalk_20260923_074025068_04.jpg: 촬영 시각이 없다 — 메타에서 못 읽었고 입력도 없다.
#   시각 없는 영상은 1층에 들어가지 않는다 — 파일은 반입 대기함(inbox)에 남았다.
#
# 발행자: *"이 방법은 농업인들에게 **무리한 요구**다. **올린 날과 그 시각을 활용**해야 한다."* ·
#         *"사진을 올릴 때 **특정 날짜를 지정하면 그 날짜를 시스템이 인식**해야 할 것이다."* ·
#         *"`KakaoTalk_20260923_074025068_04` 여기에 **07:40분임을 알 수도 있다**."* ·
#         *"파일명을 강제로 수정하지 않는 한 위와 같은 시각의 구조를 가지고 있다. 적어도 안드로이드 OS 에서는."*
#
# 맞다. 메신저는 EXIF 를 지운다 — 규칙이 옳아도 **아무도 통과 못 하면 기능을 없앤 것**이다.
# 그렇다고 아무 시각이나 메우면 대리값이다. 사다리로 갈랐다: **지어내지 않고, 어디서 얻었는지를 적는다.**
#
#   manual      적어 주신 날짜        가장 세다 — 본인이 아는 사실
#   file_meta   EXIF · mvhd          기계가 잰 값
#   file_name   파일 이름의 날짜·시각  안드로이드 기본 이름이 이 구조다(발행자 확인)
#   upload_time 올리신 때            마지막 — *"찍은 때는 모른다"* 를 이 말로 적고 **화면이 그렇게 말한다**
from __future__ import annotations

from datetime import date, datetime, timezone

import pytest

from frontend import words
from ingest import media
from tests.test_chat_upload_voice_lan import SID, make_jpeg_with_exif

T = date(2026, 9, 23)
NOW = datetime(2026, 9, 23, 7, 40, 25, tzinfo=timezone.utc)


# ── 파일 이름 ──────────────────────────────────────────────────────────────────────
@pytest.mark.parametrize("name, want", [
    ("KakaoTalk_20260923_074025068_04.jpg", "2026-09-23T07:40:25+09:00"),   # 발행자가 실제로 올린 그 이름
    ("IMG_20260920_161500.jpg", "2026-09-20T16:15:00+09:00"),               # 안드로이드 기본
    ("VID_20260916_083012.mp4", "2026-09-16T08:30:12+09:00"),
    ("PXL_20260919_073000123.jpg", "2026-09-19T07:30:00+09:00"),            # 픽셀 — 밀리초가 붙는다
    ("Screenshot_20260918-121314.png", "2026-09-18T12:13:14+09:00"),
    ("2026-09-18 12.30.00.jpg", "2026-09-18T12:30:00+09:00"),               # 맥·윈도우 저장 이름
    ("20260917.jpg", "2026-09-17T00:00:00+09:00"),                          # 날짜만 — 시각은 0시
])
def test_the_time_android_leaves_in_the_file_name_is_read(name, want):
    """[발행자 실측 2026-09-24] 첫 판은 이 시각을 **UTC** 로 찍었다 — 휴대폰 파일명은 현지 시각이라 아홉 시간 어긋났다.
    관문은 TZ=Asia/Seoul 로 돈다 — 그래서 기대값이 +09:00 이다(이 PC 의 시간대로 읽는다)."""
    assert media.time_from_name(name, T) == want


@pytest.mark.parametrize("name", [
    "DSC_0042.jpg",                      # 일련번호 — 날짜가 아니다
    "screenshot_1920x1080.png",          # 해상도
    "IMG_20261332_000000.jpg",           # 13월 32일 — 날짜일 수 없다
    "KakaoTalk_20270101_000000.jpg",     # 앞날 — 카메라 시계가 미래면 칸 대조가 통째로 어긋난다
])
def test_a_number_that_is_not_a_time_is_not_taken_for_one(name):
    """넓히면 **반대편**을 함께 본다 — 지어내지 않는 것이 이 사다리의 값이다."""
    assert media.time_from_name(name, T) is None


# ── 사다리 ────────────────────────────────────────────────────────────────────────
class _Pr:
    def __init__(self, creation_time=None):
        self.creation_time = creation_time


@pytest.mark.parametrize("typed, meta, name, want_source", [
    ("2026-09-19", "2026-09-18T00:00:00+00:00", "IMG_20260917_101010.jpg", "manual"),
    (None, "2026-09-18T00:00:00+00:00", "IMG_20260917_101010.jpg", "file_meta"),
    (None, None, "IMG_20260917_101010.jpg", "file_name"),
    (None, None, "DSC_0042.jpg", "upload_time"),
])
def test_the_rungs_are_tried_in_order(typed, meta, name, want_source, tmp_path):
    when, src = media.observed_ladder(tmp_path / name, typed, _Pr(meta), NOW, T)
    assert src == want_source and when


def test_the_last_rung_means_the_file_is_never_turned_away(tmp_path):
    """마지막 칸이 있으므로 **거절이 없다** — 발행자의 넉 장이 거절당하던 자리."""
    when, src = media.observed_ladder(tmp_path / "DSC_0042.jpg", "", _Pr(None), NOW, T)
    assert src == "upload_time" and when == NOW.isoformat(timespec="seconds")


# ── 끝에서 끝까지 · 화면이 말한다 ──────────────────────────────────────────────────
def test_a_kakaotalk_photo_lands_with_the_time_from_its_name():
    """발행자가 실제로 올린 형태 — EXIF 는 없고 이름에 07:40 이 있다."""
    key = media.save_upload("KakaoTalk_20260923_074025068_04.jpg", make_jpeg_with_exif(None))
    rec = media.register(key, SID, now=NOW)
    assert rec["observed_at_source"] == "file_name"
    assert rec["observed_at"].startswith("2026-09-23T07:40")


def test_every_rung_has_a_word_a_farmer_understands():
    """출처를 **말하지 않으면** 라벨 없는 대리값이다 — 라벨이 붙어야 사실이다."""
    assert set(words.SHOT_TIME_SAID) == {"manual", "file_meta", "file_name", "upload_time"}
    for src, said in words.SHOT_TIME_SAID.items():
        assert src not in said and said.strip()
    assert "모릅니다" in words.shot_time("upload_time") or "없었습니다" in words.shot_time("upload_time")


def test_the_reply_says_where_the_time_came_from():
    """카드만 고치고 답변을 두면 반쪽이다 — 사람이 보는 줄에 출처가 있어야 한다."""
    from ingest import chat
    key = media.save_upload("DSC_9999.jpg", make_jpeg_with_exif(None))
    rec = media.register(key, SID, now=NOW)
    _, r = chat.send(SID, "", media_refs=[rec], today=T, now=NOW)
    assert words.shot_time("upload_time") in r["text"]


# ── 칸으로 이어졌는지를 화면이 말한다 (발행자 2026-09-24) ─────────────────────────────
def test_the_reply_says_which_capture_stage_the_photo_satisfied():
    """*"촬영 칸으로 이어졌는지가 보이지 않습니다."* — 이어져 있었다(대조가 사진을 증거로 썼다). 화면이 침묵했을 뿐이다.
    판정을 다시 하지 않고 같은 정본의 줄을 읽어 말한다 — 두 벌이면 언젠가 어긋난다."""
    from ingest import chat
    key = media.save_upload("KakaoTalk_20260923_074025068_01.jpg", make_jpeg_with_exif(None))
    rec = media.register(key, SID, now=NOW)
    _, r = chat.send(SID, "", media_refs=[rec], today=date(2026, 9, 24), now=NOW)
    assert "촬영" in r["text"] and "한 것으로 잡혔습니다" in r["text"], r["text"]
    assert "3단계" in r["text"], r["text"]                    # 9/23 은 칸 3 의 창(9/4~9/24) 안이다


def test_a_photo_outside_every_capture_window_does_not_claim_a_stage():
    """반대편 — 아무 창에도 안 드는 사진은 어느 칸도 잡았다고 말하지 않는다(있음을 세면 뚫린다)."""
    from ingest import chat
    key = media.save_upload("IMG_20260801_101010.jpg", make_jpeg_with_exif(None))
    rec = media.register(key, SID, now=NOW)                   # 기준점(8/25) 이전 — 소급 촬영은 증거가 아니다
    _, r = chat.send(SID, "", media_refs=[rec], today=date(2026, 9, 24), now=NOW)
    assert "잡혔습니다" not in r["text"], r["text"]


def test_a_photo_is_called_a_photo_in_the_evidence_line():
    """사진을 '영상' 이라 부르던 자리 — 사람이 보는 줄이다."""
    from judge import run as judge_run
    key = media.save_upload("KakaoTalk_20260923_074025068_02.jpg", make_jpeg_with_exif(None) + b"\x02")
    media.register(key, SID, now=NOW)
    env = next(e for e in judge_run.judgments_for(SID, today=date(2026, 9, 24)) if e.decision_id == "plan_vs_actual")
    row = next(r for r in env.result["rows"] if r["kind"] == "plan.capture" and r["status"] == "이행")
    assert row["evidence"].startswith("사진 ")


def test_the_file_name_rung_says_it_may_be_the_save_time():
    """[발행자 2026-09-24] *"파일명은 촬영 시각이 아니라 저장 시각일 수 있다"* — 라벨이 그 조건을 싣는다(조건 없는 값은 다른 사실이다)."""
    assert "저장" in words.shot_time("file_name") and "수 있" in words.shot_time("file_name")
