// MeetingNote Pro 공통 테마 - 모든 화면이 같은 토큰을 쓰도록 한 곳에 모음
// 라이트 = 시안 A 액센트 스트라이프 (카드 무채색, 색은 좌측 6px 띠와 라벨에만)
// 다크  = 시안 C 블랙 캔버스 (같은 구조에 배경만 뒤집음)
// 팔레트는 themes.html 비비드 9색. dot = 원색, text = 흰 배경용 어두운 값
tailwind.config = {
  darkMode: "class",
  theme: {
    extend: {
      fontFamily: {
        sans: ['-apple-system','BlinkMacSystemFont','Segoe UI','Pretendard','Malgun Gothic','sans-serif']
      },
      colors: {
        page: "#f4f5f6",
        ink:  { DEFAULT:"#141414", 2:"#55595f", 3:"#8b9097" },
        line: "#e4e6e9",
        canvas:  "#0d0d0f",
        surface: "#17181c",
        chip:    "#1c1e23",
        fg:      "#f2f3f5",
        dim:     "#7c828b",
        edge:    "#23252a",
        blue:   { dot:"#4CA0E5", text:"#1565B0" },
        orange: { dot:"#EF8B22", text:"#A65A00" },
        green:  { dot:"#00A65A", text:"#007A42" },
        red:    { dot:"#E1232B", text:"#C21620" },
        purple: { dot:"#7C40A2", text:"#6B3590" }
      }
    }
  }
};

// ── 공통 클래스 (문자열 상수) ──────────────────────────────
// 새 화면을 만들 때 이 값을 그대로 쓴다. 임의 조합 금지
window.UI = {
  // 입력
  input:  "w-full h-11 px-3.5 rounded-xl bg-page dark:bg-chip border border-line dark:border-edge " +
          "text-sm placeholder:text-ink-3 dark:placeholder:text-dim " +
          "focus:outline-none focus:border-blue-dot focus:ring-2 focus:ring-blue-dot/25 transition",
  label:  "block text-xs font-bold mb-1.5",
  help:   "mt-1.5 text-[11px] text-ink-3 dark:text-dim",
  errText:"mt-1.5 text-[11px] font-semibold text-red-text dark:text-red-dot",

  // 버튼
  btnPrimary: "h-11 px-4 rounded-xl bg-ink dark:bg-fg text-white dark:text-canvas text-sm font-bold " +
              "hover:opacity-90 active:scale-[.99] disabled:opacity-60 transition",
  btnGhost:   "h-11 px-4 rounded-xl bg-white dark:bg-chip border border-line dark:border-edge " +
              "text-sm font-bold hover:border-ink dark:hover:border-dim transition",
  btnDanger:  "h-11 px-4 rounded-xl bg-red-dot text-white text-sm font-bold hover:opacity-90 transition",

  // 카드 / 패널
  panel: "rounded-2xl bg-white dark:bg-surface border border-line dark:border-edge",
  card:  "rounded-xl bg-white dark:bg-surface border border-line dark:border-edge",

  // 배지
  badge: "px-2.5 py-1 rounded-md text-[11px] font-extrabold tracking-wide"
};

// 상태색 - 좌측 6px 띠 + 라벨. 카드 배경은 항상 무채색
window.STRIPE = {
  blue:   "border-l-[6px] border-l-blue-dot dark:border-l-blue-dot",
  orange: "border-l-[6px] border-l-orange-dot dark:border-l-orange-dot",
  green:  "border-l-[6px] border-l-green-dot dark:border-l-green-dot",
  red:    "border-l-[6px] border-l-red-dot dark:border-l-red-dot",
  purple: "border-l-[6px] border-l-purple-dot dark:border-l-purple-dot"
};
window.LABEL = {
  blue:   "text-blue-text dark:text-blue-dot",
  orange: "text-orange-text dark:text-orange-dot",
  green:  "text-green-text dark:text-green-dot",
  red:    "text-red-text dark:text-red-dot",
  purple: "text-purple-text dark:text-purple-dot"
};

// 알림 박스 - 좌측 띠로 종류 구분
window.notice = (kind, title, body) => `
  <div class="rounded-xl bg-white dark:bg-surface border border-line dark:border-edge ${window.STRIPE[kind]} px-4 py-3">
    <p class="text-[13px] font-bold ${window.LABEL[kind]}">${title}</p>
    ${body ? `<p class="text-[12px] text-ink-2 dark:text-dim mt-0.5">${body}</p>` : ""}
  </div>`;

// 테마 토글 - localStorage('theme'), 초기값 prefers-color-scheme
window.initTheme = function (onChange) {
  const root = document.documentElement;
  const saved = localStorage.getItem("theme");
  root.classList.toggle("dark",
    saved ? saved === "dark" : matchMedia("(prefers-color-scheme: dark)").matches);
  const btn = document.getElementById("themeBtn");
  if (btn) btn.onclick = () => {
    localStorage.setItem("theme", root.classList.toggle("dark") ? "dark" : "light");
    if (onChange) onChange();
  };
};

window.THEME_BTN = `
  <button id="themeBtn" class="w-8 h-8 grid place-items-center rounded-lg hover:bg-page dark:hover:bg-edge transition" aria-label="테마 전환">
    <svg class="w-4 h-4 hidden dark:block" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><circle cx="12" cy="12" r="4"/><path d="M12 2v2M12 20v2M4.9 4.9l1.4 1.4M17.7 17.7l1.4 1.4M2 12h2M20 12h2M4.9 19.1l1.4-1.4M17.7 6.3l1.4-1.4"/></svg>
    <svg class="w-4 h-4 block dark:hidden" fill="none" stroke="currentColor" stroke-width="2" viewBox="0 0 24 24"><path d="M21 12.8A9 9 0 1111.2 3a7 7 0 009.8 9.8z"/></svg>
  </button>`;

// ── 상태 전환 바 ──────────────────────────────────────────
// 퍼블리싱 확인용. 실제 구현에는 넣지 않는다
window.stateBar = function (states, onPick) {
  const bar = document.createElement("div");
  bar.className = "sticky top-0 z-50 bg-purple-dot text-white";
  bar.innerHTML = `
    <div class="max-w-7xl mx-auto px-3 py-1.5 flex items-center gap-2 overflow-x-auto">
      <span class="text-[10px] font-extrabold tracking-widest shrink-0 opacity-80">STATE</span>
      <div class="flex gap-1" id="stateBtns"></div>
      <span class="ml-auto shrink-0 text-[10px] opacity-70">퍼블리싱 확인용. 구현 시 제거</span>
    </div>`;
  document.body.prepend(bar);
  const wrap = bar.querySelector("#stateBtns");
  states.forEach((s, i) => {
    const b = document.createElement("button");
    b.textContent = s.label;
    b.dataset.i = i;
    b.className = "px-2.5 py-1 rounded-md text-[11px] font-bold whitespace-nowrap transition";
    wrap.appendChild(b);
  });
  const sync = (idx) => {
    [...wrap.children].forEach((b, i) => {
      b.className = "px-2.5 py-1 rounded-md text-[11px] font-bold whitespace-nowrap transition " +
        (i === idx ? "bg-white text-purple-text" : "bg-white/15 hover:bg-white/25");
    });
  };
  wrap.addEventListener("click", (e) => {
    const b = e.target.closest("button");
    if (!b) return;
    const i = +b.dataset.i;
    sync(i);
    onPick(states[i].key, i);
  });
  sync(0);
  onPick(states[0].key, 0);
};
