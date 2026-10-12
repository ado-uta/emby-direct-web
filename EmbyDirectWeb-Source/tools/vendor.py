from pathlib import Path
import shutil, requests, concurrent.futures, json
root=Path(__file__).resolve().parents[1]
out=root/'web/vendor';out.mkdir(parents=True,exist_ok=True)
for f in (root/'node_modules/@libmedia/avplayer-ui/dist/umd').glob('*.js'): shutil.copy2(f,out/f.name)
# AVPlayer initializes Worklet even when explicitly disabled. Respect the instance option.
bundle=out/'avplayer.js'
text=bundle.read_text(encoding='utf-8')
needle='A.A.audioWorklet&&await(0,me.A)(Ue.audioContext'
assert text.count(needle)==1, 'Upstream changed: review audio compatibility patch'
text=text.replace(needle,'A.A.audioWorklet&&Ue.Instances.some(e=>e.options.enableAudioWorklet)&&await(0,me.A)(Ue.audioContext')
assert text.count('async destroy(){await super.destroy(),this.keyboard.destroy(),this.ui.destroy()}')==1
text=text.replace('async destroy(){await super.destroy(),this.keyboard.destroy(),this.ui.destroy()}','async destroy(){this.keyboard.destroy(),this.ui.destroy(),await super.destroy()}')
assert text.count('g.ioReader=d,g.ioWriter=f,')==1
text=text.replace('g.ioReader=d,g.ioWriter=f,','g.ioReader=d,g.ioWriter=f,g.directwebDurationMs=e.formatOptions?.directwebDurationMs,')
from audio_patch import patch_audio
text=patch_audio(text)
bundle.write_text(text,encoding='utf-8')
ts=out/'502.avplayer.js'
ts_text=ts.read_text(encoding='utf-8')
old='let I=(0,i.d)(e.streams,A,t.timeBase);const x=g-(0,i.d)(e.streams,BigInt(1e4),c.i0),P=(0,i.d)(e.streams,BigInt(1e4),c.i0);'
new='let I=(0,i.d)(e.streams,A,t.timeBase);const dwDuration=Number(e.directwebDurationMs);const dwKnown=Number.isFinite(dwDuration)&&dwDuration>10000;const dwWindow=dwKnown?g*BigInt(10000)/BigInt(Math.round(dwDuration)):(0,i.d)(e.streams,BigInt(1e4),c.i0);if(dwKnown){const dwRelative=(0,o.k)(A,t.timeBase,c.i0);I=g*(dwRelative>BigInt(2000)?dwRelative-BigInt(2000):BigInt(0))/BigInt(Math.round(dwDuration));}const x=g-dwWindow,P=dwWindow;'
assert ts_text.count(old)==1
ts_text=ts_text.replace(old,new)
helper="function directwebEstimate(points,target,low,high,previous,initialFallback){\n const sorted=points.filter(p=>typeof p.pos==='bigint'&&typeof p.time==='bigint').sort((a,b)=>a.time<b.time?-1:a.time>b.time?1:0);\n let left=null,right=null;\n for(const point of sorted){if(point.time<=target)left=point;else if(!right)right=point;}\n if(!left||!right){const nearby=sorted.slice().sort((a,b)=>{const da=a.time>target?a.time-target:target-a.time;const db=b.time>target?b.time-target:target-b.time;return da<db?-1:da>db?1:0;}).slice(0,2).sort((a,b)=>a.time<b.time?-1:1);left=nearby[0];right=nearby[1];}\n const fallback=typeof initialFallback==='bigint'?initialFallback:(low+high)>>1n;\n if(!left||!right||right.time<=left.time||right.pos<=left.pos)return fallback;\n let guess=left.pos+(target-left.time)*(right.pos-left.pos)/(right.time-left.time);\n if(guess<=low||guess>=high||guess===previous)return fallback;\n return guess;\n}"
anchor='const b=(0,s._5)();let S=g,k=BigInt(0);'
assert ts_text.count(anchor)==1
ts_text=ts_text.replace(anchor,helper+'const dwBase=(0,o.k)(t.startTime!==c.Dh?t.startTime:t.firstDTS,t.timeBase,c.i0);const dwPoints=e.directwebSeekPoints||(e.directwebSeekPoints=[]);if(!dwPoints.length&&dwBase>=0n)dwPoints.push({pos:p,time:dwBase});'+anchor)
ts_text=ts_text.replace('const n=(0,o.Mr)(r.f[17](b+8),b+72,c.i0);let p=n-y;','const n=(0,o.Mr)(r.f[17](b+8),b+72,c.i0);if(!dwPoints.some(v=>v.pos===i)){dwPoints.push({pos:i,time:n});if(dwPoints.length>64)dwPoints.splice(1,1);}let p=n-y;')
assert ts_text.count('p>BigInt(0)?(S=I,I=k+S>>BigInt(1)):(k=I,I=k+S>>BigInt(1))')==1
ts_text=ts_text.replace('p>BigInt(0)?(S=I,I=k+S>>BigInt(1)):(k=I,I=k+S>>BigInt(1))','p>BigInt(0)?S=I:k=I;I=directwebEstimate(dwPoints,y-BigInt(2000),k,S,I)')
assert ts_text.count('const b=(0,s._5)();let S=g,k=BigInt(0);')==1
ts_text=ts_text.replace('const b=(0,s._5)();let S=g,k=BigInt(0);','if(dwPoints.length>=2){I=directwebEstimate(dwPoints,y-BigInt(2000),p,x,BigInt(-1),I);}const b=(0,s._5)();let S=g,k=BigInt(0);')
ts.write_text(ts_text,encoding='utf-8')

ref='v1.3.1' 
r=requests.get(f'https://api.github.com/repos/zhaohappy/libmedia/git/trees/{ref}?recursive=1',timeout=60);r.raise_for_status()
tree=r.json();paths=[x['path'] for x in tree['tree'] if x['path'].startswith(('dist/decode/','dist/resample/','dist/stretchpitch/')) and x['path'].endswith('.wasm') and '-64' not in x['path'] and '-atomic' not in x['path']]
def get(path):
 dest=root/'web/wasm'/path.removeprefix('dist/');dest.parent.mkdir(parents=True,exist_ok=True)
 if not dest.exists():
  r=requests.get('https://raw.githubusercontent.com/zhaohappy/libmedia/'+tree['sha']+'/'+path,timeout=90);r.raise_for_status();dest.write_bytes(r.content)
 return dest.stat().st_size
with concurrent.futures.ThreadPoolExecutor(max_workers=8) as ex: sizes=list(ex.map(get,paths))
(root/'web/vendor/versions.json').write_text(json.dumps({'avplayer':'1.3.1','wasm_commit':tree['sha'],'wasm_files':len(paths),'bytes':sum(sizes)},indent=2),encoding='utf-8')
lic=root/'licenses';lic.mkdir(exist_ok=True)
shutil.copy2(root/'node_modules/@libmedia/avplayer/COPYING.LGPLv3',lic/'libmedia-LGPLv3.txt')
print('Vendored',len(paths),'wasm files;',sum(sizes),'bytes')
