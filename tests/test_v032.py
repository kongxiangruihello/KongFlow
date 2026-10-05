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
 def test_expand_control_has_visible_footer(self):
  source=(core.ROOT/'client/sources/SquirrelPanel.swift').read_text()
  layout=source[source.index('func show()'):]
  # The footer under the candidate box must be painted, and the control must be labelled, not a bare arrow.
  self.assertIn('footerBack.layer?.backgroundColor = theme.backgroundColor.cgColor',layout)
  self.assertIn('footerBack.isHidden = footer == 0 || vertical',layout)
  self.assertIn('"更多 ▾"',layout);self.assertIn('"收起 ▴"',layout)
  self.assertLess(source.index('contentView.addSubview(footerBack)'),source.index('contentView.addSubview(scrollView)'),'footer background must sit below the candidate box')
 def test_panel_background_uses_full_bounds(self):
  source=(core.ROOT/'client/sources/SquirrelView.swift').read_text()
  body=source[source.index('override func draw('):]
  # A partial dirty rect after 收起 must not shrink the candidate background.
  self.assertIn('let dirtyRect = bounds',body[:600])
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
