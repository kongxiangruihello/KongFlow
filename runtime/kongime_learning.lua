-- Keep the already ranked candidates, but detach their learnable Phrase identity.
-- SimpleCandidate commits are ignored by librime Memory::ProcessSegmentOnCommit.
-- Do not use ShadowCandidate: it unwraps to the original learnable phrase.
local M = {}
function M.func(input, env)
  local paused = env.engine.context:get_option('kongime_pause_learning')
  for candidate in input:iter() do
    if paused then
      local copy = Candidate(candidate.type, candidate.start, candidate._end, candidate.text, candidate.comment)
      copy.quality = candidate.quality
      copy.preedit = candidate.preedit
      yield(copy)
    else
      yield(candidate)
    end
  end
end
return M
