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
