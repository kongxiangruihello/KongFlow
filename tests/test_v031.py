import tempfile,unittest,plistlib
from pathlib import Path
from unittest.mock import patch
import core,workflow,update_check
class V031Tests(unittest.TestCase):
 def test_brand_and_unknown_mode_are_preserved(self):
  with tempfile.TemporaryDirectory() as d:
   root=Path(d);app=root/'client';(app/'Contents').mkdir(parents=True)
   (app/'Contents/Info.plist').write_bytes(plistlib.dumps({'CFBundleDisplayName':'KongFlow','KongIMEVersion':workflow.VERSION}))
   data=root/'data';data.mkdir()
   for contexts in ([],[{'app':'com.apple.Notes','english':False,'active':False}]):
    inputs={'selected':None,'enabled':None,'runtimes':[{'version':workflow.VERSION,'input_context':c} for c in contexts]}
    with patch.object(core,'DATA',data),patch.object(workflow,'client',return_value=app),patch.object(workflow,'input_status',return_value=inputs):
     result=workflow.status()
    self.assertTrue(result['branded']);self.assertIsNone(result['selected']);self.assertEqual(result['input_contexts'],contexts)
 def test_new_release_asset_and_legacy_asset_are_supported(self):
  for name in ['KongFlow-9.0-Mac.zip','KongIME-9.0-Mac.zip']:
   url=update_check.REPO+'/releases/'
   row={'tag_name':'v9.0.0','html_url':url+'tag/v9.0.0','assets':[{'state':'uploaded','name':name,'size':1,'browser_download_url':url+'download/v9.0.0/'+name}]}
   self.assertTrue(update_check.select([row])['available'])
