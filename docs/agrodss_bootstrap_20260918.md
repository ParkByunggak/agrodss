# agrodss 부트스트랩 — `D:\agrodss` 로컬 세션 첫 작업

작성 2026-09-18. 발행자 결정: 로컬 Claude Code 세션을 `D:\agrodss` 에서 시작한다.
이 문서는 그 세션의 **첫 지시 한 장**이다. 원격 저장소를 clone 하고 단계 0 을 시작한다.

## 1. 로컬 준비 (2026-09-18 갱신 — 원격이 생겼다)

원격 `https://github.com/ParkByunggak/agrodss` 에 첫 커밋(1110d16)이 있다. 로컬은 한 줄이다.

```
git clone https://github.com/ParkByunggak/agrodss.git D:\agrodss
```

vela 원격은 **추가하지 않는다**. vela 는 경험이지 원격이 아니다 — 남겨 두면 다음 사람이
코드를 당겨 온다(이식 폐기 결정). 필요한 문서는 전부 이 저장소 `docs/` 에 있다.

PowerShell 5.1 의 `>` 는 UTF-16 으로 쓴다 — 한글 파일을 리다이렉트로 만들지 않는다.
대장을 화면에 띄우려면 `python docs\render_backlog.py docs\agrodss_backlog.md backlog.html`
(`python -m pip install markdown` 1회 필요).

## 2. 세션 시작 시 확인 1회

CLAUDE.md 씨앗의 가드(heredoc 차단 훅)는 **그것을 만든 회차에 안 돈다**(VELA 실측
2026-09-16). 첫 세션은 규율로만 지킨다는 것을 알고 시작한다. 두 번째 세션부터
스크래치패드에 heredoc 으로 파일을 써 보고 차단되는지 본다.

## 3. 첫 지시 (그대로 붙여 넣기)

```
docs/agrodss_backlog.md 가 정본이다. 먼저 M-0 을 완료로 갱신한다.
docs/agrodss_milestones_20260918.md 단계 0 을 시작한다.
읽을 것: design_tree_review_20260918.md(§4 즉시 4건 · §6 몰 중심) · agrodss_mall_tree_20260918.md.
할 것:
 대장 I-1~I-5 (0-4 즉시 5건)를 각각 한 장으로 확정한다 — ①산출 7종 정의 ②양분 축 등록(관측 축 · 해상도 두 수준)
     ③입력 5종(필지·사건·관찰·계획·결정) ④격자가 참조하는 축 최소 목록 ⑤몰↔DSS 경계 필드 목록(source 필수).
     전부 종이(docs/) — 코드 없음. 각 장은 "무엇을 지키려는가" 한 줄로 시작한다.
하지 말 것: 코드 · 스키마 파일 · VELA 저장소 참조(경험 문서 두 개만 본다).
막히면: 0-1(첫 농가·작목) · 0-3(노출 여부)은 발행자 결정 — 가정을 적고 진행하되 가정을 표에 남긴다.
```

## 4. 이 저장소에 없는 것

- VELA 코드 — 이식 폐기. `agrodss_port_inventory` §2·§4 의 원천·키 이름만 경험으로
- VELA `.env` 값 — agrodss 는 키를 따로 받는다(쿼터 경합·회전 단절)
- 실질의 — 들깨 1건은 VELA `improvement_drafts.json` 에 있다. 필요하면 **읽기만**
