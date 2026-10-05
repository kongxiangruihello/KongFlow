-- 年号与公元纪年互查（前缀 i）
--   i康熙拼音+年数   ikangxi20 / ikx20  → 康熙二十年（1681）
--   i年号拼音        ikangxi / ikx       → 康熙（清 1662–1722）
--   i公元年          i1681 → 该年所有年号；iq140 → 公元前 140 年
-- 数据：kongflow_eras.tsv（全拼、首字母、年号、起年、止年、朝代、君主），公元前用负数，无公元 0 年。
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
    local full, abbr, name, s, e, dyn, ruler = line:match('^([^\t]*)\t([^\t]*)\t([^\t]*)\t(-?%d+)\t(-?%d+)\t([^\t]*)\t?(.*)$')
    if full then
      rows[#rows + 1] = { full = full, abbr = abbr, name = name, s = tonumber(s), e = tonumber(e), dyn = dyn, ruler = ruler }
    end
  end
  f:close()
  return rows
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
  return row.dyn .. (row.ruler ~= '' and ('·' .. row.ruler) or '')
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
  if digits then
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
