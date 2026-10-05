-- 典籍原文速输（前缀 v）：输入句子（或任一分句）开头几个字的拼音首字母。
--   vxesx → 学而时习之，不亦说乎？    论语·学而 1.1
-- 收录四书、诗经、楚辞、唐诗三百首、蒙学，以及用户在设置里导入的典籍。
-- 数据：kongflow_classics.tsv 与 kongflow_classics_user.tsv
--   （首字母、原文、出处（引用形式，如《论语·学而》）、位置说明、1=句首 2=分句起）。
-- 引文带出处：方案 kongflow_classics/cite 为 paren 时上屏「……（《论语·学而》）」，
--   dash 时上屏「……——《论语·学而》」，none 时只上屏原文；另一种形式作为第二候选。
local M = {}

local function load(rows, path)
  local f = io.open(path, 'r')
  if not f then return end
  for line in f:lines() do
    local code, text, cite, src, rank = line:match('^([^\t]+)\t([^\t]+)\t([^\t]*)\t([^\t]*)\t(%d)$')
    if code then rows[#rows + 1] = { code = code, text = text, cite = cite, src = src, rank = tonumber(rank) } end
  end
  f:close()
end

function M.init(env)
  env.rows = {}
  local dir = rime_api.get_user_data_dir()
  load(env.rows, dir .. '/kongflow_classics_user.tsv')   -- the user's own texts first
  load(env.rows, dir .. '/kongflow_classics.tsv')
  local ok, style = pcall(function() return env.engine.schema.config:get_string('kongflow_classics/cite') end)
  env.cite = ok and style or 'none'
end

local function cited(row, style)
  if row.cite == '' or style == 'none' then return row.text end
  if style == 'dash' then return row.text .. '——' .. row.cite end
  return row.text .. '（' .. row.cite .. '）'
end

function M.func(input, seg, env)
  if not seg:has_tag('kongflow_classics') then return end
  local code = input:sub(2)
  -- Older librime-lua builds cannot set the prompt; it is only a hint.
  pcall(function() seg.prompt = '〔典籍〕句首拼音首字母' end)
  if #code < 2 then return end
  local first, later = {}, {}
  for _, row in ipairs(env.rows) do
    if row.code:sub(1, #code) == code then
      local bucket = row.rank == 1 and first or later
      if #bucket < 40 then bucket[#bucket + 1] = row end
    end
  end
  local shown = 0
  local alternate = env.cite == 'none' and 'paren' or 'none'
  for _, list in ipairs({ first, later }) do
    for _, row in ipairs(list) do
      shown = shown + 1
      if shown > 40 then return end
      yield(Candidate('kongflow_classics', seg.start, seg._end, cited(row, env.cite), row.src))
      if shown <= 3 and row.cite ~= '' then
        -- The other form, for the leading matches only, so the list stays short.
        yield(Candidate('kongflow_classics', seg.start, seg._end, cited(row, alternate), row.src))
      end
    end
  end
end

return M
