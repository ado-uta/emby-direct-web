"""Local-only Emby API and raw-file bridge. Never runs a transcoder."""
import argparse
import hashlib
import ipaddress
import json
import mimetypes
import os
import re
import secrets
import socket
import sys
import threading
import time
import webbrowser
from http.cookies import SimpleCookie
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlsplit, urljoin, parse_qs, urlencode, quote
import requests
from catalog import query_items, filter_options
from subtitles import subtitle_options, merge_subtitle_streams
from core import validate_base, direct_location, validate_range, playback_request, origin

ROOT=Path(getattr(sys,'_MEIPASS',Path(__file__).resolve().parent))
REDIRECTS=(301,302,303,307,308)
DEVICE_ID=secrets.token_hex(12)

def http():
    s=requests.Session();s.trust_env=False;return s

def identifier(value):
    value=str(value)
    if not re.fullmatch(r'[A-Za-z0-9_-]{1,128}',value): raise ValueError('媒体 ID 无效')
    return value

def detect_container(head,hint=''):
    if head.startswith(b'\x1a\x45\xdf\xa3'):return 'mkv'
    if len(head)>8 and head[4:8] in (b'ftyp',b'moov',b'mdat',b'free',b'wide'):return 'mp4'
    if head.startswith(b'RIFF') and head[8:12]==b'AVI ':return 'avi'
    if head.startswith(b'FLV'):return 'flv'
    if len(head)>188 and head[0]==71 and head[188]==71:return 'mpegts'
    if head.lstrip().lower().startswith((b'<html',b'<!doctype',b'{"',b'#extm3u')):
        raise ValueError('115 返回页面或播放清单，未取得原始视频文件')
    return hint.lower() if hint.lower() in ('mkv','mp4','mov','avi','flv','webm','mpegts') else ''

class Emby:
    def __init__(self,base,ua):
        self.base=validate_base(base);self.ua=ua;self.token=None;self.user=None
    def headers(self):
        h={'User-Agent':self.ua,'X-Emby-Authorization':f'Emby Client="DirectWeb", Device="Windows Browser", DeviceId="{DEVICE_ID}", Version="0.8.0"'}
        if self.token: h['X-Emby-Token']=self.token
        return h
    def api(self,path,method='GET',params=None,data=None):
        with http() as s, s.request(method,self.base+path,params=params,json=data,headers=self.headers(),allow_redirects=False,timeout=(3,5) if path.startswith('/Sessions/') else (10,30)) as r:
            if r.status_code in REDIRECTS: raise ValueError('Emby API 返回跳转，请填写可直接访问的正确地址及端口')
            if r.status_code in (401,403): raise ValueError('Emby 登录或权限失败，请检查账号及地址')
            if not r.ok: raise ValueError(f'Emby 接口返回 HTTP {r.status_code}')
            if not r.content:return {}
            try:return r.json()
            except ValueError:raise ValueError('该地址未返回 Emby API 数据，请检查端口或 /emby 路径')
    def login(self,name,password):
        data=self.api('/Users/AuthenticateByName','POST',data={'Username':name,'Pw':password})
        self.token=data['AccessToken'];self.user=data['User'];return {'name':self.user.get('Name',name),'storageScope':hashlib.sha256((self.base+'\0'+str(self.user['Id'])).encode()).hexdigest()}
    def resolve(self,item_id,source_id):
        params={'static':'true','MediaSourceId':source_id,'api_key':self.token}
        url=self.base+'/Videos/'+identifier(item_id)+'/stream?'+urlencode(params)
        with http() as s, s.get(url,headers={**self.headers(),'Range':'bytes=0-0','Accept-Encoding':'identity'},stream=True,allow_redirects=False,timeout=(10,30)) as r:
            if r.status_code not in REDIRECTS or not r.headers.get('Location'):
                raise ValueError(f'原文件入口未返回 302 直链（HTTP {r.status_code}），已阻止从 HK 读取视频。请确认现有 302 服务支持 /Videos/ID/stream?static=true')
            target=direct_location(self.base,r.headers['Location'])
            if self.token in parse_qs(urlsplit(target).query).get('api_key',[]):raise ValueError('直链包含 Emby 令牌，已拒绝向网盘发送')
            return target

class MediaConnectionPool(requests.adapters.HTTPAdapter):
    # Each request keeps separate headers/cookies while urllib3 pools reusable sockets.
    def close(self):pass

class AppServer(ThreadingHTTPServer):
    daemon_threads=True
    def __init__(self,address,allow_private_media=False):
        self.launch_key=secrets.token_urlsafe(32);self.cookie_key=secrets.token_urlsafe(32)
        self.emby=None;self.plays={};self.dns_cache={};self.media_pool=MediaConnectionPool(pool_connections=16,pool_maxsize=16);self.allow_private_media=allow_private_media;self.lock=threading.RLock()
        super().__init__(address,Handler)
    def server_close(self):
        super().server_close();requests.adapters.HTTPAdapter.close(self.media_pool)
    def media_target(self,url):
        target=direct_location(self.emby.base,url)
        if not self.allow_private_media:
            host=urlsplit(target).hostname
            cached=self.dns_cache.get(host)
            addresses=cached[1] if cached and time.monotonic()-cached[0]<60 else socket.getaddrinfo(host,urlsplit(target).port or 443,type=socket.SOCK_STREAM)
            self.dns_cache[host]=(time.monotonic(),addresses)
            for info in addresses:
                if not ipaddress.ip_address(info[4][0]).is_global:raise ValueError('直链指向本地或私有地址，已拒绝')
        return target
    def open_media(self,play,range_value):
        session=http();session.mount('https://',self.media_pool);session.mount('http://',self.media_pool)
        try:
            for attempt in range(2):
                with play['resolve_lock']:
                    if not play.get('target'): play['target']=self.emby.resolve(play['item'],play['source'])
                    target=play['target']
                for _ in range(6):
                    target=self.media_target(target)
                    headers={'User-Agent':self.emby.ua,'Accept-Encoding':'identity'}
                    if range_value:headers['Range']=range_value
                    r=session.get(target,headers=headers,stream=True,allow_redirects=False,timeout=(10,40))
                    if r.status_code in REDIRECTS:
                        location=r.headers.get('Location');r.close()
                        if not location:raise ValueError('网盘跳转缺少 Location')
                        target=urljoin(target,location);continue
                    break
                else:raise ValueError('网盘重定向次数过多')
                if r.status_code in (401,403,410) and attempt==0:
                    r.close()
                    with self.lock:play['target']=None
                    continue
                if r.status_code not in (200,206):
                    status=r.status_code;r.close();raise ValueError(f'115 直链返回 HTTP {status}，检查 UA/IP 限制或链接时效')
                if range_value and (r.status_code!=206 or not r.headers.get('Content-Range')):
                    r.close();raise ValueError('网盘未正确响应 Range，不能保证原文件拖动播放')
                if r.headers.get('Content-Type','').lower().startswith(('text/','application/json')):
                    r.close();raise ValueError('直链返回错误页面而非视频数据')
                play['host']=urlsplit(target).hostname
                if not self.allow_private_media and not any(play['host']==d or play['host'].endswith('.'+d) for d in ('115.com','115cdn.com','115cdn.net')):
                    r.close();raise ValueError('最终地址不是已识别的 115 域名，已阻止读取视频：'+play['host'])
                play['target']=target
                return session,r
            raise ValueError('直链刷新失败')
        except Exception:session.close();raise

class Handler(BaseHTTPRequestHandler):
    protocol_version='HTTP/1.1'
    def handle(self):
        try:super().handle()
        except (ConnectionAbortedError,ConnectionResetError,BrokenPipeError):pass
    def log_message(self,*args):pass  # Never log tokens, cloud URLs or passwords.
    def end_headers(self):
        self.send_header('Cross-Origin-Opener-Policy','same-origin')
        self.send_header('Cross-Origin-Embedder-Policy','require-corp')
        self.send_header('Cross-Origin-Resource-Policy','same-origin')
        self.send_header('X-Content-Type-Options','nosniff')
        self.send_header('Referrer-Policy','no-referrer')
        self.send_header('Cache-Control','no-store' if not self.path.startswith(('/vendor/','/wasm/')) else 'public, max-age=86400')
        super().end_headers()
    def send(self,status,data,ctype='application/json',headers=None):
        if not isinstance(data,bytes):data=json.dumps(data,ensure_ascii=False).encode('utf-8')
        self.send_response(status);self.send_header('Content-Type',ctype);self.send_header('Content-Length',str(len(data)))
        for k,v in (headers or {}).items():self.send_header(k,v)
        self.end_headers()
        if self.command!='HEAD':self.wfile.write(data)
    def guard(self):
        expected=f'127.0.0.1:{self.server.server_port}'
        if self.headers.get('Host')!=expected:raise PermissionError('只允许通过本机地址访问')
        site=self.headers.get('Origin')
        if site and site!='http://'+expected:raise PermissionError('拒绝跨站请求')
        if self.headers.get('Sec-Fetch-Site')=='cross-site':raise PermissionError('拒绝跨站请求')
        cookie=SimpleCookie();cookie.load(self.headers.get('Cookie',''))
        if not cookie.get('directweb') or not secrets.compare_digest(cookie['directweb'].value,self.server.cookie_key):raise PermissionError('请通过启动程序自动打开的网页访问')
    def body(self):
        if not self.headers.get('Content-Type','').startswith('application/json'):raise ValueError('需要 JSON 请求')
        size=int(self.headers.get('Content-Length','0'))
        if size<0 or size>32768:raise ValueError('请求过大')
        data=json.loads(self.rfile.read(size) or b'{}')
        if not isinstance(data,dict):raise ValueError('请求数据无效')
        return data
    def need_emby(self):
        if not self.server.emby:raise LookupError('请先登录 Emby')
        return self.server.emby
    def do_GET(self):self.handle_request()
    def do_HEAD(self):self.handle_request()
    def do_POST(self):self.handle_request()
    def handle_request(self):
        try:self.route()
        except PermissionError as e:self.send(403,{'error':str(e)})
        except LookupError as e:self.send(401,{'error':str(e)})
        except (ValueError,KeyError) as e:self.send(400,{'error':str(e)})
        except requests.RequestException:self.send(502,{'error':'上游连接失败或超时，请检查地址、网络和 HTTPS 证书'})
        except (BrokenPipeError,ConnectionResetError,ConnectionAbortedError):pass
        except Exception:self.send(500,{'error':'本机服务处理失败，请重启程序后再试'})
    def route(self):
        parts=urlsplit(self.path);path=parts.path;q=parse_qs(parts.query)
        if path=='/' and q.get('launch'):
            if self.headers.get('Host')!=f'127.0.0.1:{self.server.server_port}' or not secrets.compare_digest(q['launch'][0],self.server.launch_key):raise PermissionError('启动链接无效')
            self.send(303,b'',headers={'Location':'/','Set-Cookie':f'directweb={self.server.cookie_key}; HttpOnly; SameSite=Strict; Path=/'})
            return
        self.guard()
        if path.startswith('/api/') or path.startswith('/media/'):
            if path=='/api/login' and self.command=='POST':
                data=self.body();ua=data.get('ua') or self.headers.get('User-Agent','DirectWeb/0.1')
                if '\r' in ua or '\n' in ua or len(ua)>1024:raise ValueError('UA 无效')
                emby=Emby(data['server'],ua);result=emby.login(data['username'],data['password'])
                with self.server.lock:self.server.emby=emby;self.server.plays.clear()
                self.send(200,result);return
            if path=='/api/logout' and self.command=='POST':
                self.body()
                with self.server.lock:self.server.emby=None;self.server.plays.clear()
                self.send(200,{});return
            emby=self.need_emby();user=identifier(emby.user['Id'])
            if path=='/api/session' and self.command=='GET':
                self.send(200,{'name':emby.user.get('Name',''),'storageScope':hashlib.sha256((emby.base+'\0'+str(user)).encode()).hexdigest()});return
            if path=='/api/views' and self.command=='GET':
                self.send(200,emby.api(f'/Users/{user}/Views'));return
            if path=='/api/item' and self.command=='GET':
                item=identifier(q.get('id',[''])[0]);fields='Overview,People,Genres,Studios,MediaSources,MediaStreams,UserData,Taglines,ProviderIds,Tags,Chapters,ProductionLocations,ExternalUrls'
                full=emby.api(f'/Users/{user}/Items/'+item,params={'Fields':fields})
                if not full.get('Overview'):
                    try:
                        extra=emby.api('/Items/'+item,params={'UserId':user,'Fields':fields})
                        full.update({k:v for k,v in extra.items() if v is not None and v!='' and v!=[]})
                    except (ValueError,requests.RequestException):pass
                self.send(200,full);return
            if path=='/api/catalog-page' and self.command=='GET':
                start=max(0,int(q.get('start',[0])[0]))
                if start>=50000:raise ValueError('媒体库超过五万部，请缩小范围')
                params={'StartIndex':start,'Limit':200,'Recursive':True,'MediaTypes':'Video','IncludeItemTypes':'Movie,Episode,Video','Fields':'Genres,People,UserData,SortName,DateCreated,MediaSources,ProductionYear,PremiereDate,CommunityRating','SortBy':'SortName','SortOrder':'Ascending'}
                if q.get('parent'):params['ParentId']=identifier(q['parent'][0])
                data=emby.api(f'/Users/{user}/Items',params=params)
                self.send(200,data);return
            if path=='/api/filters' and self.command=='GET':
                parent=identifier(q['parent'][0]) if q.get('parent') else ''
                self.send(200,filter_options(emby,user,parent));return
            if path=='/api/items' and self.command=='GET':
                result=query_items(emby,user,q);timing=result.get('CatalogTiming',{})
                header=f"emby;dur={timing.get('upstreamMs',0)}, local;dur={timing.get('localMs',0)}, catalog;dur={timing.get('totalMs',0)}"
                self.send(200,result,headers={'Server-Timing':header});return
            if path.startswith('/api/image/') and self.command in ('GET','HEAD'):
                item=identifier(path.rsplit('/',1)[1]);image_type=q.get('type',['Primary'])[0]
                if image_type not in ('Primary','Backdrop','Thumb','Logo'):raise ValueError('图片类型无效')
                url=emby.base+f'/Items/{item}/Images/{image_type}'+('/0' if image_type=='Backdrop' else '')
                with http() as s,s.get(url,headers=emby.headers(),params={'maxWidth':1600 if image_type=='Backdrop' else 600,'quality':85},allow_redirects=False,timeout=(10,20)) as r:
                    if r.status_code!=200 or not r.headers.get('Content-Type','').startswith('image/'):self.send(404,b'');return
                    self.send(200,r.content,r.headers['Content-Type']);return
            if path=='/api/play' and self.command=='POST':
                data=self.body();item=identifier(data['id'])
                info=emby.api(f'/Items/{item}/PlaybackInfo','POST',data=playback_request(user))
                sources=info.get('MediaSources') or []
                source=next((s for s in sources if s.get('Id')==data.get('source')),sources[0] if sources else None)
                if not source:raise ValueError('Emby 没有返回可播放媒体源')
                if source.get('IsInfiniteStream') or source.get('RequiresOpening'):raise ValueError('当前版本仅支持点播原文件')
                key=secrets.token_urlsafe(24);play={'item':item,'source':identifier(source['Id']),'session':info.get('PlaySessionId'),'target':None,'host':None,'last_report':0,'started':False,'resolve_lock':threading.Lock(),'streams':source.get('MediaStreams',[])}
                with self.server.lock:
                    if len(self.server.plays)>=4:raise ValueError('最多同时打开四个播放区域，请先关闭一个')
                    self.server.plays[key]=play
                try:
                    s,r=self.server.open_media(play,'bytes=0-4095')
                    try:
                        head=next(r.iter_content(4096),b'')
                        container=detect_container(head,source.get('Container',''))
                        play['diagnostic']={'container':container,'bytesProbed':len(head),'host':play['host'],'lastError':None,'fileHeader':head[:32].hex(),'sourceContainer':source.get('Container',''),'sourceSize':source.get('Size'),'durationMs':int(source.get('RunTimeTicks',0) or 0)//10000,'seekStrategy':'timestamp-interpolation-with-binary-fallback','contentRange':r.headers.get('Content-Range'),'contentType':r.headers.get('Content-Type'),'requests':[]}
                        total=r.headers.get('Content-Range','').rsplit('/',1)[-1]
                        if total.isdigit():play['totalSize']=int(total)
                    finally:r.close();s.close()
                except Exception:
                    with self.server.lock:self.server.plays.pop(key,None)
                    raise
                self.send(200,{'key':key,'url':'/media/'+key,'host':play['host'],'container':container,'streams':source.get('MediaStreams',[]),'durationMs':int(source.get('RunTimeTicks',0) or 0)//10000});return
            if path=='/api/subtitles' and self.command=='GET':
                key=q.get('key',[''])[0];play=self.server.plays.get(key)
                if not play:raise LookupError('播放会话已关闭')
                if 'subtitle_options' not in play:
                    streams=play.get('streams',[]);errors=[];routes=[]
                    for route in (f'/Users/{user}/Items/'+play['item'],'/Items/'+play['item']):
                        try:
                            full=emby.api(route,params={'UserId':user,'Fields':'MediaStreams,MediaSources'})
                            streams=merge_subtitle_streams(streams,full,play['source']);routes.append('user-item' if '/Users/' in route else 'item')
                        except (ValueError,requests.RequestException) as error:
                            errors.append(type(error).__name__)
                        if subtitle_options(streams):break
                    play['subtitle_options']=subtitle_options(streams)
                    play.setdefault('diagnostic',{})['subtitles']={'trackCount':sum(x.get('Type')=='Subtitle' for x in streams),'externalTracks':play['subtitle_options'],'metadataSources':routes,'metadataErrors':errors}
                choices=play['subtitle_options']
                if not q.get('index'):
                    self.send(200,{'Items':choices});return
                index=int(q['index'][0]);choice=next((x for x in choices if x['index']==index),None)
                if not choice or not choice['supported']:raise ValueError('该外挂字幕格式暂不支持本地文本渲染')
                url=emby.base+f"/Videos/{play['item']}/{play['source']}/Subtitles/{index}/Stream.{choice['format']}"
                with http() as session,session.get(url,headers=emby.headers(),params={'StartPositionTicks':0},allow_redirects=False,stream=True,timeout=(10,30)) as response:
                    if response.status_code!=200:raise ValueError('Emby 字幕接口返回 HTTP '+str(response.status_code))
                    content=bytearray()
                    for chunk in response.iter_content(65536):
                        content.extend(chunk)
                        if len(content)>16*1024*1024:raise ValueError('外挂字幕超过 16 MB')
                    if not content or bytes(content).lstrip().lower().startswith((b'<html',b'<!doctype',b'{"')):raise ValueError('字幕接口未返回字幕文件')
                self.send(200,bytes(content),'application/octet-stream');return
            if path=='/api/diagnostic' and self.command=='GET':
                play=self.server.plays.get(q.get('key',[''])[0])
                if not play:raise LookupError('播放会话已关闭')
                self.send(200,play.get('diagnostic',{}));return
            if path.startswith('/media/') and self.command in ('GET','HEAD'):
                key=path.rsplit('/',1)[1];play=self.server.plays.get(key)
                if not play:raise LookupError('播放会话已关闭，请重新选片')
                value=validate_range(self.headers.get('Range'))
                play.setdefault('diagnostic',{}).setdefault('requests',[]).append({'range':value,'method':self.command})
                play['diagnostic']['requests']=play['diagnostic']['requests'][-8:]
                if self.command=='HEAD' and play.get('totalSize') and not value:
                    play['diagnostic']['requests'][-1].update(status=200,cached=True,contentLength=str(play['totalSize']),headerMs=0)
                    self.send_response(200);self.send_header('Content-Type','application/octet-stream');self.send_header('Content-Length',str(play['totalSize']));self.send_header('Accept-Ranges','bytes');self.end_headers();return
                request_start=time.monotonic()
                try:s,r=self.server.open_media(play,value)
                except Exception as error:
                    play.setdefault('diagnostic',{})['lastError']=str(error) if isinstance(error,ValueError) else '115 原文件读取连接失败或超时'
                    raise
                try:
                    play['diagnostic']['requests'][-1].update(status=r.status_code,contentRange=r.headers.get('Content-Range'),contentLength=r.headers.get('Content-Length'),headerMs=round((time.monotonic()-request_start)*1000))
                    self.send_response(r.status_code)
                    self.send_header('Content-Type','application/octet-stream')
                    for h in ('Content-Length','Content-Range','Accept-Ranges','ETag','Last-Modified'):
                        if h in r.headers:self.send_header(h,r.headers[h])
                    if 'Content-Length' not in r.headers:self.send_header('Connection','close');self.close_connection=True
                    self.end_headers()
                    if self.command!='HEAD':
                        received=0;metric=play['diagnostic']['requests'][-1]
                        for chunk in r.iter_content(16*1024):
                            if key not in self.server.plays:break
                            if chunk:
                                if not received:metric['firstByteMs']=round((time.monotonic()-request_start)*1000)
                                received+=len(chunk);metric['bytes']=received
                                metric['elapsedMs']=round((time.monotonic()-request_start)*1000)
                                self.wfile.write(chunk)
                finally:r.close();s.close()
                return
            if path=='/api/report' and self.command=='POST':
                data=self.body();play=self.server.plays.get(data.get('key'))
                if not play:raise LookupError('播放会话已关闭')
                event=data.get('event','Progress')
                if event not in ('Playing','Progress','Stopped'):raise ValueError('播放事件无效')
                ticks=max(0,int(float(data.get('milliseconds',0))*10000))
                payload={'ItemId':play['item'],'MediaSourceId':play['source'],'PlaySessionId':play['session'],'PositionTicks':ticks,'IsPaused':bool(data.get('paused')),'PlayMethod':'DirectPlay','CanSeek':True}
                # Claiming DirectPlay in Emby alone does not prove the 302 route; open_media verifies it.
                if event=='Stopped' and not play['started']:
                    self.server.plays.pop(data['key'],None);self.send(200,{});return
                if event!='Stopped' and not play['started']:
                    emby.api('/Sessions/Playing','POST',data=payload);play['started']=True
                elif event!='Playing' or play['started']:
                    route='/Sessions/Playing/Stopped' if event=='Stopped' else '/Sessions/Playing/Progress'
                    try:emby.api(route,'POST',data=payload)
                    finally:
                        if event=='Stopped':
                            play['started']=False
                            if data.get('release',True):self.server.plays.pop(data['key'],None)
                self.send(200,{});return
            self.send(404,{'error':'接口不存在'});return
        if self.command not in ('GET','HEAD'):self.send(405,{});return
        relative='index.html' if path=='/' else re.sub(r'^vendor/v[0-9]+/','vendor/',path.lstrip('/'))
        file=(ROOT/'web'/relative).resolve();webroot=(ROOT/'web').resolve()
        if not file.is_relative_to(webroot) or not file.is_file():self.send(404,b'');return
        ctype=('application/wasm' if file.suffix=='.wasm' else 'text/javascript; charset=utf-8' if file.suffix=='.js' else mimetypes.guess_type(file)[0] or 'application/octet-stream')
        self.send(200,file.read_bytes(),ctype)

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--port',type=int,default=0);parser.add_argument('--no-browser',action='store_true');args=parser.parse_args()
    server=AppServer(('127.0.0.1',args.port))
    url=f'http://127.0.0.1:{server.server_port}/?launch={server.launch_key}'
    print('Emby Direct Web 0.8 — 本机解码，禁止服务器转码',flush=True)
    print('启动地址：'+url,flush=True)
    if not args.no_browser:webbrowser.open(url)
    try:server.serve_forever()
    except KeyboardInterrupt:pass
    finally:server.server_close()

if __name__=='__main__':main()
