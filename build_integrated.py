from pathlib import Path
import shutil,subprocess,plistlib,zipfile
import build_installer
root=Path(__file__).resolve().parent
out=root/'release/KongFlow-0.37';out.mkdir(parents=True,exist_ok=False)
# Assemble and sign outside ~/Documents: when Documents syncs with iCloud, files there
# carry file-provider attributes that codesign rejects ("…Finder information, or similar
# detritus not allowed"), and xattr -c cannot keep them off.
import tempfile
stage=Path(tempfile.mkdtemp(prefix='kongflow-payload-v037-'))
client=stage/'Squirrel.app'
shutil.copytree(root/'branding/payload/Squirrel.app',client,symlinks=True)
shutil.copy2(root/'client/build/Squirrel',client/'Contents/MacOS/Squirrel')
helper=client/'Contents/Helpers/KongFlow设置.app'
(helper/'Contents/MacOS').mkdir(parents=True)
shutil.copy2(root/'client/build/KongIMESettings',helper/'Contents/MacOS/Qingyan')
manager=helper/'Contents/Resources/manager'
manager.mkdir(parents=True)
shutil.copytree(root/'vendor/rime-ice',manager/'vendor/rime-ice',ignore=shutil.ignore_patterns('.git','__pycache__'))
shutil.copytree(root/'licenses',manager/'licenses')
shutil.copy2(root/'sgpu_pinyin.json',manager/'sgpu_pinyin.json')
shutil.copy2(root/'client/build/choose-folder',manager/'choose-folder')
for name in ['app.py','core.py','workflow.py','jobs.py','quick.py','profile_backup.py','cloud_client.py','library_tools.py','personal_data.py','local_snapshots.py','learning.py','restore_review.py','phrase_tools.py','engine_check.py','upgrade_check.py','complete_backup.py','update_check.py','term_tools.py']:shutil.copy2(root/name,manager/name)
shutil.copy2(root/'client/build/credential-store',manager/'credential-store')
shutil.copy2(root/'client/build/learning-tool',manager/'learning-tool')
shutil.copy2(root/'client/build/ime-status',manager/'ime-status')
shutil.copy2(root/'client/build/engine-check',manager/'engine-check')
shutil.copy2(root/'branding/rime.pdf',client/'Contents/Resources/rime.pdf')
# App icon (光标 K): replaces Squirrel's Rime.icns and gives the settings helper the same icon.
shutil.copy2(root/'branding/KongFlow.icns',client/'Contents/Resources/Rime.icns')
(helper/'Contents/Resources').mkdir(parents=True,exist_ok=True)
shutil.copy2(root/'branding/KongFlow.icns',helper/'Contents/Resources/KongFlow.icns')
shutil.copytree(root/'runtime',manager/'runtime')
shutil.copytree(root/'web',manager/'web')
p=helper/'Contents/Info.plist';info={'CFBundleExecutable':'Qingyan','CFBundleIdentifier':'local.qingyan.manager','CFBundlePackageType':'APPL','LSMinimumSystemVersion':'13.0','NSAppTransportSecurity':{'NSAllowsLocalNetworking':True},'NSHighResolutionCapable':True};info['CFBundleURLTypes']=[{'CFBundleURLName':'KongIME settings','CFBundleURLSchemes':['kongime-settings']}]
info.update(CFBundleShortVersionString='0.37.0',CFBundleVersion='370',CFBundleDisplayName='KongFlow设置',CFBundleName='KongFlow',CFBundleIconFile='KongFlow',LSUIElement=True);p.write_bytes(plistlib.dumps(info))
p=client/'Contents/Info.plist';info=plistlib.loads(p.read_bytes());info['CFBundleDisplayName']='KongFlow';info['CFBundleName']='KongFlow';info['KongIMEVersion']='0.37.0';info['tsInputMethodIconFileKey']='rime.pdf';info['CFBundleVersion']='13100';info['CFBundleShortVersionString']='1.1.2-KongIME.0.37';info.pop('SUFeedURL',None);info['SUEnableAutomaticChecks']=False;p.write_bytes(plistlib.dumps(info))
def load_strings(raw):
    # Squirrel 1.1.2 ships UTF-16 XML that declares UTF-8; expat rejects it as-is.
    try:return plistlib.loads(raw)
    except Exception:
        if raw[:2] in (b'\xff\xfe',b'\xfe\xff'):return plistlib.loads(raw.decode('utf-16').encode('utf-8'))
        raise
for localized in (client/'Contents/Resources').glob('*.lproj/InfoPlist.strings'):
    values=load_strings(localized.read_bytes());values={k:v.replace('KongIME','KongFlow') if isinstance(v,str) else v for k,v in values.items()}
    # Name the input source KongFlow even when the payload still carries upstream 鼠须管/Squirrel strings.
    values.update({k:'KongFlow' for k in ['CFBundleDisplayName','CFBundleName','im.rime.inputmethod.Squirrel','im.rime.inputmethod.Squirrel.Hans','im.rime.inputmethod.Squirrel.Hant']})
    localized.write_bytes(plistlib.dumps(values))
# This custom client uses manual KongIME updates; upstream updates would remove the integration.
shutil.rmtree(client/'Contents/Frameworks/Sparkle.framework')
# AppleDouble files (._name) from archive extraction break code signing.
for stray in [x for x in client.rglob('._*') if x.is_file()]:stray.unlink()
# Extended attributes (Finder info, quarantine, provenance) on copied files make codesign
# fail with "resource fork, Finder information, or similar detritus not allowed".
subprocess.run(['xattr','-cr',str(client)],check=True)
subprocess.run(['codesign','--force','--deep','--options','0','--sign','-',str(client)],check=True)
subprocess.run(['codesign','--verify','--deep','--strict',str(client)],check=True)
components=[{'RootRelativeBundlePath':'Squirrel.app','BundleHasStrictIdentifier':True,'BundleIsRelocatable':False,'BundleIsVersionChecked':False,'BundleOverwriteAction':'upgrade'}]
componentFile=root/'client/build/components.plist';componentFile.write_bytes(plistlib.dumps(components))
subprocess.run(['pkgbuild','--root',str(stage),'--install-location','/Library/Input Methods','--identifier','local.kongime.inputmethod','--version','0.37.0','--component-plist',str(componentFile),'--scripts',str(root/'branding/installer-scripts'),str(root/'client/build/KongIME-component.pkg')],check=True)
build_installer.build(root/'client/build/KongIME-component.pkg',out/'安装KongFlow.pkg',root/'client/build/installer-v037','0.37.0')
shutil.copy2(root/'README-0.37.md',out/'开始使用.txt')
source=out/'源码';source.mkdir()
for n in ['LearningTool.cpp','EngineCheck.cpp','Launcher.swift','CredentialStore.swift','ChooseFolder.swift','IMEStatus.swift','app.py','core.py','workflow.py','jobs.py','quick.py','profile_backup.py','cloud_client.py','library_tools.py','personal_data.py','local_snapshots.py','learning.py','restore_review.py','phrase_tools.py','engine_check.py','upgrade_check.py','complete_backup.py','update_check.py','term_tools.py','sgpu_pinyin.json','build_integrated.py','build_installer.py','build_client.sh','README-0.37.md','VALIDATION-0.37.md']:shutil.copy2(root/n,source/n)
for n in ['web','licenses','tests','runtime','cloud','tools']:shutil.copytree(root/n,source/n,ignore=shutil.ignore_patterns('__pycache__'))
shutil.copytree(root/'client/sources',source/'client/sources')
shutil.copy2(root/'client/LICENSE.txt',source/'client/LICENSE.txt')
shutil.copytree(root/'branding/installer-scripts',source/'branding/installer-scripts')
for name in ['rime.pdf','KongFlow.icns']:shutil.copy2(root/'branding'/name,source/'branding'/name)
shutil.copytree(root/'branding/icon',source/'branding/icon',ignore=shutil.ignore_patterns('__pycache__'))
shutil.copytree(root/'client/build/installer-v037',source/'branding/installer')
archive=root.parent/'KongFlow-0.37-Mac.zip'
subprocess.run(['ditto','-c','-k','--sequesterRsrc','--keepParent',str(out),str(archive)],check=True)
with zipfile.ZipFile(archive) as z:
    assert z.testzip() is None
    assert not any(n.endswith('/state.json') for n in z.namelist())
# Disk image for double-click installation: the signed installer package and the guide.
image=root.parent/'KongFlow-0.37.dmg'
volume=root/'client/build/dmg-v037';volume.mkdir(exist_ok=False)
shutil.copy2(out/'安装KongFlow.pkg',volume/'安装KongFlow.pkg');shutil.copy2(out/'开始使用.txt',volume/'开始使用.txt')
subprocess.run(['hdiutil','create','-volname','KongFlow 0.37','-srcfolder',str(volume),'-fs','HFS+','-format','UDZO','-imagekey','zlib-level=9',str(image)],check=True)
subprocess.run(['hdiutil','verify',str(image)],check=True)
print(archive);print(image)
