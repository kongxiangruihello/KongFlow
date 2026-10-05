import json,os,tempfile,unittest
from pathlib import Path
from unittest import mock
import core,complete_backup,migration,profile_backup

class V038MigrationTests(unittest.TestCase):
 def setUp(self):
  self.temp=tempfile.TemporaryDirectory();base=Path(self.temp.name)
  self.old=core.DATA,core.RIME,os.environ.get('KONGIME_ICLOUD_ROOT')
  core.DATA=base/'data';core.RIME=base/'rime';core.RIME.mkdir()
  (base/'icloud').mkdir();os.environ['KONGIME_ICLOUD_ROOT']=str(base/'icloud')
  core.save(core.state());self.base=base
 def tearDown(self):
  core.DATA,core.RIME,icloud=self.old
  if icloud is None:os.environ.pop('KONGIME_ICLOUD_ROOT',None)
  else:os.environ['KONGIME_ICLOUD_ROOT']=icloud
  self.temp.cleanup()
 def export(self,auto=False):
  temp=self.base/('t'+str(len(list(self.base.iterdir()))));temp.mkdir()
  return migration.export(Path('/missing-tool'),Path('/missing-lib'),temp,auto=auto)
 def fill(self):
  s=core.state();s['names']=[{'name':'王守仁','kind':'号','alias':'阳明','pinyin':''}];core.save(s)
  core.atomic_json(core.DATA/'classics_user.json',[{'name':'传习录','chapters':[{'name':'卷上','paragraphs':['学问之道无他。']}]}])
  core.atomic_json(core.DATA/'typing-stats.json',{'version':1,'days':{'2026-10-01':{'chars':100,'han':90,'commits':20}}})
 def test_auto_backup_skips_empty_profile(self):
  self.assertTrue(self.export(auto=True)['skipped'])
  self.assertEqual(migration.status()['machines'],[])
 def test_round_trip_restores_names_classics_and_stats(self):
  self.fill();r=self.export()
  self.assertEqual(r['summary']['names'],1);self.assertEqual(r['summary']['classics'],1)
  st=migration.status();self.assertEqual(len(st['machines']),1);m=st['machines'][0]
  self.assertTrue(m['mine']);self.assertTrue(m['downloaded']);self.assertEqual(m['kind'],'manual')
  # 模拟新电脑：清空本机数据
  for f in ('state.json','classics_user.json','classics_user.tsv'):(core.DATA/f).unlink(missing_ok=True)
  core.atomic_json(core.DATA/'typing-stats.json',{'version':1,'days':{'2026-10-01':{'chars':5,'han':5,'commits':1},'2026-10-04':{'chars':7,'han':7,'commits':2}}})
  core.save(core.state())
  self.assertTrue(migration.status()['suggest'])
  pending={}
  def preview(value):pending['v']=value;return {'id':'x'}
  def confirm(token):profile_backup.restore(pending['v']['profile']);return {'verified':True}
  with mock.patch.object(complete_backup,'preview',preview),mock.patch.object(complete_backup,'confirm',confirm):
   out=migration.restore(m['id'],m['file'])
  self.assertTrue(out['ok'])
  self.assertEqual(core.state()['names'][0]['alias'],'阳明')
  self.assertIn('学问之道无他',(core.DATA/'classics_user.tsv').read_text() if (core.ROOT/'vendor/rime-ice/cn_dicts/8105.dict.yaml').exists() else json.dumps(json.loads((core.DATA/'classics_user.json').read_text()),ensure_ascii=False))
  days=json.loads((core.DATA/'typing-stats.json').read_text())['days']
  self.assertEqual(days['2026-10-01']['chars'],100);self.assertEqual(days['2026-10-04']['chars'],7)
  self.assertFalse(migration.status()['suggest'])
 def test_tampered_backup_rejected(self):
  self.fill();r=self.export();m=migration.status()['machines'][0]
  path=migration.root()/m['id']/m['file'];value=json.loads(path.read_text())
  value['extras']['typing_stats']['2026-10-02']={'chars':1}
  path.write_text(json.dumps(value,ensure_ascii=False))
  with self.assertRaises(ValueError):migration.validate(json.loads(path.read_text()))
 def test_auto_backups_pruned_manual_kept(self):
  self.fill();self.export();folder=migration.root()/migration.machine()['id']
  for i in range(14):(folder/('KongFlow-202601%02d-030000-auto.json'%(i+1))).write_text('{}')
  migration._prune(folder)
  names=[n for n,_ in migration._files(folder)]
  self.assertEqual(sum(n.endswith('-auto.json') for n in names),migration.AUTO_KEEP)
  self.assertEqual(sum(n.endswith('-manual.json') for n in names),1)
 def test_icloud_placeholder_listed_as_not_downloaded(self):
  folder=migration.root()/'0123456789abcdef';folder.mkdir(parents=True)
  (folder/'.KongFlow-20261001-080000-auto.json.icloud').write_bytes(b'')
  m=migration.status()['machines'][0]
  self.assertEqual(m['file'],'KongFlow-20261001-080000-auto.json');self.assertFalse(m['downloaded']);self.assertFalse(m['mine'])
 def test_auto_setting_and_bad_names(self):
  self.assertFalse(migration.set_auto(False)['auto'])
  self.assertTrue(self.export(auto=True)['skipped'])
  for bad in ('x/../y','KongFlow-1.json'):
   with self.assertRaises(ValueError):migration._load('0123456789abcdef',bad)
  with self.assertRaises(ValueError):core.normalize_name_rows([{'name':'王','kind':'外号','alias':'x'}])
 def test_client_runs_daily_idle_backup(self):
  source=(core.ROOT/'client/sources/SquirrelApplicationDelegate.swift').read_text()
  self.assertIn('func autoBackupIfDue()',source);self.assertIn('learningWorker(mode:"migration-auto")',source)
  self.assertIn('secondsSinceLastEventType',source)
  self.assertIn("mode=='migration-auto'",(core.ROOT/'learning.py').read_text())
  self.assertIn("'migration.py'",(core.ROOT/'build_integrated.py').read_text())

class V038LearningCodeTests(unittest.TestCase):
 def test_english_and_mixed_codes_are_accepted(self):
  import learning
  rows=[{'word':'github','pinyin':'G I T H U B','commits':3},{'word':'翻译hi','pinyin':'fan yi H I','commits':1},{'word':'中文','pinyin':'zhong wen','commits':9}]
  self.assertEqual(learning.validate({'format':learning.FORMAT,'rows':rows}),rows)
  for bad in ('zhong\twen','zhong  wen',' zhong','中文'):
   with self.assertRaises(ValueError):learning.validate({'format':learning.FORMAT,'rows':[{'word':'x','pinyin':bad,'commits':1}]})
 def test_export_skips_unrepresentable_entries(self):
  import learning
  with tempfile.TemporaryDirectory() as t:
   f=Path(t)/'x.txt';f.write_text('github\tG I T H U B\t2\n坏\tzhong\x01\t1\n删\tshan\t-1\n中文\tzhong wen \t5\n')
   rows=learning.from_tsv(f)['rows']
  self.assertEqual([r['word'] for r in rows],['github','中文'])

class V038SyncPageTests(unittest.TestCase):
 def test_backup_page_shows_only_migration(self):
  import re
  html=(core.ROOT/'web/index.html').read_text()
  i=html.index('<section id="sync"');j=html.index('</section>',i);page=html[i:j]
  legacy=page.index('<div id="sync-legacy" hidden>')
  visible=page[:legacy]
  self.assertIn('id="migration"',visible);self.assertIn('id="migration-undo"',visible)
  self.assertEqual(re.findall('<h2',visible),[])
  for old in ('complete-export','icloud-save','snapshot-create','rollback-profile'):self.assertIn(old,page[legacy:])

class V038BuildTests(unittest.TestCase):
 def test_payload_permissions_normalized_before_signing(self):
  source=(core.ROOT/'build_integrated.py').read_text()
  self.assertIn('stage.chmod(0o755)',source)
  self.assertIn("0o755 if path.is_dir() or path.stat().st_mode&0o111 else 0o644",source)
  self.assertLess(source.index('stage.chmod(0o755)'),source.index("'codesign','--force'"))

if __name__=='__main__':unittest.main()
