-- 字号互查：输入字号或别号的全拼，在首选之后列出本名；输入本名的全拼，列出其字号。
--   yangming → 王守仁（号阳明）       wangshouren → 阳明（号）、伯安（字）
-- 数据：kongflow_names.tsv（全拼、候选文字、注释），由设置程序根据你导入的人名表生成。
local M = {}

-- 人名表读成一个字符串，按需查找（不拆成大量 Lua 表，以免拖慢每次按键的垃圾回收）。
function M.init(env)
  env.data = '\n'
  local f = io.open(rime_api.get_user_data_dir() .. '/kongflow_names.tsv', 'r')
  if f then
    env.data = '\n' .. f:read('a')
    f:close()
  end
end

local function lookup(data, code)
  local found, pos, needle = {}, 1, '\n' .. code .. '\t'
  while true do
    local s, e = data:find(needle, pos, true)
    if not s then break end
    local stop = data:find('\n', e + 1, true) or (#data + 1)
    local text, note = data:sub(e + 1, stop - 1):match('^([^\t]+)\t(.*)$')
    if text then found[#found + 1] = { text = text, note = note } end
    pos = stop
  end
  return found
end

function M.func(input, env)
  local code = env.engine.context.input
  local extra = (code:match('^[a-z]+$') and #env.data > 1) and lookup(env.data, code) or nil
  local index = 0
  for cand in input:iter() do
    yield(cand)
    index = index + 1
    -- Only when the first candidate spans the whole input, so the inserted names replace all of it.
    if index == 1 and extra and cand.start == 0 and cand._end == #code then
      for _, e in ipairs(extra) do
        yield(Candidate('kongflow_name', cand.start, cand._end, e.text, e.note))
      end
    end
  end
end

return M
