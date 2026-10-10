# Real browser + generated media + fake Emby/302 servers. No user credentials.
import sys,subprocess,threading,json,re,time,faulthandler,os
os.environ["PW_TEST_SCREENSHOT_NO_FONTS_READY"]="1"
# All browser actions have bounded timeouts.
from pathlib import Path
sys.path.insert(0,str(Path(__file__).resolve().parents[1]));sys.path.insert(0,str(Path(__file__).parent/'deps'))
import imageio_ffmpeg
from http.server import BaseHTTPRequestHandler,ThreadingHTTPServer
from urllib.parse import urlsplit,parse_qs
from playwright.sync_api import sync_playwright
from server import AppServer
root=Path(__file__).resolve().parents[1];samples=root/'tests/samples';samples.mkdir(exist_ok=True)
ffmpeg=imageio_ffmpeg.get_ffmpeg_exe()
for name,video,audio in [('sample.mp4','libx264','aac'),('sample.mkv','libx264','ac3'),('hevc.mkv','libx265','eac3'),('sample.ts','libx264','aac')]:
    dest=samples/name
    if not dest.exists():subprocess.run([ffmpeg,'-hide_banner','-loglevel','error','-y','-f','lavfi','-i','testsrc2=size=640x360:rate=24','-f','lavfi','-i','sine=frequency=440:sample_rate=48000','-t','30','-c:v',video,'-preset','ultrafast','-g','24','-c:a',audio,'-b:a','128k',str(dest)],check=True)
sub=(samples/'subtitles.srt');sub.write_text('1\n00:00:00,000 --> 00:00:25,000\nSubtitle test\n',encoding='utf-8')
if not (samples/'multi.mkv').exists():subprocess.run([ffmpeg,'-hide_banner','-loglevel','error','-y','-i',str(samples/'sample.mkv'),'-f','lavfi','-i','sine=frequency=880:sample_rate=48000','-i',str(sub),'-map','0:v','-map','0:a','-map','1:a','-map','2:s','-t','30','-c:v','copy','-c:a:0','copy','-c:a:1','aac','-c:s','srt',str(samples/'multi.mkv')],check=True)
class Cloud(BaseHTTPRequestHandler):
    def log_message(self,*a):pass
    def do_GET(self):
        path=samples/urlsplit(self.path).path.rsplit('/',1)[-1]
        if not path.exists():self.send_error(404);return
        data=path.read_bytes();size=len(data);a=0;b=size-1
        if self.headers.get('Range'):
            m=re.fullmatch(r'bytes=(\d*)-(\d*)',self.headers['Range']);a=int(m[1] or 0);b=min(int(m[2] or b),b);self.send_response(206);self.send_header('Content-Range',f'bytes {a}-{b}/{size}')
        else:self.send_response(200)
        self.send_header('Content-Length',str(b-a+1));self.send_header('Accept-Ranges','bytes');self.end_headers()
        try:self.wfile.write(data[a:b+1])
        except (BrokenPipeError,ConnectionResetError):pass
class FakeEmby(BaseHTTPRequestHandler):
    cloud='';reports=[];catalog_reads=0
    def log_message(self,*a):pass
    def reply(self,result):
        payload=json.dumps(result).encode();self.send_response(200);self.send_header('Content-Type','application/json');self.send_header('Content-Length',str(len(payload)));self.end_headers();self.wfile.write(payload)
    def do_POST(self):
        data=json.loads(self.rfile.read(int(self.headers.get('Content-Length',0))) or b'{}')
        if 'AuthenticateByName' in self.path:self.reply({'AccessToken':'TEST_TOKEN','User':{'Id':'u','Name':'Test User'}})
        elif 'PlaybackInfo' in self.path:
            ident=self.path.split('/')[2];ext='strm';tracks=[{'Type':'Subtitle','Index':2,'IsExternal':True,'Codec':'srt','DisplayTitle':'中文字幕'},{'Type':'Subtitle','Index':3,'IsExternal':True,'Codec':'ass','DisplayTitle':'English ASS'}] if ident=='4' else [];self.reply({'MediaSources':[{'Id':ident,'Container':ext,'RunTimeTicks':300000000,'MediaStreams':[]}],'PlaySessionId':'test-'+ident})
        else:self.reports.append((self.path,data));self.reply({})
    def do_GET(self):
        if self.path.startswith('/Items/Filters'):
            self.send_error(404);return
        if '/Subtitles/' in self.path:
            content=(b'1\n00:00:00,000 --> 00:00:29,000\nExternal subtitle test\n' if 'Stream.srt' in self.path else b'[Script Info]\nScriptType: v4.00+\n[V4+ Styles]\nFormat: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\nStyle: Default,Arial,24,&H00FFFFFF,&H000000FF,&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,1,0,2,10,10,10,1\n[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\nDialogue: 0,0:00:00.00,0:00:29.00,Default,,0,0,0,,ASS external test\n')
            self.send_response(200);self.send_header('Content-Length',str(len(content)));self.end_headers();self.wfile.write(content);return
        if self.path.startswith('/Users/u/Views'):
            self.reply({'Items':[{'Id':'movies','Name':'电影','IsFolder':True},{'Id':'tv','Name':'电视剧','IsFolder':True}]});return
        if self.path.startswith('/Users/u/Items/'):
            ident=urlsplit(self.path).path.rsplit('/',1)[-1];self.reply({'Id':ident,'Name':'TS test','Overview':'Test overview from Emby','Genres':['Drama'],'People':[{'Id':'actor','Name':'Test Actor','Role':'Actor'}],'RunTimeTicks':300000000,'MediaSources':[{'Id':ident,'MediaStreams':[{'Type':'Video','Index':0}]}],'MediaStreams':([{'Type':'Subtitle','Index':2,'IsExternal':True,'Codec':'srt','DisplayTitle':'中文字幕'},{'Type':'Subtitle','Index':3,'IsExternal':True,'Codec':'ass','DisplayTitle':'English ASS'}] if ident=='4' else []),'UserData':{'PlaybackPositionTicks':120000000}});return
        if self.path.startswith('/Videos/'):
            ident=self.path.split('/')[2];name={'1':'sample.mp4','2':'multi.mkv','3':'hevc.mkv','4':'sample.ts'}[ident];self.send_response(302);self.send_header('Location',self.cloud+'/'+name);self.end_headers()
        else:
            FakeEmby.catalog_reads+=1
            items=[{'Id':str(i+1),'Name':name,'Genres':[['Drama','Action'],['Drama'],['Action'],['Drama','Action']][i],'ProductionYear':2024 if i%2==0 else 2019,'CommunityRating':8-i/10,'MediaSources':[{'Container':'mp4' if i==0 else 'mkv'}],'UserData':{}} for i,name in enumerate(['MP4 H264 AAC','MKV H264 AC3','MKV HEVC EAC3','TS H264 AAC'])]
            for item in items[:2]:item['People']=[{'Id':'actor','Name':'Test Actor'}]
            items[0]['Genres']+=['Extra%02d'%i for i in range(25)]
            q=parse_qs(urlsplit(self.path).query)
            if q.get('Genres'):
                self.send_error(500);return
            if q.get('Genres'):items=[x for x in items if any(g in x['Genres'] for g in q['Genres'][0].split('|'))]
            if q.get('Years'):items=[x for x in items if str(x['ProductionYear'])==q['Years'][0]]
            if q.get('PersonIds'):items=[x for x in items if x['Id'] in ['1','2']]
            start=int(q.get('StartIndex',[0])[0]);limit=int(q.get('Limit',[60])[0]);self.reply({'Items':items[start:start+limit],'TotalRecordCount':len(items)})
cloud=ThreadingHTTPServer(('127.0.0.1',0),Cloud);FakeEmby.cloud=f'http://127.0.0.1:{cloud.server_port}'
emby=ThreadingHTTPServer(('127.0.0.2',0),FakeEmby);app=AppServer(('127.0.0.1',0),allow_private_media=True)
for srv in [cloud,emby,app]:threading.Thread(target=srv.serve_forever,daemon=True).start()
art=root/'tests/artifacts';art.mkdir(exist_ok=True)
errors=[];http_errors=[];logs=[]
try:
 with sync_playwright() as p:
    print('BROWSER start',flush=True)
    browser=p.chromium.launch(channel='chrome',headless=True,args=['--autoplay-policy=no-user-gesture-required']);page=browser.new_page(viewport={'width':1440,'height':1000});page.on('pageerror',lambda e:(errors.append(str(e)),print('JSERROR',str(e),e.stack,flush=True)));page.on('console',lambda m:(logs.append(m.text),print('CONSOLE',m.type,m.text,flush=True)) if m.type in ['error','warning'] else None);page.on('response',lambda r:(print('HTTP',r.status,r.url,flush=True),http_errors.append(f'{r.status} {r.url}')) if r.status>=400 else None)
    print('NAV start',flush=True)
    page.goto(f'http://127.0.0.1:{app.server_port}/?launch={app.launch_key}&inline=1');page.goto(f'http://127.0.0.1:{app.server_port}/?inline=1');print('NAV done',flush=True);print('LOGIN PAGE',page.title(),flush=True)
    print('DOM',page.evaluate("()=>({ready:document.readyState,html:document.getElementById('loginPanel').outerHTML.slice(0,200),box:document.getElementById('server').getBoundingClientRect().toJSON()})"),flush=True)
    page.fill('#server',f'http://127.0.0.2:{emby.server_port}');print('SERVER filled',flush=True);page.fill('#username','test');print('USER filled',flush=True);page.fill('#password','pw');print('PASS filled',flush=True);page.click('#connect');page.wait_for_selector('.card');assert page.locator('.card').count()==4
    for i in range(3):
        print('START PLAY',i,flush=True);page.locator('.card').filter(has_text=['MP4 H264 AAC','MKV H264 AC3','MKV HEVC EAC3'][i]).click();print('CLICK done',i,flush=True);page.wait_for_timeout(2000);print('IMMEDIATE',page.evaluate("()=>[...state.players.values()].map(e=>({status:e.status.textContent,time:Number(e.player?.currentTime||0),p:e.player?.getStatus?.()}))"),flush=True)
        print('AUDIO',page.evaluate('AVPlayer.audioContext?.state'),flush=True);print('MEDIA',page.evaluate("()=>[...document.querySelectorAll('video,audio')].map(v=>({tag:v.tagName,paused:v.paused,ready:v.readyState,time:v.currentTime,error:v.error?.message,src:v.src}))"),flush=True)
        page.wait_for_function('''() => { const e=[...state.players.values()].at(-1); return !!e && (e.player && Number(e.player.currentTime)>1500 || e.status.classList.contains('playerError')); }''',timeout=30000,polling=100)
        info=page.evaluate('''() => { const e=[...state.players.values()].at(-1); return {time:Number(e.player?.currentTime||0),status:e.status.textContent,audioFrames:Number(e.player.getStats().audioFrameRenderCount),videoFrames:Number(e.player.getStats().videoFrameRenderCount)}; }''')
        print('PLAY',i,json.dumps(info,default=str,ensure_ascii=False),flush=True)
        assert info['time']>1500,info
        assert info['audioFrames']>0 and info['videoFrames']>0,info
    page.evaluate('''async()=>{const e=[...state.players.values()][1];const audio=e.player.getStreams().filter(s=>s.mediaType==='Audio');const subs=e.player.getStreams().filter(s=>s.mediaType==='Subtitle');if(audio.length!==2||subs.length!==1)throw Error('Fixture tracks missing');await e.player.selectAudio(audio[1].id,false);e.player.setSubtitleEnable(true);await e.player.seek(15000n);}''')
    page.wait_for_function('''()=>Number([...state.players.values()][1].player.currentTime)>15000''',timeout=30000,polling=100)
    assert len(app.plays)==3
    page.locator('.card').nth(3).click();page.wait_for_function('()=>state.players.size===4&&Number([...state.players.values()].at(-1).player?.currentTime||0)>500',timeout=30000,polling=100)
    page.locator('.card').nth(0).click();assert page.locator('.playerCard').count()==4
    assert '四' in page.locator('#notice').inner_text()
    assert len(app.plays)==4
    assert page.evaluate('()=>Number([...state.players.values()].at(-1).player.getStats().audioFrameRenderCount)>0&&Number([...state.players.values()].at(-1).player.getStats().videoFrameRenderCount)>0')
    print('PLAYING verified',flush=True);page.screenshot(path=str(art/'playing.png'),full_page=True,timeout=10000)
    page.click('#closeAll');page.wait_for_function('()=>state.players.size===0');deadline=time.monotonic()+10
    while app.plays and time.monotonic()<deadline:page.wait_for_timeout(100)
    assert len(app.plays)==0
    assert any(path=='/Sessions/Playing' for path,data in FakeEmby.reports);assert any(data.get('PositionTicks',0)>150000000 for path,data in FakeEmby.reports)
    page.evaluate("()=>{AVPlayer.prototype.load=async function(){throw Error('Injected stream open failure')};}")
    page.locator('.card').nth(0).click()
    page.wait_for_function("()=>document.querySelector('.playerStatus')?.textContent.includes('fileHeader')")
    assert page.get_by_text('复制播放诊断',exact=True).count()==1
    assert len(app.plays)==1
    page.click('#closeAll');page.wait_for_function('()=>state.players.size===0')
    page.evaluate("()=>{history.replaceState({},'', '/');}")
    page.locator('.cardTitle').nth(3).click()
    page.wait_for_function("()=>document.querySelector('#detailPage')?.textContent.includes('Test overview from Emby')")
    assert 'Test Actor' in page.locator('#detailPage').inner_text()
    assert '全部已获取元数据' in page.locator('#detailPage').inner_text()
    page.screenshot(path=str(art/'details-v07.png'),full_page=True)
    page.goto(f'http://127.0.0.1:{app.server_port}/?library=1')
    page.wait_for_selector('.card')
    with page.expect_popup() as popup:
        page.locator('.posterPlay').nth(3).click()
    tab=popup.value
    tab.wait_for_function('()=>typeof state!=="undefined"&&state.players.size===1&&Number([...state.players.values()][0].player?.currentTime||0)>12000',timeout=30000)
    assert tab.locator('#grid').is_hidden()
    tab.wait_for_function('()=>[...state.players.values()][0].subtitleSelection==="external:2"')
    assert tab.locator('header .playerOptions').count()==1
    assert tab.locator('.viewport .playerOptions').count()==0
    assert tab.locator('.directSeekButton').count()==2
    assert tab.evaluate('()=>{const h=document.querySelector("header .playerOptions").getBoundingClientRect(),v=document.querySelector(".viewport").getBoundingClientRect();return h.bottom<=v.top;}')
    tab.evaluate('async()=>{const e=[...state.players.values()][0];await e.player.pause();}')
    before_seek=tab.evaluate('()=>Number([...state.players.values()][0].player.currentTime)')
    tab.get_by_role('button',name='前进 5 秒',exact=True).click(force=True)
    tab.evaluate('async()=>await [...state.players.values()][0].shortSeekQueue')
    tab.evaluate('async()=>await [...state.players.values()][0].player.play()')
    tab.wait_for_function('()=>{const e=[...state.players.values()][0];return Math.abs(Number(e.player.currentTime)-e.lastShortSeek.target)<1500;}',timeout=10000)
    after_seek=tab.evaluate('()=>Number([...state.players.values()][0].player.currentTime)')
    forward=tab.evaluate('()=>[...state.players.values()][0].lastShortSeek')
    assert forward['target']-forward['from']==5000,forward
    assert abs(after_seek-forward['target'])<1500,(forward,after_seek)
    tab.get_by_role('button',name='后退 5 秒',exact=True).click(force=True)
    tab.evaluate('async()=>await [...state.players.values()][0].shortSeekQueue')
    tab.wait_for_function('()=>{const e=[...state.players.values()][0];return Math.abs(Number(e.player.currentTime)-e.lastShortSeek.target)<1500;}',timeout=10000)
    returned=tab.evaluate('()=>Number([...state.players.values()][0].player.currentTime)')
    backward=tab.evaluate('()=>[...state.players.values()][0].lastShortSeek')
    assert backward['from']-backward['target']==5000,backward
    assert abs(returned-backward['target'])<1500,(backward,returned)
    tab.evaluate('async()=>await [...state.players.values()][0].player.play()')
    print('PASS PLAYER CONTROLS: +/-5 seconds, toolbar outside video, automatic subtitle',flush=True)

    assert '加载本地' not in tab.locator('.playerOptions').inner_text()
    tab.locator('.avplayer-ui-control-subtitle-track-value').click(force=True)
    assert tab.locator('#settingsDialog input[type=file]').count()==1
    tab.wait_for_selector('#subtitleSelect')
    assert tab.locator('#subtitleSelect option[value^=external]').count()==2
    tab.select_option('#subtitleSelect','external:2');tab.wait_for_function('()=>!document.querySelector("#subtitleSelect").disabled');print('SUBTITLE DEBUG',tab.locator('.subtitleMessage').inner_text(),tab.evaluate('()=>[...state.players.values()][0].player.getStreams().map(s=>({id:s.id,type:s.mediaType,index:s.index}))'),flush=True);tab.wait_for_function('()=>[...state.players.values()][0].subtitleSelection==="external:2"')
    first_id=tab.evaluate('()=>[...state.players.values()][0].player.getSelectedSubtitleStreamId()')
    tab.select_option('#subtitleSelect','external:3');tab.wait_for_function('()=>[...state.players.values()][0].subtitleSelection==="external:3"')
    assert tab.evaluate('()=>[...state.players.values()][0].player.getSelectedSubtitleStreamId()')!=first_id
    tab.select_option('#subtitleSelect','external:2');tab.wait_for_function('()=>[...state.players.values()][0].subtitleSelection==="external:2"')
    assert tab.evaluate('()=>[...state.players.values()][0].player.getSelectedSubtitleStreamId()')==first_id
    tab.select_option('#subtitleSelect','none');tab.wait_for_function('()=>[...state.players.values()][0].subtitleSelection==="none"')
    tab.wait_for_timeout(300)
    assert tab.evaluate('()=>[...state.players.values()][0].subtitleSelection')=='none'
    print('PASS EMBY SUBTITLES: native menu opens unified selector, item-level fallback, SRT, ASS, switching, reuse, off',flush=True)
    tab.click('#settingsClose')
    tab.evaluate('()=>document.querySelector(".playerCard").dispatchEvent(new MouseEvent("mousemove"))')
    tab.screenshot(path=str(art/'player-v05.png'),full_page=True)
    tab.evaluate('async()=>{const e=[...state.players.values()][0];await e.player.seek(15000n);}')
    tab.wait_for_function('()=>Number([...state.players.values()][0].player.currentTime)>15000',timeout=30000)
    assert tab.evaluate('()=>Number([...state.players.values()][0].player.getStats().audioFrameRenderCount)>0')
    tab.get_by_role('button',name='播放信息',exact=True).click(force=True)
    tab.wait_for_function("()=>document.querySelector('#infoText').textContent.includes('totalFirstPlayMs')")
    assert tab.locator('#infoDialog').is_visible()
    assert 'externalTracks' in tab.locator('#infoText').inner_text()
    print('PERFORMANCE',tab.locator('#infoText').inner_text()[:700],flush=True)
    tab.close()
    page.goto(f'http://127.0.0.1:{app.server_port}/?library=1&parent=movies&categoryName=电影')
    page.wait_for_function('()=>!state.loading&&document.querySelectorAll(".card").length===4')
    page.wait_for_function("()=>document.querySelectorAll('#genreFilters button').length===28")
    assert page.locator('#genreFilters button:not([hidden])').count()==11
    assert page.locator('#genreFilters button[hidden]').count()==17
    assert page.locator('#genreExpand').get_attribute('aria-expanded')=='false'
    page.click('#genreExpand');assert page.locator('#genreFilters button:not([hidden])').count()==28
    assert page.locator('#genreExpand').get_attribute('aria-expanded')=='true'
    page.locator('#genreFilters').get_by_role('button',name='Extra24',exact=True).click()
    page.wait_for_function('()=>!state.loading&&document.querySelectorAll(".card").length===1')
    page.click('#genreExpand');assert page.locator('#genreFilters').get_by_role('button',name='Extra24',exact=True).is_visible()
    page.click('#clearFilters');page.wait_for_function('()=>!state.loading&&document.querySelectorAll(".card").length===4')
    print('PASS COLLAPSE + HTTP500: ten options, expand, selected retained, genre query fallback',flush=True)
    reads=FakeEmby.catalog_reads
    probe=page.evaluate("async()=>BrowserCatalog.items(new URLSearchParams('parent=movies&genres=Drama&sort=name&videos=1'))")
    assert probe['QueryStrategy']=='browser-index' and FakeEmby.catalog_reads==reads
    assert page.locator('#categoriesTab').count()==0
    page.click('#historyTab');page.wait_for_function('()=>!state.loading&&state.tab==="history"')
    assert page.locator('.card').count()>=3
    page.goto(f'http://127.0.0.1:{app.server_port}/?library=1&parent=movies')
    page.wait_for_function('()=>!state.loading&&document.querySelectorAll(".card").length===4')
    reads=FakeEmby.catalog_reads
    page.reload();page.wait_for_function('()=>!state.loading&&document.querySelectorAll(".card").length===4')
    assert FakeEmby.catalog_reads==reads
    assert page.evaluate("()=>localStorage.getItem('directweb.server')") is None
    isolation=page.evaluate("async()=>{const session=await api('session');BrowserCatalog.setSession({storageScope:'different-account'},api);const data=await BrowserCatalog.items(new URLSearchParams('tab=history'));const ready=await BrowserCatalog.ready('movies');BrowserCatalog.setSession(session,api);return !ready&&data.TotalRecordCount===0;}")
    assert isolation
    print('PASS BROWSER CACHE: local filtering, reload persistence, account isolation, history, no saved credentials',flush=True)
    page.locator('#genreFilters').get_by_role('button',name='Drama',exact=True).click()
    page.wait_for_function('()=>!state.loading&&document.querySelectorAll(".card").length===3')
    page.locator('#genreFilters').get_by_role('button',name='Action',exact=True).click()
    page.wait_for_function('()=>!state.loading&&document.querySelectorAll(".card").length===4')
    page.click('#filterSettings');page.select_option('#genreMatch','and');page.click('#filterSettingsClose')
    page.wait_for_function('()=>!state.loading&&document.querySelectorAll(".card").length===2')
    page.locator('#sortFilters').get_by_role('button',name='评分最高',exact=True).click()
    page.wait_for_function('()=>!state.loading&&state.sort==="rating"')
    prior=page.url
    page.locator('.cardTitle').first.click();page.wait_for_selector('.detailBack')
    assert page.locator('.genreLink').inner_text()=='Drama'
    page.click('.detailBack');page.wait_for_function('()=>!state.loading&&state.parent==="movies"&&state.match==="and"&&state.genres.length===2&&state.sort==="rating"')
    assert page.url==prior
    page.locator('.cardTitle').first.click();page.wait_for_selector('.personCard')
    page.click('.personCard');page.wait_for_function('()=>!state.loading&&state.person==="actor"&&document.querySelectorAll(".card").length===2')
    page.locator('.cardTitle').first.click();page.wait_for_selector('.genreLink');page.click('.genreLink')
    page.wait_for_function('()=>!state.loading&&state.genres[0]==="Drama"&&state.person==="actor"')
    page.click('#clearFilters');page.wait_for_function('()=>!state.loading&&state.genres.length===0&&state.person===""')
    page.select_option('#yearSelect','2024')
    page.wait_for_function('()=>!state.loading&&document.querySelectorAll(".card").length===2')
    assert page.locator('#yearSelect').input_value()=='2024'
    page.reload();page.wait_for_function('()=>typeof state!=="undefined"&&!state.loading&&state.year==="2024"&&document.querySelectorAll(".card").length===2')
    assert page.locator('#yearSelect').input_value()=='2024'
    print('PASS CATALOG: categories, OR/AND, actor, genre, year, sorting, detail return preserves library context',flush=True)
    page.click('#filterSettings');page.click('#clearBrowserData')
    page.wait_for_function("()=>document.getElementById('clearBrowserDataStatus').textContent.length>0")
    assert page.evaluate("async()=>(await BrowserCatalog.items(new URLSearchParams('tab=history'))).TotalRecordCount") == 0
    print('PASS CLEAR BROWSER HISTORY',flush=True)
    page.click('#filterSettingsClose')
    page.screenshot(path=str(art/'library-v010.png'),full_page=True)
    assert not any('[error]' in line for line in logs),logs
    assert not errors,errors
    assert not http_errors,http_errors
    print('PASS: login, 4 concurrent streams, AAC/AC3/EAC3/HEVC, audio switching, embedded subtitle detection, seek, reporting, close; isolated=',page.evaluate('crossOriginIsolated'),flush=True)
    page.set_viewport_size({'width':700,'height':900});print('NARROW',page.evaluate('document.body.scrollWidth'),flush=True)
    browser.close()
finally:
 print('DIAG',json.dumps({'errors':errors,'http_errors':http_errors,'warnings':logs[-15:]},ensure_ascii=False),flush=True)
 try:
  print('STATE',page.evaluate("()=>[...state.players.values()].map(e=>({status:e.status.textContent,time:Number(e.player?.currentTime||0),started:e.started,playerStatus:e.player?.getStatus?.()}))"),flush=True)
 except Exception:pass
 (art/'browser-log.json').write_text(json.dumps({'errors':errors,'http_errors':http_errors,'warnings':logs},ensure_ascii=False,indent=2),encoding='utf-8')
 for srv in [app,emby,cloud]:srv.shutdown();srv.server_close()
