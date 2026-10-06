-- 典籍原文速输（前缀 v）：输入句子（或任一分句）开头几个字的拼音首字母。
--   vxesx → 学而时习之，不亦说乎？    论语·学而 1.1
-- 收录四书、诗经、楚辞、唐诗三百首、蒙学，以及用户在设置里导入的典籍。
-- 数据：kongflow_classics.tsv 与 kongflow_classics_user.tsv
--   （首字母、原文、出处（引用形式，如《论语·学而》）、位置说明、1=句首 2=分句起）。
-- 引文带出处：方案 kongflow_classics/cite 为 paren 时上屏「……（《论语·学而》）」，
--   dash 时上屏「……——《论语·学而》」，none 时只上屏原文；另一种形式作为第二候选。
local M = {}

-- 数据按文件整体读成一个字符串，首次输入 v 时才读取。
-- 早先把约三万行拆成三万个 Lua 表常驻内存，Lua 的垃圾回收每次都要遍历它们，
-- 使所有按键（哪怕不用典籍速输）都慢了约 20 毫秒；一个大字符串对回收器只是一个对象。
local function read(path)
  local f = io.open(path, 'r')
  if not f then return '' end
  local text = f:read('a')
  f:close()
  return text
end

function M.init(env)
  env.data = nil
  local ok, style = pcall(function() return env.engine.schema.config:get_string('kongflow_classics/cite') end)
  env.cite = ok and style or 'none'
end

local function data(env)
  if not env.data then
    local dir = rime_api.get_user_data_dir()
    -- The user's own texts first; a leading newline lets every line be found as "\n" .. code.
    env.data = { '\n' .. read(dir .. '/kongflow_classics_user.tsv'), '\n' .. read(dir .. '/kongflow_classics.tsv') }
  end
  return env.data
end

local function cited(row, style)
  if row.cite == '' or style == 'none' then return row.text end
  if style == 'dash' then return row.text .. '——' .. row.cite end
  return row.text .. '（' .. row.cite .. '）'
end

-- Rows whose code starts with `code`, in file order: sentence starts first, then clause starts.
local function lookup(env, code, limit)
  local first, later = {}, {}
  local needle = '\n' .. code
  for _, blob in ipairs(data(env)) do
    local pos = 1
    while #first < limit or #later < limit do
      local s, e = blob:find(needle, pos, true)
      if not s then break end
      local stop = blob:find('\n', e + 1, true) or (#blob + 1)
      local c, text, cite, src, rank = blob:sub(s + 1, stop - 1):match('^([^\t]+)\t([^\t]+)\t([^\t]*)\t([^\t]*)\t(%d)')
      if c then
        local bucket = rank == '1' and first or later
        if #bucket < limit then bucket[#bucket + 1] = { text = text, cite = cite, src = src } end
      end
      pos = stop
    end
  end
  return first, later
end

function M.func(input, seg, env)
  if not seg:has_tag('kongflow_classics') then return end
  local code = input:sub(2)
  -- Older librime-lua builds cannot set the prompt; it is only a hint.
  pcall(function() seg.prompt = '〔典籍〕句首拼音首字母' end)
  if #code < 2 then return end
  local first, later = lookup(env, code, 40)
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
