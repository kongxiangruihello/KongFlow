import json,sys,tempfile,unittest
from pathlib import Path
from unittest.mock import patch
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
import core,quick,profile_backup,restore_review,complete_backup,workflow
class V027Tests(unittest.TestCase):
 def setUp(self):
  self.tmp=tempfile.TemporaryDirectory();self.old=core.DATA,core.RIME;core.DATA=Path(self.tmp.name)/'data';core.RIME=Path(self.tmp.name)/'rime';core.save(core.state())
 def tearDown(self):core.DATA,core.RIME=self.old;self.tmp.cleanup()
 def test_block_scope_switch_and_undo(self):
  quick.change('block_code','nh','你好',core.RIME);quick.change('block_code',"ni'h",'你好',core.RIME)
  before=quick.read(core.RIME)[0];self.assertEqual(len(before),2)
  quick.change('block','nihao','你好',core.RIME);rows,history=quick.read(core.RIME);self.assertEqual(rows,[{'code':'nihao','word':'你好','mode':'block'}])
  quick.change('undo',root=core.RIME,event=history[-1]['id']);self.assertEqual(quick.read(core.RIME)[0],before)
  quick.change('block','nihao','你好',core.RIME);quick.change('block_code','nh','你好',core.RIME)
  self.assertEqual(quick.read(core.RIME)[0],[{'code':'nh','word':'你好','mode':'block_code'}])
  quick.change('reset','nh','你好',core.RIME);self.assertEqual(quick.read(core.RIME)[0],[])
 def test_scoped_backup_restore_and_legacy(self):
  quick.change('block_code','nh','你好',core.RIME);backup=profile_backup.snapshot()
  quick.change('reset','nh','你好',core.RIME);profile_backup.restore(backup)
  self.assertEqual(quick.read(core.RIME)[0],backup['quick'])
  complete_backup.validate(complete_backup.pack(backup,{'format':'kongime-learning-v1','rows':[]}))
  self.assertEqual(quick.normalize_preferences([{'code':'nh','word':'你好','mode':'block'}])[0]['mode'],'block')
 def test_ambiguous_scope_backup_rejected(self):
  rows=[{'code':'nh','word':'你好','mode':'block_code'},{'code':'nihao','word':'你好','mode':'block'}]
  for value in (rows,rows[::-1]):
   with self.assertRaisesRegex(ValueError,'不能同时'):quick.normalize_preferences(value)
 def test_per_app_gap_preserves_language_and_restore_diff(self):
  s=core.state();s['app_preferences']=[core.normalize_app_preference({'id':'com.microsoft.Word','mode':'default','candidate_gap':24}),core.normalize_app_preference({'id':'com.google.Chrome','mode':'english','candidate_gap':8})];core.save(s)
  backup=profile_backup.snapshot();core.generate(core.RIME,s);config=(core.RIME/'squirrel.custom.yaml').read_text()
  self.assertIn('"kongime/app_candidate_gap/com.microsoft.Word": 24',config);self.assertIn('"kongime/app_candidate_gap/com.google.Chrome": 8',config)
  self.assertNotIn('app_options/com.microsoft.Word/ascii_mode',config)
  self.assertIn('"app_options/com.google.Chrome/ascii_mode": true',config)
  s['app_preferences'][0]=core.normalize_app_preference(dict(s['app_preferences'][0],candidate_gap=None));core.save(s);core.generate(core.RIME,s)
  self.assertNotIn('kongime/app_candidate_gap/com.microsoft.Word',(core.RIME/'squirrel.custom.yaml').read_text())
  self.assertNotEqual(restore_review.canonical(backup),restore_review.canonical(profile_backup.snapshot()))
  profile_backup.restore(backup);self.assertEqual(core.state()['app_preferences'][0]['candidate_gap'],24)
 def test_invalid_app_gap(self):
  for gap in (True,0,-1,10,100,'24',float('nan')):
   with self.assertRaises(ValueError):core.normalize_app_preference({'id':'com.test.App','mode':'default','candidate_gap':gap})
