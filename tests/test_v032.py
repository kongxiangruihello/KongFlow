import shutil,subprocess,tempfile,unittest
from pathlib import Path
import core
APP=core.ROOT/'branding/payload/Squirrel.app'
class V032Tests(unittest.TestCase):
 def test_pair_hook_notifies_rime_after_interception(self):
  source=(core.ROOT/'client/sources/SquirrelInputController.swift').read_text()
  self.assertIn('if handlePairedPunctuation(event) {\n        notifyRimeOfInterceptedKey(event)\n        return true',source)
  self.assertIn('kReleaseMask.rawValue',source[source.index('func notifyRimeOfInterceptedKey'):source.index('func handlePairedPunctuation')])
 @unittest.skipUnless((APP/'Contents/Frameworks/librime.1.dylib').exists() and shutil.which('xcrun'),'需要鼠须管引擎依赖与 Xcode 命令行工具')
 def test_shift_pair_keeps_language_real_engine(self):
  with tempfile.TemporaryDirectory() as temp:
   root=Path(temp);old=core.DATA,core.RIME
   try:
    core.DATA=root/'data';core.RIME=root/'rime';core.save(core.state());core.make_bundle(core.RIME,core.state())
    subprocess.run([str(APP/'Contents/MacOS/rime_deployer'),'--build',str(core.RIME),str(APP/'Contents/SharedSupport'),str(core.RIME/'build')],check=True,capture_output=True,timeout=120)
    binary=root/'shift-pair'
    subprocess.run(['xcrun','clang++','-std=c++17','-I',str(core.ROOT/'client/librime/src'),str(core.ROOT/'tests/ShiftPairToggleSmoke.cpp'),'-o',str(binary)],check=True,capture_output=True,timeout=60)
    result=subprocess.run([str(binary),str(APP/'Contents/Frameworks/librime.1.dylib'),str(core.RIME)],text=True,capture_output=True,timeout=45)
    self.assertEqual(result.returncode,0,result.stdout+result.stderr)
   finally:core.DATA,core.RIME=old
 def test_expand_control_is_labelled_inside_the_window(self):
  source=(core.ROOT/'client/sources/SquirrelPanel.swift').read_text()
  self.assertIn('"更多 ▾"',source);self.assertIn('"收起 ▴"',source)
  # The footer is part of the laid-out window, so it shares the drawn background.
  self.assertIn('layout.footerFrame',source)
 def test_panel_background_uses_full_bounds(self):
  source=(core.ROOT/'client/sources/SquirrelPanel.swift').read_text()
  draw=source[source.index('override func draw('):source.index('final class SquirrelPanel')]
  self.assertIn('NSBezierPath(roundedRect: bounds',draw)
class V033Tests(unittest.TestCase):
 def test_folded_and_expanded_counts_are_validated_and_exported(self):
  s=core.normalize_settings({});self.assertEqual((s['folded_count'],s['expand_total']),(0,0))
  s=core.normalize_settings({'folded_count':5,'expand_total':27});self.assertEqual((s['folded_count'],s['expand_total']),(5,27))
  for bad in ({'folded_count':4},{'folded_count':'5'},{'expand_total':10},{'expand_total':True}):
   with self.assertRaises(ValueError):core.normalize_settings(bad)
  source=(core.ROOT/'core.py').read_text()
  self.assertIn("'kongime/folded_count':settings['folded_count']",source);self.assertIn("'kongime/expand_total':settings['expand_total']",source)
 def test_client_reads_counts_and_labels_extra_rows(self):
  source=(core.ROOT/'client/sources/SquirrelInputController.swift').read_text()
  self.assertIn('getDouble("kongime/folded_count")',source);self.assertIn('getDouble("kongime/expand_total")',source)
  self.assertIn('"⇧"+String(extra+1)',source);self.assertIn('selectCandidate(pageCandidateCount + digit)',source)
 def test_debug_layout_log_removed(self):
  self.assertNotIn('kongflow-panel-debug',(core.ROOT/'client/sources/SquirrelPanel.swift').read_text())
class IconTests(unittest.TestCase):
 def test_icons_are_generated_and_packaged(self):
  b=core.ROOT/'branding'
  self.assertTrue((b/'KongFlow.icns').read_bytes().startswith(b'icns'))
  self.assertTrue((b/'rime.pdf').read_bytes().startswith(b'%PDF'))
  for n in ['KongFlow-icon.svg','KongFlow-menubar.svg','make_icons.py']:self.assertTrue((b/'icon'/n).is_file())
  source=(core.ROOT/'build_integrated.py').read_text()
  self.assertIn("client/'Contents/Resources/Rime.icns'",source);self.assertIn("CFBundleIconFile='KongFlow'",source)

class V034LayoutTests(unittest.TestCase):
 @unittest.skipUnless(shutil.which('xcrun'),'需要 Xcode 命令行工具')
 def test_candidate_layout_smoke(self):
  with tempfile.TemporaryDirectory() as d:
   binary=Path(d)/'layout-smoke'
   subprocess.run(['xcrun','swiftc','-module-cache-path','/tmp/kongime-swift-cache',str(core.ROOT/'client/sources/CandidateLayout.swift'),str(core.ROOT/'tests/CandidateLayoutSmoke.swift'),'-o',str(binary)],check=True,capture_output=True,timeout=180)
   result=subprocess.run([str(binary)],text=True,capture_output=True,timeout=60)
   self.assertEqual(result.returncode,0,result.stdout+result.stderr)
 def test_panel_has_single_view_without_scrolling(self):
  source=(core.ROOT/'client/sources/SquirrelPanel.swift').read_text()
  self.assertIn('CandidateLayout.make(',source)
  self.assertNotIn('NSTextLayoutManager',source);self.assertNotIn('private let scrollView',source)
  self.assertFalse((core.ROOT/'client/sources/SquirrelView.swift').exists())
class V035Tests(unittest.TestCase):
 @unittest.skipUnless(shutil.which('xcrun'),'需要 Xcode 命令行工具')
 def test_punctuation_pairs_smoke(self):
  with tempfile.TemporaryDirectory() as d:
   binary=Path(d)/'pairs'
   subprocess.run(['xcrun','swiftc','-module-cache-path','/tmp/kongime-swift-cache',str(core.ROOT/'client/sources/PunctuationPairs.swift'),str(core.ROOT/'tests/PunctuationPairsSmoke.swift'),'-o',str(binary)],check=True,capture_output=True,timeout=180)
   result=subprocess.run([str(binary)],text=True,capture_output=True,timeout=60)
   self.assertEqual(result.returncode,0,result.stdout+result.stderr)
 def test_new_settings_are_validated(self):
  s=core.normalize_settings({})
  self.assertEqual((s['traditional'],s['rare_chars'],s['radical_lookup'],s['select_character'],s['reference_tools'],s['stats'],s['quote_style'],s['density']),(False,True,True,True,True,True,'curly','standard'))
  for bad in ({'traditional':'yes'},{'quote_style':'square'},{'density':'tight'}):
   with self.assertRaises(ValueError):core.normalize_settings(bad)
 def schema(self,**settings):
  with tempfile.TemporaryDirectory() as d:
   old=core.DATA;core.DATA=Path(d)/'data'
   try:
    s=core.state();s['settings']=core.normalize_settings(settings);target=Path(d)/'rime';target.mkdir()
    if not (core.ROOT/'vendor/rime-ice/rime_ice.schema.yaml').exists():self.skipTest('需要雾凇基础文件')
    core.generate(target,s)
    files={str(f.relative_to(target)) for f in target.rglob('*') if f.is_file()}
    return (target/'qingyan.schema.yaml').read_text(),(target/'qingyan.dict.yaml').read_text(),files
   finally:core.DATA=old
 def test_schema_enables_features(self):
  # Plain-text checks: the macOS system Python has no YAML module.
  text,dictionary,files=self.schema()
  self.assertIn('  processors: [lua_processor@*select_character, ',text)
  self.assertIn('simplifier@traditionalize',text);self.assertIn('affix_segmentor@radical_lookup',text)
  for t in ('lua_translator@*kongflow_era','lua_translator@*kongflow_classics','lua_translator@*kongflow_tone','table_translator@radical_lookup'):self.assertIn(t,text)
  for p in ('kongflow_era: ','kongflow_classics: ','kongflow_tone: ','radical_lookup: "^u'):self.assertIn('    '+p,text)
  self.assertIn('cn_dicts/41448',dictionary)
  for f in ('lua/kongflow_era.lua','lua/kongflow_classics.lua','lua/kongflow_tone.lua','kongflow_eras.tsv','kongflow_classics.tsv'):self.assertIn(f,files)
 def test_schema_respects_switches_and_paging_keys(self):
  text,dictionary,_=self.schema(rare_chars=False,radical_lookup=False,reference_tools=False,quote_style='corner',traditional=True,shortcuts={'previous':'bracketleft','next':'bracketright'})
  self.assertNotIn('lua_processor@*select_character',text)
  self.assertNotIn('affix_segmentor@radical_lookup',text);self.assertNotIn('cn_dicts/41448',dictionary)
  self.assertIn("""    '"': {pair: ['「', '」']}""",text)
  self.assertIn('  - name: traditionalization\n    states: [简, 繁]\n    reset: 1\n',text)
 def test_reference_data(self):
  eras=(core.ROOT/'runtime/kongflow_eras.tsv').read_text().splitlines()
  self.assertGreater(len(eras),500)
  rows={l.split('\t')[2]:l.split('\t') for l in eras}
  self.assertEqual(rows['康熙'][3:5],['1662','1722']);self.assertEqual(rows['贞观'][3:5],['627','649']);self.assertEqual(rows['乾隆'][0],'qianlong')
  classics=(core.ROOT/'runtime/kongflow_classics.tsv').read_text()
  self.assertIn('xesxzbyyh\t学而时习之，不亦说乎？\t论语·学而 1.1',classics)
class V035ManagerTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.old=core.DATA;core.DATA=Path(self.temp.name)/'data';core.save(core.state())
 def tearDown(self):core.DATA=self.old;self.temp.cleanup()
 def test_term_scan_finds_new_names_and_adds_them(self):
  import term_tools,zipfile
  if not (core.ROOT/'vendor/rime-ice/cn_dicts/8105.dict.yaml').exists():self.skipTest('需要雾凇词库')
  folder=Path(self.temp.name)/'docs';folder.mkdir()
  (folder/'a.md').write_text('朱维铮先生论晚明思想。朱维铮以为章太炎与康有为异趣。读朱维铮《走出中世纪》。')
  with zipfile.ZipFile(folder/'b.docx','w') as z:z.writestr('word/document.xml','<w:document><w:p><w:t>又见朱维铮之说。</w:t></w:p></w:document>')
  (folder/'.hidden.txt').write_text('朱维铮'*50)
  r=term_tools.scan(folder)
  self.assertEqual(r['files'],2)
  row=next(x for x in r['terms'] if x['word']=='朱维铮')
  self.assertEqual(row['count'],4);self.assertEqual(row['pinyin'],'zhu wei zheng')
  self.assertEqual(term_tools.add([{'word':'朱维铮','pinyin':'zhu wei zheng'}]),{'added':1,'skipped':0})
  self.assertEqual(term_tools.add([{'word':'朱维铮','pinyin':'zhu wei zheng'}])['skipped'],1)
  self.assertNotIn('朱维铮',[x['word'] for x in term_tools.scan(folder)['terms']])
 def test_typing_stats_summary(self):
  import term_tools,datetime,json
  (core.DATA/'typing-stats.json').write_text(json.dumps({'version':1,'days':{'2026-10-05':{'chars':10,'han':8,'commits':3},'2026-10-01':{'chars':5,'han':5,'commits':1},'2026-08-01':{'chars':7,'han':7,'commits':2}}}))
  r=term_tools.typing_stats(datetime.date(2026,10,5))
  self.assertEqual(r['today']['han'],8);self.assertEqual(r['week']['han'],13);self.assertEqual(r['total']['chars'],22);self.assertEqual(r['days'],3)
