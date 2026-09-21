# -*- coding: utf-8 -*-
# FILE: scripts/hook_block_shell_authoring.py
# ROLE: [U-13] Claude Code PreToolUse 훅 — 셸로 파일을 고치거나 셸이 문면을 먹는 경로를 관문에서 막는다.
#       CLAUDE.md "파일 수정: Edit/Write 가 기본 — heredoc · python -c 파일 쓰기 금지" 의 **경로**다. 문서는 경로를 막지 못한다.
#
#   규칙은 VELA HEREDOC-1(2026-09-14 · 갈래 확장 09-15)에서 인용했다(코드는 다시 썼다):
#     막는다   ① heredoc 이 파일로 흘러간다(리다이렉트 · tee · 출력 버리기)  ② heredoc 본문이 파일을 쓴다
#              ③ 인라인 코드(-c/-e)가 파일을 쓴다  ④ 큰따옴표 인라인 코드 안의 백틱 · $( (셸이 먹어 조용히 바뀐다)
#              ⑤ PowerShell 파일 쓰기(Set/Add-Content · Out-File · [IO.File]::Write · New-Item -Force · 리다이렉트) · 보간형 @"…"@
#     통과      읽기 전용 측정 heredoc(출력만) · 작은따옴표 인라인 · @'…'@ · > $null · 2>$null · | Out-Null · 판정 불능(가드가 작업을 인질로 잡지 않는다)
#
#   계약: stdin 으로 훅 JSON({tool_name, tool_input.command})을 받아, 막을 때만 deny JSON 을 stdout 에 낸다. 항상 exit 0.
#   배선: .claude/settings.json PreToolUse · matcher Bash|PowerShell. 래칫: tests/test_hook_guard.py(거부·통과 양방향 + 배선).
#   가드 창: 훅 설정은 세션 시작 시 읽힌다 — 이 훅을 만든 회차에는 안 돈다(VELA 실측). 세션 시작 시 heredoc 파일 쓰기를 한 번 시도해 확인한다.
from __future__ import annotations

import json
import re
import sys

try:
    sys.stdout.reconfigure(encoding="utf-8")   # type: ignore[attr-defined]
except Exception:
    pass

HEREDOC = re.compile(r"<<(-?)\s*(?:(['\"])([A-Za-z_]\w*)\2|([A-Za-z_]\w*))(?![\w<])")
REDIRECT = re.compile(r"(?<![-=<])\d?>>?\s*(?!&)\S")       # 2>&1 · >&2 는 파일이 아니다 · `->` `=>` 는 화살표다(D 리뷰 #29)
TEE = re.compile(r"\|\s*tee\b")
TEE_LINE = re.compile(r"(?m)^\s*tee\b")                    # 앞줄이 `|` 로 끝나고 다음 줄이 tee 로 시작하는 형태(D9)
WRITERS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"\.write_text\s*\("), "write_text"), (re.compile(r"\.write_bytes\s*\("), "write_bytes"),
    # [코드 평가 D10] 표준출력 쓰기(sys.stdout/stderr.write · json.dump(…, sys.stdout))는 측정이다 — 막지 않는다(과잉 차단은 가드를 끄게 만든다)
    (re.compile(r"(?<!sys\.stdout)(?<!sys\.stderr)(?<!stdout)(?<!stderr)\.\s*write\s*\("), "write()"), (re.compile(r"\bwritelines\s*\("), "writelines()"),
    # open() 은 **모드 인자**만 본다 — 전에는 `[^)]*` 가 비어 따옴표 뒤 첫 글자를 모드로 읽어 open("agrodss_backlog.md") 를 쓰기로 오판했다
    (re.compile(r"\bopen\s*\((?:[^,()]*,\s*)(?:mode\s*=\s*)?['\"][rbt+]*[wax]"), "open(…,'w'/'a'/'x')"),
    (re.compile(r"\bjson\.dump\s*\((?![^()]*sys\.std(?:out|err))"), "json.dump()"),
    (re.compile(r"\bshutil\.(copy|move)"), "shutil.copy/move"), (re.compile(r"\bos\.(replace|rename|remove|unlink)\b"), "os.replace/remove"),
    (re.compile(r"\.unlink\s*\("), "unlink()"), (re.compile(r"\.rename\s*\("), "rename()"),
    (re.compile(r"\b(?:write|append)File(?:Sync)?\s*\("), "fs.writeFile/appendFile"),   # node -e
)
# [코드 평가 D8] 인터프리터 앞 경로(/usr/bin/python3) · 버전 접미(python3.12) · 아무 옵션 토큰(-3 · -X utf8) 뒤의 -c/-e 도 본다.
# 전에는 옵션이 `-[A-Za-z]\w*` 뿐이고 lookbehind 가 `/` 를 제외해 배치가 고르는 바로 그 호출형(`py -3 -c`)을 못 봤다.
INLINE = re.compile(r"(?<![\w-])(?:\S*/)?(python3?(?:\.\d+)?|py|node|perl|ruby)(?:\.exe)?\s+(?:-\S+\s+(?:(?!-)\S+\s+)?)*?-([ce])\s+")
SHELL_EATS = ((re.compile(r"(?<!\\)`"), "백틱 명령 치환"), (re.compile(r"(?<!\\)\$\("), "$( ) 명령 치환"))
PS_WRITERS: tuple[tuple[re.Pattern[str], str], ...] = (
    (re.compile(r"(?i)\b(Set|Add)-Content\b"), "Set-Content/Add-Content"), (re.compile(r"(?i)\bOut-File\b"), "Out-File"),
    (re.compile(r"(?i)\[(?:System\.)?IO\.File\]::(Write|Append)"), "[IO.File]::Write/Append"),
    (re.compile(r"(?i)\bNew-Item\b(?=[^\n]*-Force)"), "New-Item -Force"), (re.compile(r"\d?>>?\s*(?!&|\$null\b)\S"), "리다이렉트"),
)
PS_HERE_INTERP = re.compile(r"@\"\s*\r?\n")
# [실측 2026-09-21] 이 세션에서 규율을 세 번 어겼고, 그 셋을 판정기에 그대로 먹여 보니 **둘은 잡고 하나는 샜다** —
# `sed -i` 다. heredoc 도 아니고 인라인 코드도 아니면서 **파일을 제자리에서 고친다**. 규율의 대상은 '긴 문면'이 아니라
# *"셸로 파일을 고치는 것"* 이므로 같은 급이다. 읽기 전용(`sed -n 1,5p`)은 통과해야 한다 — 과잉 차단은 가드를 끄게 만든다.
INPLACE: tuple[tuple[re.Pattern[str], str], ...] = (
    # 붙여 쓴 플래그(`-Ei` · `-pi`)도 본다 — `-i` 라는 **글자 그대로**를 찾으면 그 형태가 샌다(첫 판이 `perl -pi` 를 놓쳤다).
    # 대문자 `-I` 같은 다른 뜻의 플래그를 안 건드리게 **실제로 쓰는 조합만** 적는다(과잉 차단은 가드를 끄게 만든다).
    (re.compile(r"\bsed\s+[^|\n]*?(?:--in-place|-[Ernsz]*i(?:\.\S+)?(?=[\s'\"]|$))"), "sed -i (제자리 수정)"),
    (re.compile(r"\bperl\s+[^|\n]*?-(?:i|[pn]i|[pn]ie)(?:\.\S+)?(?=[\s'\"]|$)"), "perl -i (제자리 수정)"),
    (re.compile(r"\bawk\s+[^|\n]*?-i\s+inplace\b"), "awk -i inplace"),
    (re.compile(r"\btruncate\s+[^|\n]*?-s\b"), "truncate -s"),
    (re.compile(r"\bdd\s+[^|\n]*?\bof="), "dd of="),
)
REASON = """[U-13] 긴 문면을 셸에 통과시키지 않는다 — {why}
  걸린 지점: {evidence}
  대신: 소스·검사·대장 수정은 Edit/Write 도구, 새 파일은 Write, 되풀이 작업은 scripts/ 에 파일로 두고 실행한다.
  셸 인라인은 읽기 전용 측정에만 — 그때도 출력을 버리지 않고, 꼭 인라인이면 작은따옴표로 감싼다."""


def _heredoc_body(cmd: str, end: int, delim: str, strip_tabs: bool) -> str:
    nl = cmd.find("\n", end)
    if nl < 0:
        return ""
    body: list[str] = []
    for line in cmd[nl + 1:].split("\n"):
        if (line.lstrip("\t") if strip_tabs else line).strip() == delim:
            break
        body.append(line)
    return "\n".join(body)


def _quoted(cmd: str, i: int):
    if i >= len(cmd) or cmd[i] not in "\"'":
        return None
    q, j = cmd[i], i + 1
    while j < len(cmd):
        if cmd[j] == "\\" and q == '"':
            j += 2
            continue
        if cmd[j] == q:
            return q, cmd[i + 1:j]
        j += 1
    return q, cmd[i + 1:]


def _inline(cmd: str):
    for m in INLINE.finditer(cmd):
        blk = _quoted(cmd, m.end())
        if not blk:
            continue
        quote, code = blk
        for rx, name in WRITERS:
            if rx.search(code):
                return f"인라인 코드({m.group(1)} -{m.group(2)})가 파일을 쓴다({name}).", code.strip()[:120]
        if quote != '"':
            continue
        for rx, name in SHELL_EATS:
            hit = rx.search(code)
            if hit:
                return f"큰따옴표 인라인 코드 안에 {name}이 있다 — 셸이 먹어 조용히 바뀐다.", code[max(0, hit.start() - 30):hit.start() + 30].strip()
    return None


def _powershell(cmd: str):
    for rx, name in PS_WRITERS:
        hit = rx.search(cmd)
        if hit:
            s = cmd.rfind("\n", 0, hit.start()) + 1
            e = cmd.find("\n", hit.start())
            return f"PowerShell 로 파일을 쓴다({name}).", cmd[s:e if e >= 0 else len(cmd)].strip()[:120]
    if PS_HERE_INTERP.search(cmd):
        return "보간형 here-string(@\" … \"@) — $( ) 와 백틱 이스케이프가 먹혀 문면이 바뀐다. @'…'@ 를 쓴다.", "@\" … \"@"
    return _inline(cmd)


def verdict(cmd: str, tool: str = "Bash"):
    """막을 사유 (why, evidence). 통과면 None. 도구별로 갈린다(PowerShell 백틱은 치환이 아니라 이스케이프 — 규칙을 그대로 옮기면 오탐)."""
    if tool == "PowerShell":
        return _powershell(cmd)
    v = _inline(cmd)
    if v:
        return v
    for rx, name in INPLACE:                # heredoc 도 인라인 코드도 아니면서 파일을 고치는 형태(실측된 구멍)
        hit = rx.search(cmd)
        if hit:
            return f"셸이 파일을 제자리에서 고친다({name}).", hit.group(0).strip()[:120]
    outside = cmd                       # [코드 평가 D9] heredoc 본문을 걷어낸 나머지 — 리다이렉트·tee 는 같은 줄이 아니라 **어디든** 본다
    for m in HEREDOC.finditer(cmd):
        delim = m.group(3) or m.group(4)
        s = cmd.rfind("\n", 0, m.start()) + 1
        e = cmd.find("\n", m.start())
        line = cmd[s:e if e >= 0 else len(cmd)]
        if REDIRECT.search(line) or TEE.search(line):
            return "heredoc 출력이 파일로 흘러간다(출력을 버리는 것도 포함).", line.strip()[:120]
        body = _heredoc_body(cmd, m.end(), delim, strip_tabs=bool(m.group(1)))
        if body:
            outside = outside.replace(body, "", 1)
        # `{ cat <<EOF … EOF } > out.txt` · `( … ) > out.txt` · 다음 줄 `tee out.txt` — 본문 밖 어디에 있어도 파일로 흐르는 것이다
        rest = outside.replace(line, "", 1)
        hit = REDIRECT.search(rest) or TEE.search(rest) or TEE_LINE.search(rest)   # 파이프가 앞줄 끝에 있고 tee 가 다음 줄에 오는 형태
        if hit:
            ln = rest[max(0, hit.start() - 40):hit.end() + 40].strip().replace("\n", "⏎")
            return "heredoc 이 있는 명령의 출력이 파일로 흘러간다(다른 줄 · 블록 뒤).", ln[:120]
        for rx, name in WRITERS:
            hit = rx.search(body)
            if hit:
                ln = body[:hit.start()].count("\n") + 1
                return f"heredoc 본문이 파일을 쓴다({name}).", f"<<{delim} 본문 {ln}행: {body.split(chr(10))[ln - 1].strip()[:100]}"
    return None


def main() -> int:
    try:
        payload = json.load(sys.stdin)
        cmd = (payload.get("tool_input") or {}).get("command") or ""
        tool = payload.get("tool_name") or "Bash"
    except Exception as e:  # noqa: BLE001
        # [조용한 실패 전수 2026-09-21] 여기서 0 을 돌려주는 것은 **통과**다. 못 읽은 것을 판정할 수는 없으니 통과가
        # 맞다(막으면 어떤 Bash 도 못 돈다). 그러나 **조용히** 통과하면 가드가 죽은 줄을 아무도 모른다 —
        # "가드가 있는데 안 도는 상태는 가드가 없는 것보다 나쁘다". 통과하되 말한다.
        print(f"[hook] 입력을 못 읽어 통과시킨다 — 이 회차의 가드는 무력하다({type(e).__name__}: {e})", file=sys.stderr)
        return 0
    if not cmd:
        return 0
    v = verdict(cmd, tool)
    if not v:
        return 0
    print(json.dumps({"hookSpecificOutput": {"hookEventName": "PreToolUse", "permissionDecision": "deny",
                                             "permissionDecisionReason": REASON.format(why=v[0], evidence=v[1])}}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
