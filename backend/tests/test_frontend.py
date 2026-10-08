"""프런트 규칙: publish 클래스 보존, 개발용 장치 제거, I-01 매핑표 대조, 기한 판정 함수."""
import re
import shutil
import subprocess

import pytest

from app import config

FE = config.ROOT / "frontend"
PUB = config.ROOT / "publish"
PAGES = ["login", "meetings", "detail", "todos", "team", "profile"]

# 스토리보드 I-01 통합 매핑표
I01 = {
    "login":    {("POST", "/api/auth/signup"), ("POST", "/api/auth/login"), ("POST", "/api/teams/join")},
    "meetings": {("POST", "/api/teams/{id}/meetings"), ("GET", "/api/teams/{id}/meetings"),
                 ("POST", "/api/upload"), ("GET", "/api/auth/me"), ("POST", "/api/auth/logout")},
    "detail":   {("GET", "/api/meetings/{id}"), ("PUT", "/api/meetings/{id}"), ("DELETE", "/api/meetings/{id}"),
                 ("PUT", "/api/todos/{id}"), ("POST", "/api/meetings/{id}/comments"),
                 ("GET", "/api/meetings/{id}/comments"), ("DELETE", "/api/comments/{id}")},
    "todos":    {("GET", "/api/teams/{id}/todos"), ("PUT", "/api/todos/{id}"), ("DELETE", "/api/todos/{id}"),
                 ("GET", "/api/me/todos")},
    "team":     {("POST", "/api/teams"), ("GET", "/api/teams"), ("PUT", "/api/teams/{id}"),
                 ("POST", "/api/teams/join"), ("GET", "/api/teams/{id}/members"), ("PUT", "/api/teams/{id}/code"),
                 ("GET", "/api/teams/{id}/activities")},
    "profile":  {("GET", "/api/auth/me"), ("PUT", "/api/auth/me"), ("GET", "/api/me/todos"),
                 ("GET", "/api/me/activities")},
}

# 매핑표와 실제 화면이 다른 곳 (구현 중 확인된 것. 보고서에도 적는다)
#  - 모든 화면: 팀 id 와 역할을 얻으려고 auth/me 를 부른다 (표는 meetings · profile 에만 적음)
#  - meetings: logout 버튼은 publish 에 없고 profile 에 있다 (표는 meetings 에 적음)
#  - detail · todos: 담당자 선택 목록에 팀 멤버가 필요해 members 를 부른다 (표에 없음)
ALLOWED_EXTRA = {
    "login": {("GET", "/api/auth/me")},
    "meetings": set(),
    "detail": {("GET", "/api/auth/me"), ("GET", "/api/teams/{id}/members"), ("GET", "/api/teams/{id}/todos")},
    "todos": {("GET", "/api/auth/me"), ("GET", "/api/teams/{id}/members")},
    "team": {("GET", "/api/auth/me")},
    "profile": {("POST", "/api/auth/logout")},
}
MOVED_AWAY = {"meetings": {("POST", "/api/auth/logout")}}

CALL_START = re.compile(r"API\.(get|post|put|del)\(")
BOOT = re.compile(r"API\.(me|requireLogin|requireTeam)\(")
M = {"get": "GET", "post": "POST", "put": "PUT", "del": "DELETE"}


def _read(page):
    return (FE / f"{page}.html").read_text(encoding="utf-8")


def _first_arg(src: str, start: int) -> str:
    """API.xxx( 바로 뒤에서 첫 인자 식을 문자열 밖의 쉼표나 닫는 괄호까지 읽는다."""
    depth, i, quote = 0, start, None
    while i < len(src):
        c = src[i]
        if quote:
            if c == "\\":
                i += 1
            elif c == quote:
                quote = None
        elif c in "'\"`":
            quote = c
        elif c in "([{":
            depth += 1
        elif c in ")]}":
            if depth == 0:
                break
            depth -= 1
        elif c == "," and depth == 0:
            break
        i += 1
    return src[start:i]


def _paths(expr: str) -> list[str]:
    """첫 인자 식에서 경로 후보를 만든다. 삼항(? :)은 가지마다, 문자열 이어붙이기는 하나로,
    문자열이 아닌 항은 {id} 로 본다."""
    parts, buf, quote, i = [], "", None, 0
    tokens = []
    while i < len(expr):
        c = expr[i]
        if quote:
            buf += c
            if c == "\\":
                i += 1
                buf += expr[i]
            elif c == quote:
                tokens.append(("s", buf[1:-1]))
                buf, quote = "", None
        elif c == "(":
            depth, j, q = 1, i + 1, None
            while j < len(expr) and depth:
                ch = expr[j]
                if q:
                    if ch == "\\":
                        j += 1
                    elif ch == q:
                        q = None
                elif ch in "'\"`":
                    q = ch
                elif ch == "(":
                    depth += 1
                elif ch == ")":
                    depth -= 1
                j += 1
            tokens.append(("o", expr[i:j]))
            i = j
            continue
        elif c in "'\"`":
            if buf.strip():
                tokens.append(("o", buf.strip()))
            buf, quote = c, c
        elif c in "?:" :
            if buf.strip():
                tokens.append(("o", buf.strip()))
            buf = ""
            tokens.append(("t", c))
        elif c == "+":
            if buf.strip():
                tokens.append(("o", buf.strip()))
            buf = ""
        else:
            buf += c
        i += 1
    if buf.strip():
        tokens.append(("o", buf.strip()))
    branches, cur = [], []
    for kind, val in tokens:
        if kind == "t" and val == "?":
            cur = []  # 조건식은 버린다
        elif kind == "t" and val == ":":
            branches.append(cur)
            cur = []
        else:
            cur.append("{id}" if kind == "o" else re.sub(r"\$\{[^}]*\}", "{id}", val))
    branches.append(cur)
    out = []
    for b in branches:
        p = "".join(b).split("?")[0]
        p = re.sub(r"(?<=[A-Za-z])\{id\}$", "", p)  # 슬래시 없이 붙은 변수는 질의 문자열
        if p.startswith("/api/"):
            out.append(p)
    return out


def calls(page: str) -> set:
    src = _read(page)
    out = set()
    for m in CALL_START.finditer(src):
        for p in _paths(_first_arg(src, m.end())):
            out.add((M[m.group(1)], p))
    if BOOT.search(src):
        out.add(("GET", "/api/auth/me"))
    return out


@pytest.mark.parametrize("page", PAGES)
def test_page_has_api_js_and_no_publish_scaffolding(page):
    src = _read(page)
    assert '<script src="api.js"></script>' in src
    assert src.index("theme.js") < src.index("api.js")
    assert "stateBar(" not in src
    assert "const STATES" not in src and "STATES[" not in src
    assert 'id="note"' not in src
    assert "!important" not in src


@pytest.mark.parametrize("page", PAGES)
def test_no_api_path_or_status_code_shown_to_users(page):
    src = _read(page)
    # 사용자에게 보이는 글자에 상태 코드 이름이 새어 나오지 않는다 (코드 비교용 문자열은 스크립트 안에서만)
    html_only = re.sub(r"<script.*?</script>", "", src, flags=re.S)
    for bad in ("PAYLOAD_TOO_LARGE", "UNSUPPORTED_MEDIA_TYPE", "INVALID_CREDENTIALS", "OWNER_ONLY", "{assignee_id}"):
        assert bad not in html_only


def _tokens(text: str) -> set:
    """class="..." 속성의 클래스 토큰. 값 안에 ${...} 보간이 있으면 그 부분은 뺀다."""
    out = set()
    text = re.sub(r"\$\{[^}]*\}", " ", text)
    for m in re.finditer(r'class="([^"]*)"', text):
        out |= set(m.group(1).split())
    return out


# 퍼블리싱 확인용 줄이 지워지면서 사라지는 것만 허용 (note 줄 · 개발자 설명 줄 · 활동의 kind 라벨)
ALLOWED_GONE = {"mt-2.5", "mt-3", "mt-4", "font-mono"}
# 잠금 표시(team.html 의 member-view 와 같은 표시)와 숨김, 그리고 구현 중 확인된 예외
#  detail.html 수정 모드 입력: h-9 w-auto (보고서에 적은 열린 항목)
ALLOWED_NEW = {"hidden", "opacity-40", "opacity-60", "pointer-events-none", "disabled", "h-9", "w-auto"}


@pytest.mark.parametrize("page", PAGES)
def test_publish_class_tokens_survive(page):
    """확정 디자인의 클래스를 그대로 쓴다. 제거된 개발용 요소의 것만 빠질 수 있다."""
    pub = (PUB / f"{page}.html").read_text(encoding="utf-8")
    fe = _read(page)
    alive = set(re.findall(r"[A-Za-z0-9:\-\[\]./%#()_,!]+", fe))
    gone = {t for t in _tokens(pub) if t not in alive} - ALLOWED_GONE
    assert gone == set(), sorted(gone)


@pytest.mark.parametrize("page", PAGES)
def test_no_new_class_tokens_beyond_the_recorded_exceptions(page):
    """새 색 · 새 크기를 만들지 않는다. class 속성에 새로 생긴 토큰은 기록된 예외뿐."""
    pub = (PUB / f"{page}.html").read_text(encoding="utf-8")
    new = _tokens(_read(page)) - _tokens(pub) - ALLOWED_NEW
    assert new == set(), sorted(new)


def test_theme_js_is_identical_to_publish():
    assert (FE / "theme.js").read_bytes() == (PUB / "theme.js").read_bytes()


@pytest.mark.parametrize("page", PAGES)
def test_page_calls_cover_the_i01_mapping(page):
    got = calls(page)
    need = I01[page] - MOVED_AWAY.get(page, set())
    assert need <= got, f"{page}: 매핑표에 있는데 부르지 않음 {sorted(need - got)}"
    extra = got - I01[page]
    assert extra <= ALLOWED_EXTRA[page], f"{page}: 매핑표에 없는 호출 {sorted(extra - ALLOWED_EXTRA[page])}"


def test_union_of_all_pages_is_exactly_the_26_endpoints_and_none_unused():
    from test_contract import EXPECTED
    norm = {(m, re.sub(r"\{[^}]+\}", "{id}", p)) for m, p in EXPECTED}
    union = set().union(*(calls(p) for p in PAGES))
    assert norm - union == set(), f"어느 화면도 부르지 않는 경로: {sorted(norm - union)}"
    assert union - norm == set(), f"서버에 없는 경로를 부름: {sorted(union - norm)}"
    assert len(norm) == 26


@pytest.mark.skipif(shutil.which("node") is None, reason="node 가 없음")
def test_is_late_and_time_helpers_with_node():
    r = subprocess.run(["node", str(config.ROOT / "backend" / "tests" / "js" / "islate.check.js")],
                       capture_output=True, text=True)
    assert r.returncode == 0, r.stdout + r.stderr


@pytest.mark.skipif(shutil.which("node") is None, reason="node 가 없음")
@pytest.mark.parametrize("page", PAGES)
def test_inline_scripts_have_valid_syntax(page, tmp_path):
    scripts = re.findall(r"<script>(.*?)</script>", _read(page), flags=re.S)
    assert scripts
    f = tmp_path / f"{page}.js"
    f.write_text("\n".join(scripts), encoding="utf-8")
    r = subprocess.run(["node", "--check", str(f)], capture_output=True, text=True)
    assert r.returncode == 0, r.stderr
