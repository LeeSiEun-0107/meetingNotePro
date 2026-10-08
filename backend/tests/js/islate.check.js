// api.js 의 isLate 를 브라우저 없이 확인한다. 실패하면 종료 코드 1
const fs = require("fs");
const path = require("path");
global.window = {};
global.localStorage = { getItem() { return null; }, setItem() {}, removeItem() {} };
global.document = {};
const src = fs.readFileSync(path.join(__dirname, "..", "..", "..", "frontend", "api.js"), "utf8");
new Function("window", "localStorage", "document", "location", src)(window, localStorage, document, {});
const isLate = window.isLate;
const now = new Date(2026, 8, 25, 12, 0, 0); // 2026-09-25
const cases = [
  ["어제", "DOING", "2026-09-24T05:00:00Z", true],
  ["지난 주", "OPEN", null, true],
  ["지난 달", "OPEN", null, true],
  ["지난주", "OPEN", null, true],
  ["어제", "DONE", null, false],
  ["9월 12일", "OPEN", "2026-09-10T00:00:00Z", true],
  ["9월 12일", "DONE", "2026-09-10T00:00:00Z", false],
  ["9월 25일", "OPEN", "2026-09-10T00:00:00Z", false],   // 오늘 마감은 아직 지나지 않음
  ["9월 26일", "OPEN", "2026-09-10T00:00:00Z", false],
  ["다음 주 금요일", "OPEN", null, false],
  ["이번 주 안", "OPEN", null, false],
  ["미정", "OPEN", null, false],
  ["", "OPEN", null, false],
];
let bad = 0;
for (const [due, st, met, want] of cases) {
  const got = isLate(due, st, met, now);
  if (got !== want) { bad++; console.log("FAIL", JSON.stringify({ due, st, met, want, got })); }
}
const f = window.fmt;
if (!/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}Z$/.test(f.toIso("2026-09-18T10:30"))) { bad++; console.log("FAIL toIso"); }
if (bad) process.exit(1);
console.log("isLate ok", cases.length);
