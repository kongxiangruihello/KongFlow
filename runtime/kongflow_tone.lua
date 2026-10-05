-- 带声调拼音（前缀 /）：数字标调转为调号。
--   /lun2yu3 → lúnyǔ · lún yǔ · Lúnyǔ      v 表示 ü：/lv4 → lǜ；5 或 0 为轻声。
-- 只单独一个 / 时输出 / 本身。
local M = {}

local MARKS = {
  a = { 'ā', 'á', 'ǎ', 'à' }, e = { 'ē', 'é', 'ě', 'è' }, i = { 'ī', 'í', 'ǐ', 'ì' },
  o = { 'ō', 'ó', 'ǒ', 'ò' }, u = { 'ū', 'ú', 'ǔ', 'ù' }, ['ü'] = { 'ǖ', 'ǘ', 'ǚ', 'ǜ' },
}

-- Standard placement: a or e takes the mark; in "ou" the o; otherwise the last vowel.
local function mark(syllable, tone)
  syllable = syllable:gsub('v', 'ü')
  if tone < 1 or tone > 4 then return syllable end
  local target
  if syllable:find('a') then target = 'a'
  elseif syllable:find('e') then target = 'e'
  elseif syllable:find('ou') then target = 'o'
  else
    -- last vowel (ü is two bytes; scan characters)
    for _, ch in utf8.codes(syllable) do
      local c = utf8.char(ch)
      if MARKS[c] then target = c end
    end
  end
  if not target then return syllable end
  local pos = syllable:find(target, 1, true)
  if target ~= 'a' and target ~= 'e' and target ~= 'o' then
    -- for the last-vowel rule replace the last occurrence
    local from = 1
    while true do
      local p = syllable:find(target, from, true)
      if not p then break end
      pos = p; from = p + 1
    end
  end
  return syllable:sub(1, pos - 1) .. MARKS[target][tone] .. syllable:sub(pos + #target)
end

function M.func(input, seg, env)
  if not seg:has_tag('kongflow_tone') then return end
  -- Older librime-lua builds cannot set the prompt; it is only a hint.
  pcall(function() seg.prompt = '〔注音〕拼音后加 1–4 标调，v 为 ü' end)
  local code = input:sub(2)
  if code == '' then
    yield(Candidate('kongflow_tone', seg.start, seg._end, '/', ''))
    return
  end
  local parts = {}
  for letters, tone in code:gmatch('([a-z]+)(%d?)') do
    parts[#parts + 1] = mark(letters, tonumber(tone) or 0)
  end
  if #parts == 0 then return end
  -- Pinyin orthography: an apostrophe before a, o, e that start a later syllable (nǚ'ér, Xī'ān).
  local glued = { parts[1] }
  for i = 2, #parts do
    local head = parts[i]:sub(1, 1)
    local vowel = head == 'a' or head == 'o' or head == 'e' or parts[i]:match('^[\195\196\199]')
      and (parts[i]:find('^ā') or parts[i]:find('^á') or parts[i]:find('^ǎ') or parts[i]:find('^à')
        or parts[i]:find('^ō') or parts[i]:find('^ó') or parts[i]:find('^ǒ') or parts[i]:find('^ò')
        or parts[i]:find('^ē') or parts[i]:find('^é') or parts[i]:find('^ě') or parts[i]:find('^è'))
    glued[#glued + 1] = (vowel and "'" or '') .. parts[i]
  end
  local joined = table.concat(glued)
  local spaced = table.concat(parts, ' ')
  yield(Candidate('kongflow_tone', seg.start, seg._end, joined, '注音'))
  if #parts > 1 then yield(Candidate('kongflow_tone', seg.start, seg._end, spaced, '分写')) end
  if joined:match('^[a-z]') then
    yield(Candidate('kongflow_tone', seg.start, seg._end, joined:sub(1, 1):upper() .. joined:sub(2), '首字母大写'))
  end
end

return M
