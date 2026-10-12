"""Create a clean GitHub-ready source distribution including replaceable assets."""
from pathlib import Path
import zipfile
root=Path(__file__).resolve().parents[1]
output=root/'EmbyDirectWeb-Source-v0.18.zip'
paths=[root/name for name in ['core.py','server.py','catalog.py','subtitles.py','launcher.py','README.md','requirements.txt','requirements-dev.txt','.gitignore','package.json','package-lock.json']]
paths+=list((root/'tools').glob('*.py'))+list((root/'tests').glob('test_*.py'))+list((root/'tests').glob('test_*.cjs'))
for folder in ['web','licenses','docs']:
    paths.extend(p for p in (root/folder).rglob('*') if p.is_file())
with zipfile.ZipFile(output,'w',zipfile.ZIP_DEFLATED) as archive:
    for path in sorted(set(paths)):
        archive.write(path,'EmbyDirectWeb-Source/'+path.relative_to(root).as_posix())
print('SOURCE',output,'files',len(set(paths)),'bytes',output.stat().st_size)
