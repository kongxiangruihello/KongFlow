import json,os,subprocess,tempfile,unittest
from pathlib import Path
import core,quick,learning
class V028Tests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();self.root=Path(self.temp.name);self.old=core.DATA,core.RIME
  core.DATA=self.root/'data';core.RIME=self.root/'rime';core.save(core.state())
 def tearDown(self):core.DATA,core.RIME=self.old;self.temp.cleanup()
 def test_exact_undo_token_and_stale_protection(self):
  first=quick.change('block_code','nh','你好',core.RIME)
  second=quick.change('pin','zg','中国',core.RIME);before=(core.RIME/'kongime_quick.tsv').read_bytes()
  with self.assertRaisesRegex(ValueError,'先撤销'):quick.change('undo',root=core.RIME,event=first['event'])
  self.assertEqual(before,(core.RIME/'kongime_quick.tsv').read_bytes())
  quick.change('undo',root=core.RIME,event=second['event']);quick.change('undo',root=core.RIME,event=first['event'])
  self.assertEqual(quick.read(core.RIME)[0],[])
 def test_native_cli_json_contract(self):
  env=dict(os.environ,KONGIME_RIME=str(core.RIME));script=str(core.ROOT/'quick.py')
  r=subprocess.run(['/usr/bin/python3','-B',script,'--json','block','nh','你好'],env=env,text=True,capture_output=True,check=True)
  value=json.loads(r.stdout);self.assertEqual(value['event'],quick.read(core.RIME)[1][-1]['id'])
  r=subprocess.run(['/usr/bin/python3','-B',script,'--undo-json',value['event']],env=env,text=True,capture_output=True,check=True)
  self.assertTrue(json.loads(r.stdout)['ok']);self.assertEqual(quick.read(core.RIME)[0],[])
 def test_pause_state_native(self):
  binary=self.root/'pause-state'
  subprocess.run(['xcrun','swiftc','-module-cache-path','/tmp/kongime-swift-cache',str(core.ROOT/'client/sources/LearningPause.swift'),str(core.ROOT/'tests/LearningPauseStateSmoke.swift'),'-o',str(binary)],check=True,capture_output=True)
  subprocess.run([str(binary)],check=True,capture_output=True)
 def test_pause_preserves_rank_and_stops_learning_real_engine(self):
  core.make_bundle(core.RIME,core.state());app=core.ROOT/'branding/payload/Squirrel.app';library=app/'Contents/Frameworks/librime.1.dylib'
  subprocess.run([str(app/'Contents/MacOS/rime_deployer'),'--build',str(core.RIME),str(app/'Contents/SharedSupport'),str(core.RIME/'build')],check=True,capture_output=True,timeout=120)
  binary=self.root/'pause-engine'
  subprocess.run(['xcrun','clang++','-std=c++17','-I',str(core.ROOT/'client/librime/src'),str(core.ROOT/'tests/LearningPauseSmoke.cpp'),'-o',str(binary)],check=True,capture_output=True,timeout=60)
  def run(mode):
   result=subprocess.run([str(binary),str(library),str(core.RIME),mode],text=True,capture_output=True,timeout=45)
   self.assertEqual(result.returncode,0,result.stderr)
  def export():
   out=self.root/'export.txt'
   subprocess.run([str(core.ROOT/'client/build/learning-tool'),str(library),str(core.RIME),'export',str(out),str(out)],check=True,capture_output=True,timeout=30)
   return sorted(line for line in out.read_text().splitlines() if line and not line.startswith('#'))
  run('learn');before=export();self.assertTrue(any('你好' in line for line in before))
  run('pause');self.assertEqual(export(),before,'paused commits must not change learned rows or weights')
  run('resume');self.assertNotEqual(export(),before,'resuming must learn again')
