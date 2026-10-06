import re,unittest
import core

class V040LatencyTests(unittest.TestCase):
 """Large data must not live in Lua as thousands of small tables: the garbage collector walks
 them on every keystroke (measured ~20 ms/key with 30,000 典籍 rows, ~0.8 ms/key after)."""
 def lua(self,name):return (core.ROOT/'runtime'/name).read_text()
 def test_classics_kept_as_strings_and_loaded_lazily(self):
  s=self.lua('kongflow_classics.lua')
  self.assertNotIn('rows[#rows + 1]',s)
  init=s[s.index('function M.init'):s.index('\nend',s.index('function M.init'))]
  self.assertNotIn('io.open',init);self.assertNotIn('read(',init)
  self.assertIn("blob:find(needle, pos, true)",s)
 def test_names_kept_as_string(self):
  s=self.lua('kongflow_names.lua')
  self.assertNotIn('env.map',s);self.assertIn("data:find(needle, pos, true)",s)
 def test_month_table_packed(self):
  s=self.lua('kongflow_era.lua')
  self.assertIn("string.pack(RECORD",s);self.assertIn("string.unpack(RECORD",s)
  self.assertNotIn('m.jd[#m.jd + 1]',s)
