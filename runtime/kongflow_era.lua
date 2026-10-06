-- 年号与公元纪年互查（前缀 i）
--   i康熙拼音+年数   ikangxi20 / ikx20  → 康熙二十年（1681）
--   i年号拼音        ikangxi / ikx       → 康熙（清 1662–1722）
--   i公元年          i1681 → 该年所有年号；iq140 → 公元前 140 年
--   i年月日（8 位）  i16810315 → 康熙二十年正月廿六，附干支纪年、纪日；iq01400301 为公元前
--                    1582 年 10 月 15 日以前按儒略历理解（史学惯例），之后按格里历。
-- 农历月表：kongflow_months.tsv（月首儒略日数、农历年、月份（负数为闰月）、天数），
--   取自刘玉棠（Yuk Tung Liu）计算的历代历表（ytliu0/ChineseCalendar），公元前 221 年至公元 2100 年。
-- 数据：kongflow_eras.tsv（全拼、首字母、年号、起年、止年、朝代、君主、来源），公元前用负数，无公元 0 年。
-- 年份按“年号某年 ≈ 该公历年”对应，岁首差异（如农历年末）不作换算。
local M = {}

local STEMS = { '甲', '乙', '丙', '丁', '戊', '己', '庚', '辛', '壬', '癸' }
local BRANCHES = { '子', '丑', '寅', '卯', '辰', '巳', '午', '未', '申', '酉', '戌', '亥' }
local DIGITS = { '一', '二', '三', '四', '五', '六', '七', '八', '九' }

local function load(env)
  local rows = {}
  local path = rime_api.get_user_data_dir() .. '/kongflow_eras.tsv'
  local f = io.open(path, 'r')
  if not f then return rows end
  for line in f:lines() do
    local cols = {}
    for col in (line .. '\t'):gmatch('([^\t]*)\t') do cols[#cols + 1] = col end
    if #cols >= 6 and tonumber(cols[4]) and tonumber(cols[5]) then
      rows[#rows + 1] = { full = cols[1], abbr = cols[2], name = cols[3], s = tonumber(cols[4]), e = tonumber(cols[5]),
                          dyn = cols[6], ruler = cols[7] or '', source = cols[8] or '' }
    end
  end
  f:close()
  return rows
end

-- 月表约 2.9 万行，打包成一个二进制字符串（每月 8 字节：月首儒略日数、农历年、月份），
-- 用二分查找读取；不建成大量 Lua 表，以免拖慢每次按键的垃圾回收。
local RECORD = '<i4i2i2'
local SIZE = string.packsize(RECORD)

local function load_months()
  local parts = {}
  local f = io.open(rime_api.get_user_data_dir() .. '/kongflow_months.tsv', 'r')
  if not f then return '' end
  for line in f:lines() do
    local jd, y, mo = line:match('^(%d+)\t(-?%d+)\t(-?%d+)')
    if jd then parts[#parts + 1] = string.pack(RECORD, tonumber(jd), tonumber(y), tonumber(mo)) end
  end
  f:close()
  return table.concat(parts)
end

function M.init(env)
  env.rows = load(env)
end

-- Gregorian year from an era start and an ordinal, skipping the non-existent year 0.
local function add_years(start, n)
  local y = start + n - 1
  if start < 0 and y >= 0 then y = y + 1 end
  return y
end

local function ordinal(start, year)
  local n = year - start + 1
  if start < 0 and year > 0 then n = n - 1 end
  return n
end

local function year_text(y)
  if y < 0 then return '前' .. tostring(-y) end
  return tostring(y)
end

local function ganzhi(y)
  local a = y < 0 and y + 1 or y   -- astronomical year numbering
  local i = (a - 4) % 60
  return STEMS[i % 10 + 1] .. BRANCHES[i % 12 + 1]
end

local function numeral(n)
  if n == 1 then return '元' end
  if n < 10 then return DIGITS[n] end
  local tens, ones = math.floor(n / 10), n % 10
  local s = (tens == 1 and '' or DIGITS[tens]) .. '十'
  if ones > 0 then s = s .. DIGITS[ones] end
  return s
end

local function where(row)
  return row.dyn .. (row.ruler ~= '' and ('·' .. row.ruler) or '') .. (row.source == '明正朔' and '（据明正朔）' or '')
end

-- Julian Day Number; dates before 1582-10-15 are Julian, later ones Gregorian. y is astronomical.
local function jdn(y, m, d)
  local a = math.floor((14 - m) / 12)
  local yy, mm = y + 4800 - a, m + 12 * a - 3
  local base = d + math.floor((153 * mm + 2) / 5) + 365 * yy + math.floor(yy / 4)
  if y > 1582 or (y == 1582 and (m > 10 or (m == 10 and d >= 15))) then
    return base - math.floor(yy / 100) + math.floor(yy / 400) - 32045
  end
  return base - 32083
end

local function valid_date(y, m, d)
  if m < 1 or m > 12 or d < 1 then return false end
  local leap
  if y > 1582 then leap = (y % 4 == 0 and y % 100 ~= 0) or y % 400 == 0 else leap = y % 4 == 0 end
  local days = ({ 31, leap and 29 or 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31 })[m]
  if y == 1582 and m == 10 and d > 4 and d < 15 then return false end
  return d <= days
end

local MONTHS = { '正', '二', '三', '四', '五', '六', '七', '八', '九', '十', '十一', '十二' }
local function month_name(n)
  return (n < 0 and '闰' or '') .. MONTHS[math.abs(n)] .. '月'
end

local function day_name(d)
  if d <= 10 then return '初' .. ({ '一', '二', '三', '四', '五', '六', '七', '八', '九', '十' })[d] end
  if d < 20 then return '十' .. DIGITS[d - 10] end
  if d == 20 then return '二十' end
  if d < 30 then return '廿' .. DIGITS[d - 20] end
  return '三十'
end

local function day_ganzhi(j)
  local i = (j + 49) % 60
  return STEMS[i % 10 + 1] .. BRANCHES[i % 12 + 1]
end

-- Chinese date of a Julian Day Number: year label, month number (negative = leap), day.
local function chinese_date(m, j)
  local n = #m // SIZE
  local function at(i) return string.unpack(RECORD, m, (i - 1) * SIZE + 1) end
  if n == 0 or j < at(1) or j >= at(n) + 30 then return nil end
  local lo, hi = 1, n
  while lo < hi do
    local mid = (lo + hi + 1) // 2
    if at(mid) <= j then lo = mid else hi = mid - 1 end
  end
  local jd, year, month = at(lo)
  return year, month, j - jd + 1
end

function M.func(input, seg, env)
  if not seg:has_tag('kongflow_era') then return end
  local code = input:sub(2)
  -- Older librime-lua builds cannot set the prompt; it is only a hint.
  pcall(function() seg.prompt = '〔年号纪年〕拼音+年数，或公元年（前用 q）' end)
  if code == '' then return end
  local count = 0
  local function emit(text, comment)
    count = count + 1
    if count <= 40 then yield(Candidate('kongflow_era', seg.start, seg._end, text, comment)) end
  end

  local bce, digits = code:match('^(q?)(%d+)$')
  if digits and #digits == 8 then
    local y, mo, d = tonumber(digits:sub(1, 4)), tonumber(digits:sub(5, 6)), tonumber(digits:sub(7, 8))
    if bce == 'q' then y = -y end
    if y == 0 then return end
    local astro = y < 0 and y + 1 or y
    if not valid_date(astro, mo, d) then return end
    env.months = env.months or load_months()
    local j = jdn(astro, mo, d)
    local cy, cm, cd = chinese_date(env.months, j)
    local calendar = (y > 1582 or (y == 1582 and (mo > 10 or (mo == 10 and d >= 15)))) and '公历' or '儒略历'
    local western = year_text(y) .. '年' .. mo .. '月' .. d .. '日（' .. calendar .. '）'
    if not cy then
      emit(day_ganzhi(j) .. '日', western .. '  超出农历表范围（前221—2100）')
      return
    end
    local md = month_name(cm) .. day_name(cd)
    for _, row in ipairs(env.rows) do
      if row.s <= cy and cy <= row.e then
        emit(row.name .. numeral(ordinal(row.s, cy)) .. '年' .. md, where(row) .. '  ' .. western)
      end
    end
    emit(ganzhi(cy) .. '年' .. md, western)
    emit(day_ganzhi(j) .. '日', '日干支  ' .. western)
    return
  end
  if digits and #digits <= 4 then
    local y = tonumber(digits)
    if bce == 'q' then y = -y end
    if y == 0 then return end
    for _, row in ipairs(env.rows) do
      if row.s <= y and y <= row.e then
        local n = ordinal(row.s, y)
        emit(row.name .. numeral(n) .. '年（' .. year_text(y) .. '）', where(row) .. '  ' .. ganzhi(y))
      end
    end
    emit(year_text(y) .. '年（' .. ganzhi(y) .. '）', '干支')
    return
  end

  local letters, number = code:match('^([a-z]+)(%d*)$')
  if not letters then return end
  local exact, prefix = {}, {}
  for _, row in ipairs(env.rows) do
    if row.full == letters or row.abbr == letters then
      exact[#exact + 1] = row
    elseif row.full:sub(1, #letters) == letters then
      prefix[#prefix + 1] = row
    end
  end
  local n = tonumber(number)
  for _, list in ipairs({ exact, prefix }) do
    for _, row in ipairs(list) do
      if n then
        local y = add_years(row.s, n)
        if n >= 1 and y <= row.e then
          emit(row.name .. numeral(n) .. '年（' .. year_text(y) .. '）', where(row) .. '  ' .. ganzhi(y))
        end
      else
        emit(row.name, where(row) .. '  ' .. year_text(row.s) .. (row.e ~= row.s and ('–' .. year_text(row.e)) or ''))
      end
    end
  end
end

return M
