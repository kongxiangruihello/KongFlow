-- 字号互查：输入字号或别号的全拼，在首选之后列出本名；输入本名的全拼，列出其字号。
--   yangming → 王守仁（号阳明）       wangshouren → 阳明（号）、伯安（字）
-- 数据：kongflow_names.tsv（全拼、候选文字、注释），由设置程序根据你导入的人名表生成。
local M = {}

function M.init(env)
  env.map = {}
  local f = io.open(rime_api.get_user_data_dir() .. '/kongflow_names.tsv', 'r')
  if not f then return end
  for line in f:lines() do
    local key, text, note = line:match('^([a-z]+)\t([^\t]+)\t(.*)$')
    if key then
      env.map[key] = env.map[key] or {}
      table.insert(env.map[key], { text = text, note = note })
    end
  end
  f:close()
end

function M.func(input, env)
  local code = env.engine.context.input
  local extra = env.map[code]
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
