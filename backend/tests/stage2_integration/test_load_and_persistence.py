"""동시 50명 · 성능 기준 · 서버를 껐다 켜도 데이터가 남는지."""
import statistics
import time
from concurrent.futures import ThreadPoolExecutor

import httpx

from .conftest import PW, new_team, new_user


def _p95(xs):
    xs = sorted(xs)
    return xs[max(0, int(len(xs) * 0.95) - 1)]


def test_fifty_concurrent_users_can_sign_up_and_use_the_api(server):
    """Assumptions: 동시 50명."""
    def one(i):
        with httpx.Client(base_url=server.base, timeout=90) as c:
            r = c.post("/api/auth/signup", json={"email": f"conc{i}-{int(time.time()*1000)}@example.com",
                                                 "password": PW, "name": f"동시{i}"})
            tok = r.json()["token"]
            s = time.perf_counter()
            me = c.get("/api/auth/me", headers={"Authorization": f"Bearer {tok}"})
            return r.status_code, me.status_code, time.perf_counter() - s

    t0 = time.perf_counter()
    with ThreadPoolExecutor(50) as ex:
        res = list(ex.map(one, range(50)))
    total = time.perf_counter() - t0
    assert all(a == 201 and b == 200 for a, b, _ in res), [(a, b) for a, b, _ in res if (a, b) != (201, 200)]
    assert total < 60, total
    print(f"\n[동시 50명] 가입 50건 전체 {total:.1f}초, /me 최대 {max(x[2] for x in res)*1000:.0f}ms")


def test_api_response_time_under_100ms_over_http(http):
    """Metrics: API 100ms 이내 (받아쓰기와 인증 2종 제외)."""
    leader, _, team = new_team(http)
    for i in range(40):
        leader.post(f"/api/teams/{team['id']}/meetings", json={
            "title": f"회의 {i}", "met_at": f"2026-09-{(i % 27) + 1:02d}T05:00:00Z", "attendees": "김대리", "body": "본문"})
    tid = team["id"]
    paths = [f"/api/auth/me", f"/api/teams/{tid}/meetings", f"/api/teams/{tid}/todos", "/api/me/todos",
             f"/api/teams/{tid}/members", f"/api/teams/{tid}/activities", "/api/me/activities"]
    for p in paths:  # 워밍업
        leader.get(p)
    report = {}
    for p in paths:
        ms = []
        for _ in range(20):
            s = time.perf_counter()
            r = leader.get(p)
            ms.append((time.perf_counter() - s) * 1000)
            assert r.status_code == 200
        report[p] = (statistics.mean(ms), _p95(ms))
    print("\n[API 응답 ms 평균/p95] " + ", ".join(f"{p.split('/')[-1]} {a:.0f}/{b:.0f}" for p, (a, b) in report.items()))
    assert max(v[1] for v in report.values()) < 100, report


def test_signup_and_login_under_250ms_over_http(http):
    """Metrics: 가입 · 로그인은 bcrypt 비용 때문에 250ms 이내."""
    s = time.perf_counter()
    u = new_user(http, "측정")
    signup_ms = (time.perf_counter() - s) * 1000
    ms = []
    for _ in range(5):
        s = time.perf_counter()
        r = http.post("/api/auth/login", json={"email": u.email, "password": PW})
        ms.append((time.perf_counter() - s) * 1000)
        assert r.status_code == 200
    print(f"\n[인증 ms] 가입 {signup_ms:.0f}, 로그인 평균 {statistics.mean(ms):.0f} 최대 {max(ms):.0f}")
    assert signup_ms < 250 and max(ms) < 250


def test_data_survives_a_server_restart(server, http):
    """파일 DB: 서버를 껐다 켜도 계정 · 팀 · 회의록이 남는다."""
    leader, _, team = new_team(http)
    m = leader.post(f"/api/teams/{team['id']}/meetings", json={
        "title": "재시작 전 회의", "met_at": "2026-09-24T05:00:00Z", "attendees": "김대리", "body": "남아야 하는 본문"}).json()
    server.stop()
    server.start(keep_db=True)
    with httpx.Client(base_url=server.base, timeout=30) as c:
        r = c.post("/api/auth/login", json={"email": leader.email, "password": PW})
        assert r.status_code == 200
        h = {"Authorization": f"Bearer {r.json()['token']}"}
        got = c.get(f"/api/meetings/{m['id']}", headers=h).json()
        assert got["title"] == "재시작 전 회의" and got["body"] == "남아야 하는 본문"
        assert len(c.get(f"/api/teams/{team['id']}/members", headers=h).json()) == 3
        # 같은 JWT_SECRET 이라 재시작 전에 받은 토큰도 계속 유효하다
        assert c.get("/api/auth/me", headers={"Authorization": f"Bearer {leader.token}"}).status_code == 200
