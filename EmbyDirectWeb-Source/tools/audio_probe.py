"""Synthetic PCM quality and scheduling probe; no real credentials or media."""
from pathlib import Path
prefix=Path(__file__).with_name('browser_smoke.py').read_text(encoding='utf-8').split('try:'+chr(10)+' with sync_playwright() as p:')[0]
exec(compile(prefix,'browser_smoke-fixture','exec'))
try:
 with sync_playwright() as p:
  browser=p.chromium.launch(channel='chrome',headless=True,args=['--autoplay-policy=no-user-gesture-required'])
  page=browser.new_page()
  page.goto(f'http://127.0.0.1:{app.server_port}/?launch={app.launch_key}&inline=1')
  page.goto(f'http://127.0.0.1:{app.server_port}/?inline=1')
  page.evaluate("""()=>{window.audioProbe=[];const original=AudioBufferSourceNode.prototype.start;AudioBufferSourceNode.prototype.start=function(when,...args){const b=this.buffer;if(b){const a=b.getChannelData(0);let peak=0,power=0,cross=0,maxStep=0;for(let i=0;i<a.length;i++){peak=Math.max(peak,Math.abs(a[i]));power+=a[i]*a[i];if(i){if(a[i-1]<0&&a[i]>=0)cross++;maxStep=Math.max(maxStep,Math.abs(a[i]-a[i-1]));}}window.audioProbe.push({when,now:this.context.currentTime,rate:b.sampleRate,length:a.length,peak,rms:Math.sqrt(power/a.length),cross,maxStep,first:a[0],last:a.at(-1)});}return original.call(this,when,...args);};}""")
  page.fill('#server',f'http://127.0.0.2:{emby.server_port}');page.fill('#username','test');page.fill('#password','pw');page.click('#connect');page.wait_for_selector('.card')
  page.locator('.card').filter(has_text='MKV H264 AC3').click()
  page.wait_for_function('()=>[...state.players.values()][0]?.player&&Number([...state.players.values()][0].player.currentTime)>1000',timeout=30000)
  page.wait_for_timeout(2000)
  page.evaluate('()=>window.audioProbe=[]')
  for target in [15000,3000,21000]:
   page.evaluate('async target=>await [...state.players.values()][0].player.seek(BigInt(target))',target)
   page.wait_for_timeout(1500)
  page.wait_for_timeout(2000)
  data=page.evaluate('()=>({contextRate:AVPlayer.audioContext.sampleRate,stats:[...state.players.values()][0].player.getStats(),blocks:audioProbe})')
  data['stats']={k:str(v) for k,v in data['stats'].items()}
  Path('tests/artifacts/audio-probe.json').write_text(json.dumps(data,indent=2),encoding='utf-8')
  blocks=data['blocks'];late=[b for b in blocks if b['now']-b['when']>.005]
  print(json.dumps({'blocks':len(blocks),'lateBlocks':len(late),'maxLateMs':max([(b['now']-b['when'])*1000 for b in blocks] or [0]),'peak':max([b['peak'] for b in blocks] or [0]),'rms':sum(b['rms'] for b in blocks)/max(1,len(blocks)),'maxSampleStep':max([b['maxStep'] for b in blocks] or [0]),'rates':list(set(b['rate'] for b in blocks))}))
  assert max([(b['now']-b['when'])*1000 for b in blocks] or [0])<100, 'Audio scheduled in past after seek'
  browser.close()
finally:
 for srv in [app,emby,cloud]:srv.shutdown();srv.server_close()
