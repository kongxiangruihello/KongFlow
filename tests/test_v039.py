import re,unittest
from html.parser import HTMLParser
import core

VOID={'input','br','img','meta','link','hr','source'}
class Node:
 def __init__(self,tag,attrs,parent):self.tag,self.attrs,self.parent,self.children,self.text=tag,dict(attrs),parent,[],''
 def walk(self):
  yield self
  for c in self.children:yield from c.walk()
 def all_text(self):return self.text+''.join(c.all_text() for c in self.children)
 def ancestors(self):
  p=self.parent
  while p:yield p;p=p.parent
class Tree(HTMLParser):
 def __init__(self,html):
  super().__init__();self.root=Node('root',[],None);self.cur=self.root;self.feed(html)
 def handle_starttag(self,tag,attrs):
  n=Node(tag,attrs,self.cur);self.cur.children.append(n)
  if tag not in VOID:self.cur=n
 def handle_endtag(self,tag):
  p=self.cur
  while p is not self.root and p.tag!=tag:p=p.parent
  if p is not self.root:self.cur=p.parent
 def handle_data(self,d):self.cur.text+=d

def tree():return Tree((core.ROOT/'web/index.html').read_text()).root
def by_id(root,i):return next((n for n in root.walk() if n.attrs.get('id')==i),None)
def visible(n):return not any('hidden' in a.attrs or a.attrs.get('id') in ('settings-legacy','sync-legacy') for a in [n,*n.ancestors()] if a.tag!='section')

class V039SettingsLayoutTests(unittest.TestCase):
 def test_navigation(self):
  nav=next(n for n in tree().walk() if n.tag=='nav')
  got=[(b.attrs['data-tab'],b.all_text().split()[0]) for b in nav.children if b.tag=='button']
  self.assertEqual(got,[('personalization','输入'),('academic','学术写作'),('libraries','词库'),('words','我的词语'),('sync','备份与恢复'),('settings','关于与诊断')])
 def test_single_visible_save_path(self):
  r=tree()
  for i in ('settings-legacy','sync-legacy'):self.assertIn('hidden',by_id(r,i).attrs)
  shown=[b.all_text().strip() for b in r.walk() if b.tag=='button' and visible(b)]
  for retired in ('保存配置','保存并应用','保存外观','保存偏好','保存并应用模糊音','保存并应用后试打','词库','个性化'):
   self.assertNotIn(retired,shown)
  self.assertFalse(visible(by_id(r,'test-input')));self.assertTrue(visible(by_id(r,'sandbox-input')))
 def test_controls_live_in_autosave_scope(self):
  r=tree()
  for i in ('page-size','abbreviation','traditional','cite-style','quote-style','stats','candidate-theme','shortcut-expand'):
   self.assertTrue(any('config-scope' in a.attrs.get('class','').split() for a in by_id(r,i).ancestors()),i)
  js=(core.ROOT/'web/app.js').read_text()
  self.assertIn(".config-scope input, .config-scope select",js)
  self.assertIn("$('#auto-save-config').checked=true;",js)
 def test_ids_unique_and_script_targets_exist(self):
  ids=[n.attrs['id'] for n in tree().walk() if 'id' in n.attrs]
  self.assertEqual(len(ids),len(set(ids)))
  js=(core.ROOT/'web/app.js').read_text()
  self.assertEqual(sorted({m for m in re.findall(r"\$\('#([\w-]+)'\)\.(?:onclick|onchange|oninput)",js) if m not in ids}),[])
 def test_fresh_state_has_names(self):
  import tempfile
  from pathlib import Path
  old=core.DATA
  with tempfile.TemporaryDirectory() as t:
   core.DATA=Path(t)
   try:self.assertEqual(core.state()['names'],[])
   finally:core.DATA=old
