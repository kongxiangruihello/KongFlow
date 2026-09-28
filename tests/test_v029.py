import json,subprocess,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
import core,workflow,engine_check

class V029Tests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.old=core.DATA,core.RIME
  core.DATA=Path(self.tmp.name)/'data';core.RIME=Path(self.tmp.name)/'rime';core.save(core.state())
  self.status=dict(installed_version=workflow.VERSION,needs_restart=False,running_unknown=0,running_versions=[workflow.VERSION],runtime_detail='正在运行：'+workflow.VERSION,deployed=True)
  self.report=dict(ok=True,checks=[dict(code=c,ok=True,skipped=False,candidates=1) for c in ('nihao','nh','zg',"ni'h")])
 def tearDown(self):
  core.DATA,core.RIME=self.old;self.tmp.cleanup()
 def diagnose(self,report=None):
  with patch.object(workflow,'status',return_value=self.status),patch.object(workflow,'client',return_value=Path('/test/app')),patch.object(engine_check,'run',return_value=report or self.report) as run:
   value=engine_check.diagnose();return value,run
 def test_success_has_explicit_four_engine_results_and_no_writes(self):
  before=(core.DATA/'state.json').read_bytes();value,run=self.diagnose()
  self.assertTrue(value['ok']);self.assertEqual([c['label'] for c in value['checks'][-4:]],['nihao → 你好','nh → 你好','zg → 中国',"ni'h → 你好"])
  self.assertTrue(all(c['state']=='passed' for c in value['checks']));run.assert_called_once_with(Path('/test/app'),True,strict=False)
  self.assertEqual(before,(core.DATA/'state.json').read_bytes())
 def test_disabled_abbreviation_is_skipped_not_success(self):
  s=core.state();s['settings']['abbreviation']=False;core.save(s)
  value,run=self.diagnose();self.assertFalse(value['ok']);self.assertTrue(value['engine_ok'])
  self.assertTrue(all(c['state']=='skipped' for c in value['checks'][-3:]));run.assert_called_once_with(Path('/test/app'),False,strict=False)
 def test_stale_deployment_does_not_probe_wrong_config(self):
  self.status['deployed']=False;value,run=self.diagnose();run.assert_not_called();self.assertFalse(value['ok'])
  self.assertTrue(all(c['state']=='pending' for c in value['checks'][-4:]))
 def test_old_runtime_never_claims_ready_even_if_engine_passes(self):
  self.status.update(running_versions=['0.26.0'],needs_restart=True)
  value,_=self.diagnose();self.assertFalse(value['ok']);self.assertTrue(value['engine_ok']);self.assertEqual(value['checks'][2]['state'],'pending')
 def test_failure_retains_individual_results_and_repair(self):
  self.report['ok']=False;self.report['checks'][1]['ok']=False
  value,_=self.diagnose();self.assertFalse(value['ok']);self.assertEqual(value['checks'][-3]['state'],'failed');self.assertEqual(value['checks'][-3]['action'],'deploy');self.assertEqual(value['checks'][-4]['state'],'passed')
 def test_timeout_becomes_actionable_failed_rows(self):
  with patch.object(workflow,'status',return_value=self.status),patch.object(workflow,'client',return_value=Path('/test/app')),patch.object(engine_check,'run',side_effect=subprocess.TimeoutExpired('check',30)):
   value=engine_check.diagnose()
  self.assertFalse(value['ok']);self.assertTrue(all(c['state']=='failed' and c['action']=='deploy' for c in value['checks'][-4:]))
 def test_learning_filter_integrity_is_tracked(self):
  core.RIME.mkdir();target=core.RIME/'lua';target.mkdir();(target/'kongime_learning.lua').write_text('first')
  names=('lua/kongime_learning.lua',);before=workflow.file_hashes(core.RIME,names)
  (target/'kongime_learning.lua').write_text('changed');self.assertNotEqual(before,workflow.file_hashes(core.RIME,names));self.assertIn(names[0],workflow.CONFIGS)
 def test_incomplete_helper_output_rejected(self):
  (core.RIME/'build').mkdir(parents=True)
  for name in workflow.BUILT:(core.RIME/'build'/name).write_text('compiled fixture')
  result=subprocess.CompletedProcess([],0,json.dumps({'ok':True,'checks':[]}), '')
  with patch.object(engine_check.subprocess,'run',return_value=result):
   with self.assertRaisesRegex(ValueError,'不完整'):engine_check.run(Path('/test/app'),True,strict=False)
