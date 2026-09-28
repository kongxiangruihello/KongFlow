import json, subprocess, unittest
from pathlib import Path
from unittest.mock import patch
import workflow

class InputSourceTests(unittest.TestCase):
 def select(self, selected):
  with patch.object(workflow,'client',return_value=Path('/test/app')), patch.object(workflow.subprocess,'run') as run, patch.object(workflow,'input_status',return_value={'selected':selected}):
   return workflow.setup('select')
 def test_verified_selection(self):
  self.assertIn('已确认',self.select(True)['message'])
 def test_unverified_selection_is_not_success(self):
  for value in (False,None):
   with self.subTest(value=value),self.assertRaisesRegex(ValueError,'尚未确认'):
    self.select(value)
 def test_command_failure_is_actionable(self):
  with patch.object(workflow,'client',return_value=Path('/test/app')), patch.object(workflow.subprocess,'run',side_effect=subprocess.CalledProcessError(1,'select')), self.assertRaisesRegex(ValueError,'切换未成功'):
   workflow.setup('select')
 def test_no_session_does_not_claim_process_absent(self):
  report=workflow.runtime_summary(workflow.VERSION,{'runtimes':None,'screen_count':0})
  self.assertIn('无法检测',report['runtime_detail']);self.assertFalse(report['needs_restart'])
