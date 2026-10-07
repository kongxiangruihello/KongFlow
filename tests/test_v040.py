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

class V040PersonalDictTests(unittest.TestCase):
 def setUp(self):
  import tempfile
  from pathlib import Path
  self.temp=tempfile.TemporaryDirectory();self.old=core.DATA;core.DATA=Path(self.temp.name)/'data'
 def tearDown(self):core.DATA=self.old;self.temp.cleanup()
 @unittest.skipUnless((core.ROOT/'vendor/rime-ice/cn_dicts/8105.dict.yaml').exists(),'需要雾凇词库')
 def test_low_library_weights_do_not_override_rime_ice(self):
  from pathlib import Path
  s=core.state()
  lib={'id':'a'*32,'name':'导入','hash':'x','enabled':True,'manual':False,'conflict_policy':None,'count':3,'review':0}
  rows=[{'word':'飞','pinyin':'fei','weight':2},{'word':'阳明心学讲义稿','pinyin':'yang ming xin xue jiang yi gao','weight':5},{'word':'非','pinyin':'fei','weight':99999999}]
  s['libraries']=[lib];s['personal']=[{'word':'肥','pinyin':'fei','weight':1,'pinned':False}]
  orig=core.lib_rows
  core.lib_rows=lambda l:rows
  try:out={(r['word'],r['pinyin']):r['weight'] for r in core.personal_dict_rows(s,['8105','base','ext'])}
  finally:core.lib_rows=orig
  self.assertNotIn(('飞','fei'),out)              # rime-ice weight is far higher: leave it to rime-ice
  self.assertEqual(out[('阳明心学讲义稿','yang ming xin xue jiang yi gao')],5) # new word: kept
  self.assertEqual(out[('非','fei')],99999999)     # library boosts above rime-ice: kept
  self.assertEqual(out[('肥','fei')],1)            # the user's own word: always kept

class V040FallbackFontTests(unittest.TestCase):
 def test_detect_and_font_face(self):
  import tempfile
  from pathlib import Path
  with tempfile.TemporaryDirectory() as t:
   d=Path(t)
   self.assertEqual(core.font_face({'fallback_font':'auto'},[d]),'PingFang SC')
   for n in ('PlangothicP1-Regular.otf','PlangothicP2-Regular.otf','HanaMinA.ttf'):(d/n).write_bytes(b'')
   self.assertEqual([x['label'] for x in core.installed_fallback_fonts([d])],['遍黑体','花园明朝'])
   self.assertEqual(core.font_face({'fallback_font':'auto'},[d]),'PingFang SC, PlangothicP1-Regular, PlangothicP2-Regular, HanaMinA')
   self.assertEqual(core.font_face({'fallback_font':'off'},[d]),'PingFang SC')
  with tempfile.TemporaryDirectory() as t:
   (Path(t)/'Plangothic.ttc').write_bytes(b'')
   self.assertEqual(core.installed_fallback_fonts([Path(t)])[0]['fonts'],['PlangothicP1-Regular','PlangothicP2-Regular'])
 def test_setting_validated_and_wired(self):
  self.assertEqual(core.normalize_settings({})['fallback_font'],'auto')
  with self.assertRaises(ValueError):core.normalize_settings({'fallback_font':'x'})
  js=(core.ROOT/'web/app.js').read_text()
  self.assertIn("fallback_font:$('#fallback-font').value",js);self.assertIn('#fallback-font,[data-shortcut]',js)
  self.assertIn("'style/font_face':font_face(settings)",(core.ROOT/'core.py').read_text())
