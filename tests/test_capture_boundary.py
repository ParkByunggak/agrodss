# -*- coding: utf-8 -*-
# [경계일 촬영 2026-09-21] 발행자께 *"나가시는 김에 넷"* 중 하나로 **촬영**을 드렸는데, 그 경로만 걷지 않았다(예찰·제초는
# 사건이고 촬영은 **영상·사진 원장**으로 판정한다 — 다른 길이다). 걸어 보니 결함이 있었다.
#
#   9/24 사진 **한 장** → 칸 3(마감 9/24)과 칸 4(작업일 9/24)가 **둘 다 '이행'**
#
# 한 번 찍었는데 두 단계가 기록된 것으로 센다 — **거짓 이행**이고, 되먹임(이행 사례)까지 오염시킨다.
#
# 약속은 이미 정해져 있었다. `grid.capture` 가 *"격자 창은 양끝 포함이라 경계일은 두 칸에 걸린다 … 답이 오기 전까지의
# **약속**: 경계일은 **앞 칸**이다(첫 매치)"* 라고 적고, 그 주석이 **"판정기마다 따로 창을 비교하면 그 약속이 갈린다"** 고
# 경고까지 해 두었다(실측 예시로 `stage_for_day` 와 `risk_alert` 가 갈렸던 것을 들면서). 단계 판정과 경보는 그 정본으로
# 왔는데 **촬영 대조만 제 창을 따로 비교하고 있었다** — 처방이 한 지점에 갇힌 형태(§7.5 지점 축).
from __future__ import annotations

from datetime import date

import pytest

from ingest import media, parcels
from judge import plan_vs_actual as pva

SID = "p001-jjokpa-2026f"
TODAY = date(2026, 9, 25)
_RAW = [s for s in media.load_subjects() if s["id"] == SID][0]
SUBJ = parcels.enrich_subject(_RAW, parcels.by_id("p001"))


def _shot(day: str, n: str = "") -> dict:
    return {"kind": "observation.image", "id": f"img{n}_{day}", "subject": SID, "observed_at": day,
            "source": "farmer", "file": "x.jpg"}


def _caps(videos) -> dict[str, str]:
    env = pva.judge(SUBJ, today=TODAY, evts=[], videos=list(videos), reasons=[], notes=[])
    return {r["stage"].split(".", 1)[0]: r["status"] for r in env.result["rows"] if r["kind"] == "plan.capture"}


def test_one_photo_on_the_boundary_day_credits_only_the_earlier_stage():
    """원 결함 — 9/24 는 칸 3 의 마감이자 칸 4 의 작업일이다. 한 장이 두 칸을 채우면 **찍지 않은 단계가 초록**이 된다."""
    caps = _caps([_shot("2026-09-24")])
    assert caps["3"] == "이행", caps
    assert caps["4"] != "이행", f"한 장이 두 칸을 채웠다 — 경계일은 앞 칸이다(grid.capture 약속) · {caps}"
    assert sum(1 for v in caps.values() if v == "이행") == 1, caps


def test_a_photo_inside_one_window_still_credits_that_stage():
    """[게이트는 양방향] 고치면서 되던 것을 깨뜨리지 않는다 — 창 한가운데 한 장은 그 칸을 채운다."""
    caps = _caps([_shot("2026-09-22")])
    assert caps["3"] == "이행" and caps["4"] == "미이행", caps


def test_two_photos_on_two_days_credit_two_stages():
    """한 장이 한 칸만 채운다고 해서 **여러 장이 여러 칸을 못 채우는 것은 아니다**(과잉 제한의 반대편)."""
    caps = _caps([_shot("2026-09-22"), _shot("2026-09-30")])
    assert caps["3"] == "이행" and caps["4"] == "이행", caps


def test_several_photos_in_one_window_still_credit_only_that_one_stage():
    """같은 칸에 여러 장을 찍어도 칸은 하나다 — 남은 장이 **다음 칸으로 넘어가지 않는다**(경계일 밖이므로)."""
    caps = _caps([_shot("2026-09-20", "a"), _shot("2026-09-21", "b"), _shot("2026-09-22", "c")])
    assert caps["3"] == "이행" and caps["4"] == "미이행", caps


def test_the_promise_lives_in_one_place_and_this_layer_follows_it():
    """정본은 `grid.capture` 다 — 이 층이 그 약속을 **따르는지**를 문면이 아니라 동작으로 본다(칸 경계 = 앞 칸)."""
    from grid import capture as gc
    from grid import schema as gs
    unit = gs.load(gs.unit_path(SUBJ["grid_unit"]))
    day = (date.fromisoformat("2026-09-24") - date.fromisoformat(SUBJ["anchor"])).days
    open_ = [s["order"] for s in gc.stages_open(unit, day)]
    assert len(open_) >= 2, f"경계일이 아니면 이 검사가 성립하지 않는다 — 격자가 바뀌었는가 · {open_}"
    assert gc.stage_for_day(unit, day)["order"] == open_[0]                      # 정본의 약속: 앞 칸
    caps = _caps([_shot("2026-09-24")])
    assert caps[str(open_[0])] == "이행" and caps[str(open_[1])] != "이행"        # 이 층도 같은 답을 낸다
