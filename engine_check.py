"""Smoke-check the compiled engine without touching live sessions or learning data."""
import json,shutil,subprocess,tempfile,time
from pathlib import Path
import core

def run(app,enabled,strict=True):
 helper=core.ROOT/'engine-check'
 if not helper.is_file():helper=core.ROOT/'client/build/engine-check'
 if not helper.is_file():raise ValueError('缺少输入检查程序，请重新安装当前版本')
 with tempfile.TemporaryDirectory(prefix='kongime-engine-check-') as tmp:
  root=Path(tmp);(root/'build').mkdir()
  for name in ['qingyan.schema.yaml','qingyan.table.bin','qingyan.prism.bin','qingyan.reverse.bin']:
   source=core.RIME/'build'/name
   if not source.is_file():raise ValueError('缺少已编译词库，请重新应用配置')
   shutil.copy2(source,root/'build'/name)
  # No custom phrase files or learned data: verify the pinyin engine itself.
  # Copy only the local Lua modules needed by the compiled configuration.
  shutil.copytree(core.ROOT/'runtime',root/'lua')
  result=subprocess.run([str(helper),str(app/'Contents/Frameworks/librime.1.dylib'),tmp,'on' if enabled else 'off'],capture_output=True,text=True,timeout=30)
  try:report=json.loads(result.stdout)
  except (ValueError,TypeError):raise ValueError('输入检查未能完成，请重新应用；若仍失败请重新安装当前版本')
  if not isinstance(report,dict) or type(report.get('ok')) is not bool:raise ValueError('输入检查结果无效')
  checks=report.get('checks')
  if not isinstance(checks,list) or len(checks)!=4:raise ValueError('输入检查结果不完整')
  for check,code in zip(checks,('nihao','nh','zg',"ni'h")):
   if not isinstance(check,dict) or check.get('code')!=code or type(check.get('ok')) is not bool or type(check.get('skipped')) is not bool:raise ValueError('输入检查结果无效')
   if check['skipped']!=(code!='nihao' and not enabled):raise ValueError('输入检查模式不一致')
  report['ok']=result.returncode==0 and report['ok'] and all(c['ok'] for c in checks)
  report.update(time=time.strftime('%Y-%m-%d %H:%M:%S'),abbreviation=enabled)
  if strict and not report['ok']:raise ValueError('拼音或简拼检查未通过，请重新应用配置；管理页数据和学习记录仍保留')
  return report

def diagnose(progress=lambda stage: None):
 """Check the saved deployment, never rebuild or open a live learning database."""
 import workflow
 progress('check')
 status=workflow.status();enabled=core.state()['settings']['abbreviation'];checks=[]
 def add(label,state,detail,action=None):
  checks.append(dict(label=label,state=state,detail=detail,action=action))
 add('简拼开关','passed' if enabled else 'disabled','已开启，支持 nh、zg 和混合拼音。' if enabled else '已关闭，本次只检查全拼；简拼项不会标为通过。',None if enabled else 'abbreviation')
 installed=status.get('installed_version')==workflow.VERSION
 add('客户端版本','passed' if installed else 'failed','设置 '+workflow.VERSION+' / 已安装 '+str(status.get('installed_version') or '未安装'),None if installed else 'installation')
 running=installed and not status.get('needs_restart') and not status.get('running_unknown') and status.get('running_versions')==[workflow.VERSION]
 add('运行版本','passed' if running else 'pending',status['runtime_detail'],None if running else 'installation')
 add('已保存配置与词库','passed' if status['deployed'] else 'failed','编译文件与上次成功应用一致。' if status['deployed'] else '配置尚未应用或编译文件已变化，请保存并应用后重试。',None if status['deployed'] else 'deploy')
 report=None;error=None
 if status['deployed'] and workflow.client():
  try:report=run(workflow.client(),enabled,strict=False)
  except (ValueError,OSError,subprocess.SubprocessError) as e:error=str(e)
 for i,(code,target) in enumerate((('nihao','你好'),('nh','你好'),('zg','中国'),("ni'h",'你好'))):
  label=code+' → '+target
  if i and not enabled:add(label,'skipped','简拼关闭，未检查。','abbreviation')
  elif report:
   c=report['checks'][i]
   add(label,'passed' if c['ok'] else 'failed','已找到目标候选。' if c['ok'] else '未找到目标候选，请重新应用配置后再检查。',None if c['ok'] else 'deploy')
  else:add(label,'failed' if error else 'pending',error or '请先完成配置应用，再运行检查。','deploy')
 engine_ok=bool(report and report['ok'])
 ready=engine_ok and enabled and installed and running and status['deployed']
 return {'checks':checks,'ok':ready,'engine_ok':engine_ok,'abbreviation':enabled,'time':time.strftime('%Y-%m-%d %H:%M:%S'),'message':('简拼引擎检查通过，请继续在实际应用中试打。' if ready else '自检完成，请按各项提示处理；未检查的项目不代表通过。')}
