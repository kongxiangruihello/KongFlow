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

class V040MenuTests(unittest.TestCase):
 def test_candidate_menu_opens_above_panel(self):
  s=(core.ROOT/'client/sources/SquirrelPanel.swift').read_text()
  i=s.index('menu.popUp(positioning: nil, at: NSEvent.mouseLocation, in: nil)')
  before=s[i-400:i];after=s[i:i+200]
  self.assertIn('level = NSWindow.Level(rawValue: NSWindow.Level.popUpMenu.rawValue - 1)',before)
  self.assertIn('level = savedLevel',after)

class V040QuickActionPathTests(unittest.TestCase):
 def test_client_uses_the_real_helper_name(self):
  import glob
  for f in glob.glob(str(core.ROOT/'client/sources/*.swift')):
   self.assertNotIn('KongIME设置.app',open(f).read(),f)
  self.assertIn("helper=client/'Contents/Helpers/KongFlow设置.app'",(core.ROOT/'build_integrated.py').read_text())
  q=(core.ROOT/'client/sources/QuickActionController.swift').read_text()
  self.assertIn('SquirrelApplicationDelegate.managerFolder.appendingPathComponent("quick.py")',q)
