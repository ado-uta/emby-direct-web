/* Browser-only metadata and history. Never stores passwords, tokens or video URLs. */
(function(root){
'use strict';
function safeRecord(value){return JSON.parse(JSON.stringify(value,(key,v)=>/token|password|secret|authorization|url|path/i.test(key)?undefined:v));}
function filterItems(items,q){
 const genres=q.getAll('genres').map(x=>x.trim().toLowerCase()),mode=q.get('match')||'or',year=q.get('year'),person=q.get('person'),personName=q.get('personName'),search=(q.get('search')||'').toLowerCase();
 let found=items.filter(item=>{const gs=(item.Genres||[]).map(x=>x.trim().toLowerCase());if(genres.length&&!(mode==='and'?genres.every(g=>gs.includes(g)):genres.some(g=>gs.includes(g))))return false;if(year&&String(item.ProductionYear)!==year)return false;if(person&&!(item.People||[]).some(p=>String(p.Id)===person))return false;if(!person&&personName&&!(item.People||[]).some(p=>p.Name===personName))return false;if(search&&!String(item.Name||'').toLowerCase().includes(search))return false;return true;});
 const sort=q.get('sort')||'name',collator=new Intl.Collator('zh-CN',{numeric:true,sensitivity:'base'}),name=(a,b)=>collator.compare(a.SortName||a.Name||'',b.SortName||b.Name||'');
 if(sort!=='history')found.sort((a,b)=>sort==='rating'?(Number(b.CommunityRating)||0)-(Number(a.CommunityRating)||0)||name(a,b):sort==='year'?(Number(b.ProductionYear)||0)-(Number(a.ProductionYear)||0)||name(a,b):sort==='newest'||sort==='added'?String(b[sort==='added'?'DateCreated':'PremiereDate']||'').localeCompare(String(a[sort==='added'?'DateCreated':'PremiereDate']||''))||name(a,b):name(a,b));
 const start=Math.max(0,Number(q.get('start'))||0);return {Items:found.slice(start,start+60),TotalRecordCount:found.length,QueryStrategy:'browser-index'};
}
if(typeof module==='object'&&module.exports){module.exports={filterItems,safeRecord};return;}
const mem=new Map(),pending=new Map();let scope='',request=null,dbPromise=null;const revisions=new Map();
function db(){if(!dbPromise)dbPromise=new Promise((resolve,reject)=>{const r=indexedDB.open('DirectWebBrowser',1);r.onupgradeneeded=()=>{for(const name of ['indexes','history'])if(!r.result.objectStoreNames.contains(name))r.result.createObjectStore(name,{keyPath:'key'});};r.onsuccess=()=>resolve(r.result);r.onerror=()=>reject(r.error);});return dbPromise;}
async function read(store,key){try{const database=await db();return await new Promise((resolve,reject)=>{const r=database.transaction(store).objectStore(store).get(key);r.onsuccess=()=>resolve(r.result);r.onerror=()=>reject(r.error);});}catch(_){return mem.get(store+':'+key);}}
async function write(store,value){mem.set(store+':'+value.key,value);try{const database=await db();await new Promise((resolve,reject)=>{const tx=database.transaction(store,'readwrite');tx.objectStore(store).put(value);tx.oncomplete=resolve;tx.onerror=()=>reject(tx.error);});}catch(_){root.dispatchEvent(new CustomEvent('browsercachewarning',{detail:'浏览器存储不可用，当前仅在此网页内存中缓存。'}));}}
async function all(store){try{const database=await db();return await new Promise((resolve,reject)=>{const r=database.transaction(store).objectStore(store).getAll();r.onsuccess=()=>resolve(r.result);r.onerror=()=>reject(r.error);});}catch(_){return [...mem.entries()].filter(([k])=>k.startsWith(store+':')).map(([,v])=>v);}}
function key(parent){return scope+':'+(parent||'root');}
async function warm(parent='',force=false){const active=scope,revision=revisions.get(scope)||0,k=key(parent);if(pending.has(k))return pending.get(k);const saved=await read('indexes',k);if(saved&&!force&&Date.now()-saved.updatedAt<600000)return saved;
 if(pending.has(k))return pending.get(k);
 const job=(async()=>{let start=0,complete=false;const items=[];root.dispatchEvent(new CustomEvent('catalogwarm',{detail:{parent,status:'loading'}}));while(start<50000){const q=new URLSearchParams({start});if(parent)q.set('parent',parent);const data=await request('catalog-page?'+q);if(scope!==active||(revisions.get(active)||0)!==revision)throw Error('登录账号已切换');const batch=data.Items||[];items.push(...batch.map(safeRecord));start+=batch.length;if(!batch||start>=data.TotalRecordCount){complete=true;break;}}if(!complete)throw Error('媒体库超过五万部，请缩小范围');const value={key:k,scope:active,parent,updatedAt:Date.now(),items};await write('indexes',value);root.dispatchEvent(new CustomEvent('catalogwarm',{detail:{parent,status:'ready'}}));return value;})().catch(error=>{root.dispatchEvent(new CustomEvent('catalogwarm',{detail:{parent,status:'error',message:error.message}}));throw error;}).finally(()=>pending.delete(k));pending.set(k,job);return job;
}
async function index(parent=''){const saved=await read('indexes',key(parent));if(saved){if(Date.now()-saved.updatedAt>=600000)warm(parent,true).catch(()=>{});return saved;}return warm(parent);}
async function history(){return (await all('history')).filter(x=>x.scope===scope).sort((a,b)=>b.watchedAt-a.watchedAt).map(x=>x.item);}
root.BrowserCatalog={
 setSession(session,api){scope=session.storageScope||'';request=api;if(!scope)throw Error('登录未返回浏览器存储标识');},
 get scope(){return scope;},warm,
 async ready(parent=''){return read('indexes',key(parent));},
 async items(q){if(q.get('tab')==='history')return filterItems(await history(),new URLSearchParams({...Object.fromEntries(q),sort:'history'}));const parent=q.get('parent')||'',saved=await read('indexes',key(parent));const mustIndex=q.getAll('genres').length||q.get('year')||q.get('person')||q.get('personName')||q.get('search');if(saved||mustIndex){const data=saved||await index(parent);if(saved&&Date.now()-saved.updatedAt>=600000)warm(parent,true).catch(()=>{});return filterItems(data.items,q);}return request('items?'+q);},
 async filters(parent=''){const saved=await read('indexes',key(parent));if(!saved)return null;return {Genres:[...new Set(saved.items.flatMap(x=>x.Genres||[]))].sort(),Years:[...new Set(saved.items.map(x=>x.ProductionYear).filter(Boolean))].sort((a,b)=>b-a)};},
 async record(item,milliseconds,active=scope){if(!active)return;const copy=safeRecord(item);copy.UserData={...(copy.UserData||{}),PlaybackPositionTicks:Math.max(0,Math.round(milliseconds*10000))};await write('history',{key:active+':'+item.Id,scope:active,watchedAt:Date.now(),item:copy});},
 async clear(){const active=scope;revisions.set(active,(revisions.get(active)||0)+1);for(const store of ['indexes','history']){const values=(await all(store)).filter(x=>x.scope===active);for(const value of values){mem.delete(store+':'+value.key);try{const database=await db();await new Promise((resolve,reject)=>{const tx=database.transaction(store,'readwrite');tx.objectStore(store).delete(value.key);tx.oncomplete=resolve;tx.onerror=()=>reject(tx.error);});}catch(_){}}}}
};
})(typeof window==='object'?window:globalThis);
