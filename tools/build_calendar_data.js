// Build runtime/kongflow_months.tsv: the first day of every Chinese month, 221 BCE – 2100 CE.
//
// Source: ytliu0/ChineseCalendar (GPL-3.0), index_c.js — Yuk Tung Liu's computed historical
// Chinese calendars (with the dynasties' own calendar rules). Download it next to this script
// or pass its path:  node tools/build_calendar_data.js /path/to/index_c.js
// Output columns: Julian Day Number of day 1, Chinese year (labelled by its Gregorian/Julian
// year, BCE negative), month number (negative = leap month), days in the month.
const vm = require('vm'), fs = require('fs'), path = require('path');
const source = process.argv[2] || path.join(__dirname, 'index_c.js');
const stub = new Proxy(function () {}, { get: (t, k) => (k === 'length' ? 0 : stub), apply: () => stub, construct: () => stub, set: () => true });
const ctx = { console, Math, document: stub, window: stub, navigator: { userAgent: '' }, location: { search: '' }, setTimeout: () => {}, addEventListener: () => {} };
vm.createContext(ctx);
vm.runInContext(fs.readFileSync(source, 'utf8'), ctx);
const months = new Map();
for (let y = -220; y <= 2100; y++) {
  if (y === 0) continue;                     // the data uses astronomical numbering below
  const astro = y < 0 ? y + 1 : y;
  const r = vm.runInContext(`calDataYear(${astro}, langConstant(1))`, ctx);
  for (let i = 0; i < r.cmonthDate.length; i++) {
    const jdn = r.jd0 + r.cmonthDate[i] + 1;  // jd0 is the day before 1 January; cmonthDate counts 1 January as 1
    let year = astro + r.cmonthYear[i] - 1;   // cmonthYear 0 = the Chinese year before
    if (year <= 0) year -= 1;                  // back to historical numbering (no year 0)
    months.set(jdn, [jdn, year, r.cmonthNum[i], r.cmonthLong[i] ? 30 : 29]);
  }
}
const rows = [...months.values()].sort((a, b) => a[0] - b[0]);
for (let i = 0; i + 1 < rows.length; i++) {
  const gap = rows[i + 1][0] - rows[i][0];
  if (gap !== rows[i][3]) rows[i][3] = gap;   // trust the next month's start over the length flag
}
fs.writeFileSync(path.join(__dirname, '..', 'runtime', 'kongflow_months.tsv'), rows.map(r => r.join('\t')).join('\n') + '\n');
console.log(rows.length + ' months');
