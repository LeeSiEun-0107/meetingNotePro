// MeetingNote Pro 공통 호출 래퍼 - 모든 화면이 이 한 곳으로만 서버를 부른다
//   토큰 헤더, {code, msg} 오류 풀기, 401 TOKEN_EXPIRED 처리, 공통 오류 알림을 맡는다
//   색과 클래스는 theme.js 의 window.notice 만 쓴다 (새 색 · 새 화면 없음)
(function () {
  const TOKEN_KEY = "mn_token";

  const store = {
    get: () => { try { return localStorage.getItem(TOKEN_KEY); } catch (e) { return null; } },
    set: (t) => { try { localStorage.setItem(TOKEN_KEY, t); } catch (e) {} },
    clear: () => { try { localStorage.removeItem(TOKEN_KEY); } catch (e) {} }
  };

  // 토큰을 지우고 로그인 화면으로. expired 면 로그인 화면이 세션 만료 안내를 띄운다
  function toLogin(expired) {
    store.clear();
    meCache = null;
    location.href = "/login.html" + (expired ? "?expired=1" : "");
  }

  // 화면 위쪽 오른쪽에 뜨는 공통 알림. 5초 뒤 사라진다
  let toastTimer = null;
  function toast(kind, title, body) {
    let box = document.getElementById("apiToast");
    if (!box) {
      box = document.createElement("div");
      box.id = "apiToast";
      box.className = "fixed top-16 right-4 z-50 w-[min(22rem,calc(100vw-2rem))]";
      document.body.appendChild(box);
    }
    box.innerHTML = window.notice(kind, title, body);
    clearTimeout(toastTimer);
    toastTimer = setTimeout(() => { box.innerHTML = ""; }, 5000);
  }

  // 예외를 사람이 읽는 한 줄 오류 알림으로
  function showError(e, title) {
    toast("red", title || "처리하지 못함", (e && e.msg) || "잠시 뒤 다시 시도해 주세요");
  }

  // method, path, body(JSON 객체 또는 FormData). opts.keepAuth 면 401 UNAUTHORIZED 로 쫓아내지 않는다
  async function call(method, path, body, opts) {
    opts = opts || {};
    const headers = {};
    const t = store.get();
    if (t) headers["Authorization"] = "Bearer " + t;
    let payload;
    if (body instanceof FormData) payload = body;
    else if (body !== undefined && body !== null) {
      headers["Content-Type"] = "application/json";
      payload = JSON.stringify(body);
    }
    let res;
    try {
      res = await fetch(path, { method, headers, body: payload });
    } catch (netErr) {
      const e = { code: "NETWORK_ERROR", msg: "서버에 연결하지 못함. 네트워크를 확인해 주세요", status: 0 };
      if (!opts.quiet) showError(e);
      throw e;
    }
    if (res.status === 204) return null;
    let data = null;
    try { data = await res.json(); } catch (parseErr) { data = null; }
    if (res.ok) return data;

    const e = {
      code: (data && data.code) || "SERVER_ERROR",
      msg: (data && data.msg) || "서버 오류가 났음",
      status: res.status
    };
    // 배포 플랫폼이 앱에 닿기 전에 본문 없이 413 으로 거절하는 경우도 같은 안내로 읽는다
    if (res.status === 413 && !(data && data.code)) { e.code = "PAYLOAD_TOO_LARGE"; e.msg = "4.4MB 를 넘는 파일"; }
    if (e.code === "TOKEN_EXPIRED") { toLogin(true); throw e; }
    if (e.code === "UNAUTHORIZED" && !opts.keepAuth) { toLogin(false); throw e; }
    if (!opts.quiet && e.status >= 500) showError(e);
    throw e;
  }

  const api = {
    token: store,
    toLogin, toast, showError,
    get: (p, o) => call("GET", p, undefined, o),
    post: (p, b, o) => call("POST", p, b, o),
    put: (p, b, o) => call("PUT", p, b, o),
    del: (p, o) => call("DELETE", p, undefined, o)
  };

  // 내 정보 (소속 팀 id · 팀 이름 · 역할 포함). 화면마다 한 번만 부른다
  let meCache = null;
  api.me = async function (force) {
    if (!force && meCache) return meCache;
    meCache = await api.get("/api/auth/me");
    return meCache;
  };
  api.forgetMe = () => { meCache = null; };

  // 로그인 안 했으면 로그인으로, 팀이 없으면 팀 설정 화면으로 보낸다 (스토리보드 F-02)
  api.requireLogin = async function () {
    if (!store.get()) { toLogin(false); return new Promise(() => {}); }
    return api.me();
  };
  api.requireTeam = async function () {
    const me = await api.requireLogin();
    if (!me.team_id) { location.href = "/team.html"; return new Promise(() => {}); }
    return me;
  };

  window.API = api;

  // ── 시각 · 기한 도우미 ──────────────────────────────────────
  const pad = (n) => String(n).padStart(2, "0");

  // 서버는 UTC ISO 8601. 화면은 현지 시간으로 보여 준다
  window.fmt = {
    dt: (iso) => {
      const d = new Date(iso);
      return `${d.getFullYear()}-${pad(d.getMonth() + 1)}-${pad(d.getDate())} ${pad(d.getHours())}:${pad(d.getMinutes())}`;
    },
    // 서버가 받는 ISO UTC 로 (datetime-local 값은 현지 시간)
    toIso: (local) => new Date(local).toISOString().replace(/\.\d{3}Z$/, "Z"),
    // 활동 기록용: 오늘 14:12 · 어제 17:40 · 9월 18일
    when: (iso) => {
      const d = new Date(iso), now = new Date();
      const day = (x) => new Date(x.getFullYear(), x.getMonth(), x.getDate()).getTime();
      const diff = Math.round((day(now) - day(d)) / 86400000);
      const hm = `${pad(d.getHours())}:${pad(d.getMinutes())}`;
      if (diff === 0) return "오늘 " + hm;
      if (diff === 1) return "어제 " + hm;
      return `${d.getMonth() + 1}월 ${d.getDate()}일`;
    }
  };

  // 기한 지남 판정 (화면이 한다. 서버는 due_text 를 비교하지 않는다)
  //   · 어제 / 지난 주 / 지난 달 이 들어 있으면 지남
  //   · N월 N일 은 회의록 met_at 의 연도로 오늘과 비교. 해를 넘기는 날짜는 다루지 않는다
  //   · 완료는 항상 제외. 그 밖의 글자(미정 · 다음 주 금요일 · 이번 주 안)는 판정하지 않는다
  window.isLate = function (dueText, status, metAt, now) {
    if (status === "DONE" || !dueText) return false;
    if (/어제|지난\s*주|지난\s*달/.test(dueText)) return true;
    const m = dueText.match(/(\d{1,2})\s*월\s*(\d{1,2})\s*일/);
    if (!m) return false;
    const year = metAt ? new Date(metAt).getFullYear() : (now || new Date()).getFullYear();
    const due = new Date(year, +m[1] - 1, +m[2], 23, 59, 59);
    return due.getTime() < (now || new Date()).getTime();
  };
})();
