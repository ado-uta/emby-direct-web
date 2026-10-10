"use strict";
const $=id=>document.getElementById(id);
const state={parent:null,stack:[],search:'',resume:false,start:0,total:0,players:new Map(),loading:false,closingPlayers:0,genres:[],year:'',person:'',personName:'',sort:'name',tab:'films',match:localStorage.getItem('directweb.genreMatch')||'or',scroll:0};
restoreCatalogState();
async function api(path,data){const options={credentials:'same-origin',headers:{}};if(data!==undefined){options.method='POST';options.headers['Content-Type']='application/json';options.body=JSON.stringify(data);}const response=await fetch('/api/'+path,options);const result=await response.json();if(!response.ok)throw new Error(result.error||`HTTP ${response.status}`);return result;}
function notice(message){$('notice').textContent=message||'';}
const remembered=localStorage.getItem('directweb.remember')==='1';$('rememberConnection').checked=remembered;if(remembered){$('server').value=localStorage.getItem('directweb.server')||'';$('username').value=localStorage.getItem('directweb.username')||'';}else{localStorage.removeItem('directweb.server');localStorage.removeItem('directweb.username');}
$('loginForm').onsubmit=async event=>{event.preventDefault();$('connect').disabled=true;$('loginError').textContent='';try{const data={server:$('server').value.trim(),username:$('username').value,password:$('password').value,ua:$('ua').value.trim()};const result=await api('login',data);if($('rememberConnection').checked){localStorage.setItem('directweb.remember','1');localStorage.setItem('directweb.server',data.server);localStorage.setItem('directweb.username',data.username);}else{localStorage.removeItem('directweb.remember');localStorage.removeItem('directweb.server');localStorage.removeItem('directweb.username');}BrowserCatalog.setSession(result,api);preloadCatalog();$('password').value='';$('accountName').textContent=result.name;$('loginPanel').hidden=true;$('libraryPanel').hidden=false;$('logout').hidden=false;await loadCategories();await loadItems();}catch(error){$('loginError').textContent=error.message;}finally{$('connect').disabled=false;}};
$('logout').onclick=async()=>{try{await closeAll();await api('logout',{});location.reload();}catch(error){notice(error.message);}};
async function loadItems(){if(state.loading)return;state.loading=true;notice('正在读取媒体库…');$('grid').replaceChildren();const q=catalogQuery();if(state.parent)q.set('parent',state.parent);if(state.search)q.set('search',state.search);if(state.resume)q.set('resume','1');try{const data=state.resume?await api('items?'+q):await BrowserCatalog.items(q);state.total=data.TotalRecordCount||0;await loadFilterOptions();renderCatalogFilters();saveCatalogState();for(const item of data.Items||[])addCard(item);notice((data.Items||[]).length?'':'没有找到影片或文件夹。');$('page').textContent=`${Math.floor(state.start/60)+1} / ${Math.max(1,Math.ceil(state.total/60))}`;$('previous').disabled=state.start===0;$('next').disabled=state.start+60>=state.total;$('back').hidden=!state.stack.length;$('libraryTitle').textContent=state.tab==='history'?'历史播放':state.resume?'继续观看':state.search?'搜索结果':state.personName?state.personName+'的作品':state.stack.at(-1)?.name||'媒体库';$('crumb').textContent=state.stack.map(x=>x.name).join(' / ');}catch(error){notice(error.message);}finally{state.loading=false;}}
function openPlayback(item){if(new URLSearchParams(location.search).has('inline'))startPlayer(item);else window.open('/?play='+encodeURIComponent(item.Id),'_blank','noopener');}
function addCard(item){
 const card=document.createElement('article');card.className='card';card.tabIndex=0;card.setAttribute('role','link');card.title=item.Name;
 const poster=document.createElement('div');poster.className='poster';const fallback=document.createElement('b');fallback.textContent=item.IsFolder?'▦':'▶';poster.append(fallback);
 if(item.ImageTags?.Primary){const img=document.createElement('img');img.src='/api/image/'+encodeURIComponent(item.Id);img.alt=item.Name;img.loading='lazy';img.onerror=()=>img.remove();poster.append(img);}
 const title=document.createElement('span');title.className='cardTitle';title.textContent=item.Name;
 const meta=document.createElement('span');meta.className='cardMeta';meta.textContent=item.IsFolder?'查看分类全部视频':[item.ProductionYear,item.MediaSources?.[0]?.Container?.toUpperCase()].filter(Boolean).join(' · ');
 if(!item.IsFolder){const play=document.createElement('button');play.className='posterPlay';play.innerHTML='<svg viewBox="0 0 24 24" aria-hidden="true"><path d="M8 5v14l11-7z"/></svg>';play.title='直接播放';play.setAttribute('aria-label','播放 '+item.Name);play.onclick=event=>{event.stopPropagation();openPlayback(item);};poster.append(play);}
 if(item.CommunityRating){const rating=textElement('span',Number(item.CommunityRating).toFixed(1),'posterRating');poster.append(rating);}
 if(item.UserData?.PlaybackPositionTicks&&item.RunTimeTicks){const bar=document.createElement('div');bar.className='progress';bar.style.width=Math.min(100,item.UserData.PlaybackPositionTicks/item.RunTimeTicks*100)+'%';poster.append(bar);}
 const navigate=()=>{if(item.IsFolder){if(state.loading)return;state.stack.push({parent:state.parent,name:item.Name});Object.assign(state,{parent:item.Id,start:0,search:'',resume:false});loadItems();}else if(new URLSearchParams(location.search).has('inline'))startPlayer(item);else {state.scroll=scrollY;saveCatalogState();location.href='/?detail='+encodeURIComponent(item.Id)+'&return='+encodeURIComponent(location.pathname+location.search);}};
 card.append(poster,title,meta);card.onclick=navigate;card.onkeydown=event=>{if(event.target===card&&event.key==='Enter')navigate();};$('grid').append(card);
}
$('home').onclick=()=>{if(state.loading)return;state.tab='films';state.resume=false;loadItems();};
$('resume').onclick=()=>{if(state.loading)return;Object.assign(state,{parent:null,stack:[],search:'',resume:true,start:0,tab:'films'});loadItems();};
$('back').onclick=()=>{if(state.loading)return;state.parent=state.stack.pop()?.parent||null;state.start=0;loadItems();};
$('searchForm').onsubmit=event=>{event.preventDefault();if(state.loading)return;Object.assign(state,{search:$('search').value.trim(),resume:false,parent:null,stack:[],start:0});loadItems();};
$('previous').onclick=()=>{if(state.loading)return;state.start=Math.max(0,state.start-60);loadItems();};$('next').onclick=()=>{if(state.loading)return;state.start+=60;loadItems();};
function updateLayout(){const count=state.players.size;let layout=Number($('layout').value);if(count>layout){layout=count>2?4:2;$('layout').value=String(layout);}$('players').className='players'+(layout===2?' two':layout===4?' four':'');$('playArea').hidden=!count;$('playCount').textContent=`(${count}/4)`;}
$('layout').onchange=updateLayout;
async function report(entry,event,release=true){if(!entry.key)return;if(entry.started||entry.historyRecorded){entry.historyRecorded=true;await BrowserCatalog.record(entry.item,entry.finalMilliseconds??Number(entry.player?.currentTime||0),entry.browserScope);}try{await api('report',{key:entry.key,event,milliseconds:entry.finalMilliseconds??Number(entry.player?.currentTime||0),paused:entry.paused,release});if(event!=='Stopped')entry.syncError='';}catch(error){entry.syncError=error.message;if(event!=='Stopped')entry.status.textContent='播放继续；进度同步失败：'+error.message;}}
async function startPlayer(item){AVPlayer.startAudioContext().catch(error=>notice('音频初始化失败：'+error.message));AVPlayer.audioContext?.resume().catch(()=>{});if(state.players.size>=4){notice('最多同时打开四个播放区域，请先关闭一个。');return;}const clickedAt=performance.now();const id=crypto.randomUUID();const card=document.createElement('article');card.className='playerCard';const top=document.createElement('div');top.className='playerTop';const title=document.createElement('strong');title.textContent=item.Name;const close=document.createElement('button');close.textContent='关闭';const viewport=document.createElement('div');viewport.className='viewport';const status=document.createElement('div');status.className='playerStatus';status.textContent='正在验证 302 直链和分段读取…';top.append(title,close);card.append(top,viewport,status);const entry={id,card,status,clickedAt,item,browserScope:BrowserCatalog.scope,player:null,key:null,paused:false,closed:false,started:false,reportQueue:Promise.resolve()};state.players.set(id,entry);$('players').append(card);updateLayout();close.onclick=()=>closePlayer(entry);notice('');
try{const source=await api('play',{id:item.Id});entry.key=source.key;entry.prepareMs=Math.round(performance.now()-entry.clickedAt);if(entry.closed){await report(entry,'Stopped');return;}status.textContent=`已验证 302 → ${source.host} · 本机原文件中转 · 浏览器解码`;
const player=new AVPlayer({container:viewport,wasmBaseUrl:location.origin+'/wasm',enableHardware:true,enableWebCodecs:true,enableWorker:true,enableWebGPU:false,enableAudioWorklet:false,preLoadTime:1,ui:{hasFolder:false,hasHeader:false}});entry.player=player;
const enqueue=event=>{if(event==='Progress'&&entry.progressPending)return;if(event==='Progress')entry.progressPending=true;entry.reportQueue=entry.reportQueue.then(()=>report(entry,event)).finally(()=>{if(event==='Progress')entry.progressPending=false;});};
player.on('error',error=>showPlaybackError(entry,error));
player.on('played',()=>{if(!entry.firstPlayMs)entry.firstPlayMs=Math.round(performance.now()-entry.loadAt);entry.ended=false;entry.paused=false;if(!entry.started){entry.started=true;enqueue('Playing');}else enqueue('Progress');});player.on('paused',()=>{entry.paused=true;if(entry.started)enqueue('Progress');});player.on('seeking',()=>{entry.seekAt=performance.now();});player.on('seeked',()=>{entry.lastSeekMs=entry.seekAt?Math.round(performance.now()-entry.seekAt):null;if(entry.started)enqueue('Progress');});player.on('ended',()=>{entry.ended=true;entry.started=false;entry.reportQueue=entry.reportQueue.then(()=>report(entry,'Stopped',false));});
entry.loadAt=performance.now();await player.load(location.origin+source.url,{ext:source.container==='mpegts'?'ts':source.container||undefined,maxProbeDuration:source.container==='mpegts'?1:3,formatOptions:{directwebDurationMs:source.container==='mpegts'?(source.durationMs||Math.floor((item.RunTimeTicks||0)/10000)):0}});if(entry.closed)return;
const options=document.createElement('div');options.className='playerOptions';entry.options=options;const performanceButton=document.createElement('button');performanceButton.textContent='播放信息';performanceButton.onclick=async()=>{await getEmbySubtitles(entry).catch(error=>entry.subtitleError=error.message);const d=await api('diagnostic?key='+encodeURIComponent(entry.key));const text=JSON.stringify({...d,prepareMs:entry.prepareMs,decodeAndBufferMs:entry.firstPlayMs,totalFirstPlayMs:entry.firstPlayMs+entry.prepareMs,lastSeekMs:entry.lastSeekMs,subtitleError:entry.subtitleError||null,playerStats:entry.player.getStats()},(_,v)=>typeof v==='bigint'?String(v):v,2);$('infoText').textContent=text;$('infoDialog').showModal();};options.append(performanceButton);const label=document.createElement('label');label.textContent='加载本地外挂字幕';const file=document.createElement('input');file.type='file';file.accept='.srt,.ass,.ssa,.vtt';file.onchange=async()=>{if(!file.files[0])return;try{await player.loadExternalSubtitle({source:file.files[0],title:file.files[0].name});player.setSubtitleEnable(true);}catch(error){status.textContent='外挂字幕加载失败：'+error.message;}};label.append(file);const settings=document.createElement('button');settings.textContent='⚙ 播放设置';settings.onclick=()=>openSubtitleSettings(entry,label);options.append(settings);if(document.body.classList.contains("playbackPage"))document.querySelector("header").insertBefore(options,document.querySelector("header .account"));else top.insertBefore(options,close);installSeekButtons(entry,viewport,source.durationMs||Math.floor((item.RunTimeTicks||0)/10000));viewport.addEventListener('click',event=>{if(event.target.closest('.avplayer-ui-control-subtitle-track')){event.preventDefault();event.stopImmediatePropagation();openSubtitleSettings(entry,label);}},true);
const ticks=new URLSearchParams(location.search).get('start')==='0'?0:item.UserData?.PlaybackPositionTicks;if(ticks>0){status.textContent='正在定位上次观看进度…';await player.seek(BigInt(Math.floor(ticks/10000)));}await player.play();primeEmbySubtitles(entry).catch(error=>{entry.subtitleError=error.message;});entry.timer=setInterval(()=>{if(entry.started&&!entry.closed&&!entry.ended)enqueue('Progress');},10000);
}catch(error){await showPlaybackError(entry,error);}}
async function closePlayer(entry){if(entry.closed)return;entry.closed=true;state.closingPlayers++;entry.finalMilliseconds=Number(entry.player?.currentTime||0);clearInterval(entry.timer);entry.options?.remove();entry.card.remove();state.players.delete(entry.id);updateLayout();entry.reportQueue=entry.reportQueue.then(()=>report(entry,'Stopped'));try{if(entry.player){await entry.player.stop();await new Promise(resolve=>setTimeout(resolve,50));await entry.player.destroy();}}catch(error){console.warn('关闭播放器失败',error);}finally{setTimeout(()=>state.closingPlayers--,1000);}}
async function closeAll(){for(const entry of [...state.players.values()])await closePlayer(entry);}$('closeAll').onclick=closeAll;
window.addEventListener('pagehide',()=>{for(const e of state.players.values()){if(e.key)fetch('/api/report',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({key:e.key,event:'Stopped',milliseconds:Number(e.player?.currentTime||0),paused:e.paused}),keepalive:true}).catch(()=>{});}});

// IPC shutdown cancels pending decoder requests. Handle only this exact cancellation during teardown.
window.addEventListener('unhandledrejection',event=>{if(state.closingPlayers>0&&String(event.reason)==='ipc port close'){event.preventDefault();console.debug('播放器关闭：已取消待处理的解码请求');}});

async function showPlaybackError(entry,error){
 entry.status.classList.add('playerError');
 const text=typeof error==='string'?error:error?.message||JSON.stringify(error,(_,v)=>typeof v==='bigint'?String(v):v);
 entry.status.textContent='播放失败：'+text;
 if(!entry.key)return;
 try{
  await getEmbySubtitles(entry).catch(error=>entry.subtitleError=error.message);const d=await api('diagnostic?key='+encodeURIComponent(entry.key));
  entry.status.textContent='播放失败：'+text+'\n读取诊断：'+JSON.stringify(d);
  if(!entry.diagnosticButton){
   const button=document.createElement('button');button.textContent='复制播放诊断';
   button.onclick=async()=>{try{await navigator.clipboard.writeText(entry.status.textContent);notice('播放诊断已复制');}catch(_){notice('请选中播放器下方的诊断文字复制');}};
   entry.card.append(button);entry.diagnosticButton=button;
  }
 }catch(e){entry.status.textContent+='\n诊断读取失败：'+e.message;}
}

(async()=>{
 const id=new URLSearchParams(location.search).get('play');
 if(!id)return;
 document.body.classList.add('playbackPage');
 $('loginPanel').hidden=true;
 try{
  const session=await api('session');BrowserCatalog.setSession(session,api);$('accountName').textContent=session.name;
  $('libraryPanel').hidden=false;
  document.querySelector('.toolbar').hidden=true;
  document.querySelector('nav').hidden=true;
  $('grid').hidden=true;document.querySelector('.pagination').hidden=true;
  document.querySelector('.playHeading small').textContent='独立播放标签页';
  const item=await api('item?id='+encodeURIComponent(id));document.title=item.Name+' · Direct Web';$('playTitle').textContent=item.Name;
  await startPlayer(item);
 }catch(error){$('loginPanel').hidden=false;notice(error.message);}
})();

async function loadCategories(){
 try{const data=await api('views');const list=$('categoryList');list.replaceChildren();preloadCatalog();queueCatalogViews(data.Items||[]);
  for(const view of data.Items||[]){if(!view.IsFolder)continue;
   const button=document.createElement('button');button.textContent=view.Name;button.onclick=()=>{
    if(state.loading)return;if(document.body.classList.contains('detailPageMode')){location.href='/?library=1&parent='+encodeURIComponent(view.Id)+'&categoryName='+encodeURIComponent(view.Name);return;}Object.assign(state,{parent:view.Id,stack:[{parent:null,name:view.Name}],search:'',resume:false,start:0,genres:[],year:'',person:'',personName:'',tab:'films'});
    for(const b of list.children)b.classList.toggle('selected',b===button);loadItems();};button.classList.toggle('selected',state.parent===view.Id);list.append(button);
  }
 }catch(_){}
}
$('menuToggle').onclick=()=>document.body.classList.toggle(innerWidth>900?'sidebarCollapsed':'sidebarOpen');
$('infoClose').onclick=()=>$('infoDialog').close();
$('copyInfo').onclick=async()=>{await navigator.clipboard.writeText($('infoText').textContent);$('copyInfo').textContent='已复制';};

function renderDetails(item,loading=false,error=''){
 const body=$('detailBody');body.replaceChildren();
 const image=document.createElement('div');image.className='detailPoster';image.textContent='▶';if(item.ImageTags?.Primary){const cover=document.createElement('img');cover.src='/api/image/'+encodeURIComponent(item.Id);cover.alt=item.Name||'';cover.onerror=()=>cover.remove();image.append(cover);}
 const content=document.createElement('div');const title=document.createElement('h2');title.textContent=item.Name||'影片详情';
 const meta=document.createElement('p');meta.textContent=[item.ProductionYear,item.OfficialRating,item.RunTimeTicks?Math.round(item.RunTimeTicks/600000000)+' 分钟':null,item.CommunityRating?'评分 '+item.CommunityRating:null].filter(Boolean).join(' · ');
 const overview=document.createElement('p');overview.className='detailOverview';overview.textContent=loading?'正在读取 Emby 影片介绍…':item.Overview||error||'Emby 未返回影片简介';
 const genres=document.createElement('p');genres.textContent=(item.Genres||[]).join(' / ');
 const people=document.createElement('p');people.textContent=(item.People||[]).slice(0,12).map(p=>p.Name+(p.Role?'（'+p.Role+'）':'')).join('、');
 const play=document.createElement('button');play.className='detailPlay';play.textContent='▶ 播放';play.onclick=()=>window.open('/?play='+encodeURIComponent(item.Id),'_blank','noopener');
 content.append(title,meta,genres,play,overview,people);body.append(image,content);
}
async function showDetails(item){
 renderDetails(item,true);$('detailDialog').showModal();
 try{const full=await api('item?id='+encodeURIComponent(item.Id));renderDetails({...item,...full});}
 catch(error){renderDetails(item,false,'介绍读取失败：'+error.message);}
}
$('detailClose').onclick=()=>$('detailDialog').close();
(async()=>{if(!new URLSearchParams(location.search).has('library'))return;
 try{const session=await api('session');BrowserCatalog.setSession(session,api);$('accountName').textContent=session.name;$('loginPanel').hidden=true;$('libraryPanel').hidden=false;$('logout').hidden=false;await loadCategories();await loadItems();if(state.scroll)requestAnimationFrame(()=>scrollTo(0,state.scroll));}catch(_){}
})();

$('settingsClose').onclick=()=>$('settingsDialog').close();
function textElement(tag,text,cls=''){const el=document.createElement(tag);el.textContent=text??'';if(cls)el.className=cls;return el;}
function safeMetadata(value){return JSON.parse(JSON.stringify(value,(key,v)=> /token|password|secret|apikey|authorization|transcodingurl|directstreamurl|path/i.test(key)?undefined:v));}
function mediaDescription(stream){return [stream.DisplayTitle,stream.Codec,stream.Width&&stream.Height?stream.Width+'×'+stream.Height:null,stream.Language,stream.ChannelLayout||stream.Channels&&stream.Channels+' 声道',stream.BitRate?Math.round(stream.BitRate/1000)+' kbps':null].filter(Boolean).join(' · ');}
function renderDetailPage(item){
 const root=$('detailPage');root.replaceChildren();
 if(item.BackdropImageTags?.length){root.style.setProperty('--backdrop',`url('/api/image/${encodeURIComponent(item.Id)}?type=Backdrop')`);}
 const back=textElement('a','‹','detailBack');back.href=detailReturnUrl();back.title='返回媒体库';back.setAttribute('aria-label','返回媒体库');document.querySelector('header .detailBack')?.remove();document.querySelector('header').append(back);
 const hero=document.createElement('div');hero.className='detailHero';const poster=document.createElement('div');poster.className='detailPagePoster';
 if(item.ImageTags?.Primary){const img=document.createElement('img');img.src='/api/image/'+encodeURIComponent(item.Id);img.alt=item.Name||'';poster.append(img);}
 const content=document.createElement('div');content.className='detailMain';content.append(textElement('h1',item.Name));
 const minutes=Math.round((item.RunTimeTicks||0)/600000000);const length=minutes?(minutes>=60?Math.floor(minutes/60)+'小时':'')+(minutes%60?minutes%60+'分钟':''):'';
 const facts=document.createElement('div');facts.className='detailFacts';for(const value of [item.ProductionYear,length])if(value)facts.append(textElement('span',value));if(item.OfficialRating)facts.append(textElement('span',item.OfficialRating,'ratingBadge'));if(item.Genres?.[0])facts.append(textElement('span',item.Genres[0]));if(item.CommunityRating)facts.append(textElement('span','★ '+item.CommunityRating));if(item.CriticRating)facts.append(textElement('span','影评 '+item.CriticRating+'%'));content.append(facts);
 const sources=item.MediaSources||[];const streams=item.MediaStreams||sources[0]?.MediaStreams||[];
 const specs=document.createElement('div');specs.className='detailSpecs';for(const type of ['Video','Audio','Subtitle']){const found=streams.filter(x=>x.Type===type);if(found.length)specs.append(textElement('p',(type==='Video'?'视频':type==='Audio'?'音频':'字幕')+'　'+found.map(mediaDescription).join(' / ')));}content.append(specs);
 const actions=document.createElement('div');actions.className='detailActions';const play=textElement('button','▶ 播放','detailPlay');play.onclick=()=>openPlayback(item);actions.append(play);
 if(item.UserData?.PlaybackPositionTicks){const fromStart=textElement('button','从头播放');fromStart.onclick=()=>window.open('/?play='+encodeURIComponent(item.Id)+'&start=0','_blank','noopener');actions.append(fromStart);}content.append(actions);
 if(item.PremiereDate)content.append(textElement('h3','发行日期 '+item.PremiereDate.slice(0,10)));
 if(item.Taglines?.length)content.append(textElement('p',item.Taglines.join(' · '),'detailTagline'));
 content.append(textElement('p',item.Overview||'Emby 未返回影片简介','detailOverview'));
 const directors=(item.People||[]).filter(x=>x.Type==='Director');if(directors.length)content.append(textElement('p','导演：'+directors.map(x=>x.Name).join('、')));
 const genreNames=item.Genres?.length?item.Genres:(item.GenreItems||[]).map(g=>g.Name);if(genreNames.length){const row=textElement('div','类型／分类：','detailGenreLinks');for(const genre of genreNames){const link=textElement('a',genre,'genreLink');link.href=catalogLink({genres:[genre],tab:'films'});row.append(link);}content.append(row);}
 if(item.Studios?.length)content.append(textElement('p','制作／发行：'+item.Studios.map(x=>x.Name||x).join('、')));
 hero.append(poster,content);root.append(hero);
 if(item.People?.length){root.append(textElement('h2','演职人员'));const list=document.createElement('div');list.className='personList';for(const person of item.People){const card=document.createElement('a');card.className='personCard';card.href=catalogLink({person:person.Id||'',personName:person.Name,genres:[],tab:'films'});card.title='查看'+person.Name+'的作品';const image=document.createElement('div');image.className='personImage';image.innerHTML='<svg viewBox="0 0 64 64" aria-hidden="true"><circle cx="32" cy="20" r="9"/><path d="M14 52v-5c0-10 8-16 18-16s18 6 18 16v5z"/></svg>';if(person.Id&&person.PrimaryImageTag){const img=document.createElement('img');img.src='/api/image/'+encodeURIComponent(person.Id);img.alt=person.Name;img.loading='lazy';img.onerror=()=>img.remove();image.append(img);}card.append(image,textElement('strong',person.Name),textElement('small',person.Role||person.Type));list.append(card);}root.append(list);}
 if(sources.length){root.append(textElement('h2','媒体信息'));for(const source of sources){const panel=document.createElement('section');panel.className='mediaInfo';panel.append(textElement('h3',source.Name||source.Container||'媒体源'));panel.append(textElement('p',[source.Container,source.Size?(source.Size/1073741824).toFixed(2)+' GB':null,source.Bitrate?Math.round(source.Bitrate/1000)+' kbps':null].filter(Boolean).join(' · ')));for(const stream of source.MediaStreams||[])panel.append(textElement('p',(stream.Type||'')+'　'+mediaDescription(stream)));root.append(panel);}}
 const all=document.createElement('details');all.className='allMetadata';all.append(textElement('summary','查看全部已获取元数据'));const pre=textElement('pre',JSON.stringify(safeMetadata(item),null,2));all.append(pre);root.append(all);
}
(async()=>{const id=new URLSearchParams(location.search).get('detail');if(!id)return;
 $('loginPanel').hidden=true;$('libraryPanel').hidden=false;document.body.classList.add('detailPageMode');$('detailPage').hidden=false;$('detailPage').textContent='正在读取影片信息…';
 try{const session=await api('session');BrowserCatalog.setSession(session,api);$('accountName').textContent=session.name;await loadCategories();const item=await api('item?id='+encodeURIComponent(id));renderDetailPage(item);document.title=item.Name+' · 影片详情';}catch(error){$('detailPage').textContent='影片信息读取失败：'+error.message;}
})();

// Catalog navigation lives in the URL, so details and browser Back retain filters.
function catalogQuery(){const q=new URLSearchParams({start:state.start,sort:state.sort,match:state.match,videos:'1'});if(state.parent)q.set('parent',state.parent);if(state.stack.at(-1)?.name)q.set('categoryName',state.stack.at(-1).name);if(state.search)q.set('search',state.search);if(state.resume)q.set('resume','1');for(const g of state.genres)q.append('genres',g);if(state.year)q.set('year',state.year);if(state.person)q.set('person',state.person);if(state.personName)q.set('personName',state.personName);q.set('tab',state.tab);return q;}
function restoreCatalogState(){const q=new URLSearchParams(location.search);if(!q.has('library'))return;state.parent=q.get('parent');state.stack=state.parent?[{parent:null,name:q.get('categoryName')||'媒体库'}]:[];state.search=q.get('search')||'';state.resume=q.has('resume');state.start=Math.max(0,Number(q.get('start'))||0);state.genres=q.getAll('genres');state.year=q.get('year')||'';state.person=q.get('person')||'';state.personName=q.get('personName')||'';state.sort=q.get('sort')||'name';state.tab=q.get('tab')==='history'?'history':'films';state.match=q.get('match')||state.match;try{const saved=JSON.parse(sessionStorage.getItem('directweb.catalog')||'null');if(saved?.url===location.pathname+location.search)state.scroll=saved.scroll||0;}catch(_){} }
function saveCatalogState(){if(document.body.classList.contains('playbackPage')||document.body.classList.contains('detailPageMode'))return;const q=catalogQuery();q.set('library','1');if(new URLSearchParams(location.search).has('inline'))q.set('inline','1');history.replaceState({},'', '/?'+q);sessionStorage.setItem('directweb.catalog',JSON.stringify({url:location.pathname+location.search,scroll:state.scroll}));}
function detailReturnUrl(){const url=new URLSearchParams(location.search).get('return');return url?.startsWith('/?')&&new URLSearchParams(url.slice(2)).has('library')?url:'/?library=1';}
function catalogLink(changes){const q=new URLSearchParams(detailReturnUrl().slice(2));q.set('library','1');q.set('start','0');q.delete('search');q.delete('resume');for(const [key,value] of Object.entries(changes)){q.delete(key);if(Array.isArray(value)){for(const x of value)q.append(key,x);}else if(value)q.set(key,value);}return '/?'+q;}
let genreExpanded=false;
let filterScope=null,filterError='',filterData={Genres:[],Years:[]};
async function loadFilterOptions(){const scope=state.parent||'';const data=await BrowserCatalog.filters(scope);if(data){filterData=data;filterScope=scope;filterError='';}else{filterData={Genres:[],Years:[]};filterScope=null;filterError='';preloadCatalog();}}

function filterButton(label,selected,click){const button=textElement('button',label,selected?'selected':'');button.type='button';button.setAttribute('aria-pressed',String(selected));button.onclick=()=>{if(state.loading)return;state.start=0;state.scroll=0;click();loadItems();};return button;}
function renderCatalogFilters(){const genres=[...new Set([...(filterData.Genres||[]).map(g=>typeof g==='string'?g:g.Name),...state.genres])].filter(Boolean);const genreRoot=$('genreFilters');genreRoot.replaceChildren(filterButton('全部',!state.genres.length,()=>state.genres=[]));for(const [index,g] of genres.entries()){const button=filterButton(g,state.genres.includes(g),()=>{state.genres=state.genres.includes(g)?state.genres.filter(x=>x!==g):[...state.genres,g];});button.hidden=!genreExpanded&&index>=10&&!state.genres.includes(g);genreRoot.append(button);}genreRoot.classList.toggle('expanded',genreExpanded);$('genreExpand').hidden=genres.length<=10;$('genreExpand').textContent=genreExpanded?'−':'＋';$('genreExpand').setAttribute('aria-expanded',String(genreExpanded));$('genreExpand').setAttribute('aria-label',genreExpanded?'收起类型选项':'展开类型选项');$('genreExpand').title=genreExpanded?'收起类型选项':'展开类型选项';if(!genres.length)genreRoot.append(textElement('small',filterError?'类型预加载失败：'+filterError:filterScope===null?'类型预加载中…':'此媒体库没有类型元数据'));
 const years=[...new Set([...(filterData.Years||[]).map(String),state.year])].filter(Boolean).sort((a,b)=>Number(b)-Number(a));const select=$('yearSelect');select.replaceChildren(textElement('option','全部年份'));select.options[0].value='';for(const year of years){const option=textElement('option',year+' 年');option.value=year;select.append(option);}select.value=state.year;select.title=years.length?'按影片年份筛选':filterScope===null?'年份预加载中':'Emby 未提供年份信息';$('yearFilters').replaceChildren(filterButton('全部',!state.year,()=>state.year=''));for(const year of years)$('yearFilters').append(filterButton(year,state.year===year,()=>state.year=year));
 $('sortFilters').replaceChildren();for(const [id,name] of [['name','名称'],['newest','最新上映'],['added','最近添加'],['year','年份'],['rating','评分最高']])$('sortFilters').append(filterButton(name,state.sort===id,()=>state.sort=id));
 $('activeFilters').replaceChildren();if(state.personName){const actor=filterButton('演员：'+state.personName+' ×',true,()=>{state.person='';state.personName='';});$('activeFilters').append(actor);}if(state.genres.length>1)$('activeFilters').append(textElement('small',state.match==='and'?'全部符合（AND）':'任一符合（OR）'));
 $('catalogFilters').hidden=state.tab==='history';$('grid').hidden=false;document.querySelector('.pagination').hidden=false;$('home').classList.toggle('active',state.tab==='films'&&!state.resume);$('historyTab').classList.toggle('active',state.tab==='history');$('genreMatch').value=state.match;
}
$('historyTab').onclick=()=>{if(state.loading)return;Object.assign(state,{tab:'history',resume:false,genres:[],year:'',person:'',personName:'',search:'',start:0});loadItems();};
$('clearFilters').onclick=()=>{if(state.loading)return;Object.assign(state,{genres:[],year:'',person:'',personName:'',search:'',resume:false,start:0});$('search').value='';loadItems();};
$('filterSettings').onclick=()=>$('filterDialog').showModal();$('filterSettingsClose').onclick=()=>$('filterDialog').close();$('genreMatch').onchange=()=>{state.match=$('genreMatch').value;localStorage.setItem('directweb.genreMatch',state.match);state.start=0;loadItems();};

async function getEmbySubtitles(entry){if(!entry.subtitleRequest)entry.subtitleRequest=api('subtitles?key='+encodeURIComponent(entry.key)).then(data=>entry.embySubtitles=data.Items||[]).catch(error=>{entry.subtitleRequest=null;throw error;});return entry.subtitleRequest;}
async function chooseEmbySubtitle(entry,track,automatic=false){entry.externalIds??=new Map();let id=entry.externalIds.get(track.index);if(id===undefined){const response=await fetch('/api/subtitles?'+new URLSearchParams({key:entry.key,index:track.index}),{credentials:'same-origin'});if(!response.ok){const error=await response.json();throw Error(error.error||'字幕下载失败');}const bytes=new Uint8Array(await response.arrayBuffer());let text;try{const encoding=bytes[0]===255&&bytes[1]===254?'utf-16le':bytes[0]===254&&bytes[1]===255?'utf-16be':'utf-8';text=new TextDecoder(encoding,{fatal:true}).decode(bytes);}catch(_){text=new TextDecoder('gb18030').decode(bytes);}const file=new File([text.replace(/^\uFEFF/,'').replace(/\r\n?/g,'\n').trimEnd()+'\n\n'],`subtitle-${track.index}.${track.format}`);const before=new Set(entry.player.getStreams().map(s=>s.id));await entry.player.loadExternalSubtitle({source:file,title:track.title});const stream=entry.player.getStreams().find(s=>s.mediaType==='Subtitle'&&!before.has(s.id));if(!stream)throw Error('字幕文件未生成可用字幕流');id=stream.id;entry.externalIds.set(track.index,id);}if(entry.closed||(automatic&&entry.subtitleSelection!==undefined))return;if(entry.player.getSelectedSubtitleStreamId()!==id)await entry.player.selectSubtitle(id);entry.player.setSubtitleEnable(true);entry.subtitleSelection='external:'+track.index;}
async function primeEmbySubtitles(entry){const choices=await getEmbySubtitles(entry);if(entry.closed)return;const selected=PlayerControls.preferredSubtitle(choices);if(entry.subtitleSelection!==undefined)return;if(selected)await chooseEmbySubtitle(entry,selected,true);else{const stream=entry.player.getStreams().find(s=>s.mediaType==='Subtitle');if(stream){if(entry.player.getSelectedSubtitleStreamId()!==stream.id)await entry.player.selectSubtitle(stream.id);entry.player.setSubtitleEnable(true);entry.subtitleSelection='stream:'+stream.id;}}}
async function openSubtitleSettings(entry,localLabel){const body=$('settingsBody');const section=document.createElement('section');section.className='subtitleSettings';section.append(textElement('h3','字幕'));const message=textElement('p','正在读取 Emby 外挂字幕…','subtitleMessage');section.append(message);body.replaceChildren(section,localLabel);$('settingsDialog').showModal();let choices=[];try{choices=await getEmbySubtitles(entry);}catch(error){message.textContent='Emby 外挂字幕读取失败：'+error.message;}
 if(entry.closed)return;
 const select=document.createElement('select');select.setAttribute('aria-label','选择字幕');select.id='subtitleSelect';select.append(textElement('option','关闭字幕'));select.options[0].value='none';const externalIds=new Set(entry.externalIds?.values()||[]);for(const stream of entry.player.getStreams().filter(x=>x.mediaType==='Subtitle'&&!externalIds.has(x.id))){const option=textElement('option','内嵌／本地 · '+(stream.metadata?.title||stream.metadata?.language||'字幕 '+stream.index));option.value='stream:'+stream.id;select.append(option);}for(const track of choices){const option=textElement('option','Emby 外挂 · '+track.title+(track.supported?'':'（图片字幕暂不支持）'));option.value='external:'+track.index;option.disabled=!track.supported;select.append(option);}select.value=entry.subtitleSelection||'none';section.insertBefore(select,message);if(!message.textContent.includes('失败'))message.textContent=choices.length?'选择外挂字幕后才下载字幕文件，可随时切换或关闭。':'Emby 未返回外挂字幕；仍可选择已检测的内嵌／本地字幕。';
 select.onchange=async()=>{const value=select.value;select.disabled=true;message.textContent='正在切换字幕…';try{if(value==='none'){entry.player.setSubtitleEnable(false);entry.subtitleSelection=value;}else if(value.startsWith('stream:')){if(entry.player.getSelectedSubtitleStreamId()!==Number(value.slice(7)))await entry.player.selectSubtitle(Number(value.slice(7)));entry.player.setSubtitleEnable(true);entry.subtitleSelection=value;}else await chooseEmbySubtitle(entry,choices.find(x=>'external:'+x.index===value));message.textContent=value==='none'?'字幕已关闭':'字幕已切换';}catch(error){message.textContent='字幕加载失败：'+error.message;}finally{select.disabled=false;}};
}

$('genreExpand').onclick=()=>{genreExpanded=!genreExpanded;renderCatalogFilters();};

function preloadCatalog(){if(!BrowserCatalog.scope)return;BrowserCatalog.warm(state.parent||'').catch(error=>{filterError=error.message;});}
let preloadQueue=Promise.resolve();
function queueCatalogViews(views){const owner=BrowserCatalog.scope;for(const view of views){if(!view.IsFolder)continue;preloadQueue=preloadQueue.then(()=>owner===BrowserCatalog.scope?BrowserCatalog.warm(view.Id):undefined).catch(()=>{});}}
window.addEventListener('catalogwarm',async event=>{const detail=event.detail;if(detail.parent!==(state.parent||''))return;$('preloadStatus').textContent=detail.status==='loading'?'后台预加载媒体信息…':detail.status==='error'?'预加载失败：'+detail.message:'';if(detail.status==='ready'){await loadFilterOptions();renderCatalogFilters();}});
window.addEventListener('browsercachewarning',event=>$('preloadStatus').textContent=event.detail);
$('clearBrowserData').onclick=async()=>{await BrowserCatalog.clear();$('clearBrowserDataStatus').textContent='此账号的浏览器缓存与历史已清除。';filterScope=null;filterData={Genres:[],Years:[]};renderCatalogFilters();if(state.tab==='history'){$('grid').replaceChildren();state.total=0;$('page').textContent='1 / 1';}};

function installSeekButtons(entry,viewport,duration){
 const play=viewport.querySelector('.avplayer-ui-control-play');if(!play)return;
 const controls=document.createElement('div');controls.className='directSeekControls';
 for(const [delta,label,icon] of [[-5,'后退 5 秒','↶'],[5,'前进 5 秒','↷']]){const button=document.createElement('button');button.type='button';button.className='directSeekButton';button.setAttribute('aria-label',label);button.title=label;button.innerHTML='<span aria-hidden="true">'+icon+'</span><small>5</small>';button.onclick=()=>{entry.shortSeekQueue=(entry.shortSeekQueue||Promise.resolve()).then(async()=>{if(entry.closed)return;const from=Number(entry.player.currentTime);const target=PlayerControls.seekTarget(from,delta,duration||Number(entry.player.getDuration()));entry.lastShortSeek={from,target,delta};await entry.player.seek(BigInt(target));}).catch(error=>{entry.status.textContent='跳转失败：'+error.message;});};controls.append(button);}
 play.after(controls);
}

$('yearSelect').onchange=()=>{if(state.loading){$('yearSelect').value=state.year;return;}state.year=$('yearSelect').value;state.start=0;state.scroll=0;loadItems();};
