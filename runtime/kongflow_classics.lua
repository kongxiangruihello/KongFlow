-- 四书原文速输（前缀 v）：输入句子（或任一分句）开头几个字的拼音首字母。
--   vxesxz → 学而时习之，不亦说乎？    论语·学而 1.1
-- 数据：kongflow_classics.tsv（首字母、原文、出处、1=句首 2=分句起）。
local M = {}

function M.init(env)
  env.rows = {}
  local f = io.open(rime_api.get_user_data_dir() .. '/kongflow_classics.tsv', 'r')
  if not f then return end
  for line in f:lines() do
    local code, text, src, rank = line:match('^([^\t]+)\t([^\t]+)\t([^\t]+)\t(%d)$')
    if code then env.rows[#env.rows + 1] = { code = code, text = text, src = src, rank = tonumber(rank) } end
  end
  f:close()
end

function M.func(input, seg, env)
  if not seg:has_tag('kongflow_classics') then return end
  local code = input:sub(2)
  -- Older librime-lua builds cannot set the prompt; it is only a hint.
  pcall(function() seg.prompt = '〔四书〕句首拼音首字母' end)
  if #code < 2 then return end
  local first, later = {}, {}
  for _, row in ipairs(env.rows) do
    if row.code:sub(1, #code) == code then
      local bucket = row.rank == 1 and first or later
      if #bucket < 60 then bucket[#bucket + 1] = row end
    end
  end
  local shown = 0
  for _, list in ipairs({ first, later }) do
    for _, row in ipairs(list) do
      shown = shown + 1
      if shown > 60 then return end
      yield(Candidate('kongflow_classics', seg.start, seg._end, row.text, row.src))
    end
  end
end

return M
