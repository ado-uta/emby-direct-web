import hashlib,json,shutil,subprocess,sys,zipfile
from pathlib import Path
root=Path(__file__).resolve().parents[1]
cmd=[sys.executable,'-m','PyInstaller','--noconfirm','--onedir','--windowed','--name','EmbyDirectWeb','--contents-directory','runtime','--paths',str(root/'tools/tray-deps'),'--exclude-module','numpy','--hidden-import','pystray._win32','--add-data',str(root/'web')+';web','--add-data',str(root/'licenses')+';licenses',str(root/'launcher.py')]
subprocess.run(cmd,cwd=root,check=True)
folder=root/'dist/EmbyDirectWeb'
shutil.copy2(root/'README.md',folder/'README.md')
shutil.copytree(root/'licenses',folder/'licenses',dirs_exist_ok=True)
with zipfile.ZipFile(folder/'Source.zip','w',zipfile.ZIP_DEFLATED) as archive:
 paths=[root/p for p in ['subtitles.py','catalog.py','core.py','server.py','launcher.py','README.md','requirements.txt','requirements-dev.txt','.gitignore','package.json','package-lock.json']]
 paths+=list((root/'tools').glob('*.py'))+list((root/'tests').glob('test_*.py'))+list((root/'tests').glob('test_*.cjs'))+list((root/'web').glob('*.*'))+list((root/'docs').glob('*.md'))
 for path in paths:archive.write(path,path.relative_to(root).as_posix())
manifest={p.relative_to(folder).as_posix():hashlib.sha256(p.read_bytes()).hexdigest() for p in folder.rglob('*') if p.is_file() and p.name!='SHA256.json'}
(folder/'SHA256.json').write_text(json.dumps(manifest,indent=2),encoding='utf-8')
output=root/'EmbyDirectWeb-Windows-v0.17.zip'
with zipfile.ZipFile(output,'w',zipfile.ZIP_DEFLATED) as archive:
 for path in folder.rglob('*'):
  if path.is_file():archive.write(path,path.relative_to(folder.parent).as_posix())
print('PACKAGE',output,'bytes',output.stat().st_size,flush=True)
