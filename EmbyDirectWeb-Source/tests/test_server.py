import unittest, threading, json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import requests
from server import AppServer

class Upstream(BaseHTTPRequestHandler):
    cloud=''
    seen=[]
    fallback=False
    subtitle_detail_mode=0
    def log_message(self,*a): pass
    def do_POST(self):
        data=json.loads(self.rfile.read(int(self.headers.get('Content-Length',0))) or b'{}')
        self.seen.append((self.path,dict(self.headers),data))
        result=({'AccessToken':'secret-emby','User':{'Id':'u','Name':'test'}} if 'AuthenticateByName' in self.path else {'MediaSources':[{'Id':'m','Container':'mkv'}],'PlaySessionId':'ps'})
        self.send_response(200); self.send_header('Content-Type','application/json');self.end_headers();self.wfile.write(json.dumps(result).encode())
    def do_GET(self):
        self.seen.append((self.path,dict(self.headers),{}))
        if self.subtitle_detail_mode and (self.path.startswith('/Users/u/Items/1') or self.path.startswith('/Items/1?')):
            visible=self.subtitle_detail_mode==1 or self.path.startswith('/Items/')
            data={'MediaSources':[{'Id':'m','MediaStreams':[{'Type':'Video','Index':0}]}],'MediaStreams':[{'Type':'Subtitle','Index':2,'IsExternal':True,'Codec':'srt','Path':'private/path.srt'}] if visible else []}
            self.send_response(200);self.end_headers();self.wfile.write(json.dumps(data).encode());return
        if self.path.startswith('/Items/Filters'):
            self.send_response(200);self.send_header('Content-Type','application/json');self.end_headers();self.wfile.write(b'{"Genres":[],"Years":[]}');return
        if '/Subtitles/' in self.path:
            self.send_response(200);self.end_headers();self.wfile.write(b'1\n00:00:00,000 --> 00:00:05,000\nSubtitle test\n');return
        if self.path.startswith('/Videos/'):
            if self.fallback:
                self.send_response(200);self.end_headers();self.wfile.write(b'NO_HK_VIDEO');return
            self.send_response(302);self.send_header('Location',self.cloud+'/file');self.end_headers();return
        if self.path.startswith('/file'):
            data=b'0123456789';r=self.headers.get('Range')
            if r:
                a,b=r.removeprefix('bytes=').split('-');a=int(a or 0);b=int(b) if b else 9;part=data[a:b+1]
                self.send_response(206);self.send_header('Content-Range',f'bytes {a}-{b}/10')
            else: self.send_response(200);part=data
            self.send_header('Content-Length',str(len(part)));self.send_header('Accept-Ranges','bytes');self.end_headers();self.wfile.write(part);return
        self.send_response(200);self.send_header('Content-Type','application/json');self.end_headers();self.wfile.write(b'{"Items":[],"TotalRecordCount":0}')

class IntegrationTests(unittest.TestCase):
    def setUp(self):
        Upstream.seen=[];Upstream.fallback=False;Upstream.subtitle_detail_mode=0
        self.cloud=ThreadingHTTPServer(('127.0.0.1',0),Upstream)
        self.emby=ThreadingHTTPServer(('127.0.0.2',0),Upstream)
        Upstream.cloud=f'http://127.0.0.1:{self.cloud.server_port}'
        self.app=AppServer(('127.0.0.1',0),allow_private_media=True)
        for srv in [self.cloud,self.emby,self.app]:threading.Thread(target=srv.serve_forever,daemon=True).start()
        self.url=f'http://127.0.0.1:{self.app.server_port}';self.client=requests.Session();self.client.trust_env=False
        self.client.get(self.url+'/?launch='+self.app.launch_key)
    def tearDown(self):
        self.client.close()
        for srv in [self.app,self.emby,self.cloud]:srv.shutdown();srv.server_close()
    def login(self):
        r=self.client.post(self.url+'/api/login',json={'server':f'http://127.0.0.2:{self.emby.server_port}','username':'test','password':'pw'})
        self.assertEqual(r.status_code,200,r.text)
    def test_302_range_and_no_token_leak(self):
        self.login();r=self.client.post(self.url+'/api/play',json={'id':'1'});self.assertEqual(r.status_code,200,r.text);play=r.json()
        media=self.client.get(self.url+play['url'],headers={'Range':'bytes=2-5'})
        self.assertEqual(media.status_code,206);self.assertEqual(media.content,b'2345')
        self.assertEqual(media.headers['Content-Range'],'bytes 2-5/10')
        for path,headers,body in Upstream.seen:
            if path.startswith('/file'):
                self.assertNotIn('secret-emby',str(headers));self.assertNotIn('X-Emby-Authorization',headers)
            if 'PlaybackInfo' in path:
                self.assertFalse(body['EnableTranscoding']);self.assertFalse(body['EnableDirectStream'])
    def test_library_filters_forwarded(self):
        self.login()
        r=self.client.get(self.url+'/api/items?parent=category&genres=Drama&year=2024&person=actor&sort=rating')
        self.assertEqual(r.status_code,200)
        from urllib.parse import urlsplit,parse_qs
        query=parse_qs(urlsplit(Upstream.seen[-1][0]).query)
        self.assertEqual(query['Genres'],['Drama'])
        self.assertEqual(query['Years'],['2024'])
        self.assertEqual(query['PersonIds'],['actor'])
        self.assertEqual(query['SortBy'],['CommunityRating,SortName'])
        self.assertEqual(query['SortOrder'],['Descending'])
    def test_filter_options_scoped(self):
        self.login()
        r=self.client.get(self.url+'/api/filters?parent=category')
        self.assertEqual(r.status_code,200)
        self.assertIn('/Items/Filters?',Upstream.seen[-1][0])
        self.assertIn('ParentId=category',Upstream.seen[-1][0])

    def test_external_tracks_from_detail_and_secondary_route(self):
        self.login()
        for mode in (1,2):
            Upstream.subtitle_detail_mode=mode
            key='detail-'+str(mode)
            self.app.plays[key]={'item':'1','source':'m','streams':[{'Type':'Audio','Index':1}]}
            data=self.client.get(self.url+'/api/subtitles?key='+key).json()
            self.assertEqual([x['index'] for x in data['Items']],[2])
            diagnostic=self.client.get(self.url+'/api/diagnostic?key='+key).json()['subtitles']
            self.assertEqual(diagnostic['trackCount'],1)
            self.assertNotIn('private/path',json.dumps(diagnostic))
            self.assertEqual(diagnostic['metadataSources'],['user-item'] if mode==1 else ['user-item','item'])

    def test_emby_external_subtitle_download(self):
        self.login()
        self.app.plays['subtitle-test']={'item':'1','source':'m','streams':[{'Type':'Subtitle','Index':2,'IsExternal':True,'Codec':'srt'}]}
        r=self.client.get(self.url+'/api/subtitles?key=subtitle-test')
        self.assertEqual(r.status_code,200);self.assertEqual(r.json()['Items'][0]['index'],2)
        r=self.client.get(self.url+'/api/subtitles?key=subtitle-test&index=2')
        self.assertEqual(r.status_code,200);self.assertIn(b'Subtitle test',r.content)
        path,headers,_=Upstream.seen[-1]
        self.assertIn('/Videos/1/m/Subtitles/2/Stream.srt',path)
        self.assertEqual(headers['X-Emby-Token'],'secret-emby')
        self.assertNotIn(b'secret-emby',r.content)
        self.assertEqual(self.client.get(self.url+'/api/subtitles?key=subtitle-test&index=999').status_code,400)

    def test_category_lists_recursive_video_items(self):
        self.login();r=self.client.get(self.url+'/api/items?parent=category')
        self.assertEqual(r.status_code,200)
        from urllib.parse import urlsplit,parse_qs
        path=next(path for path,headers,body in reversed(Upstream.seen) if '/Items?' in path)
        query=parse_qs(urlsplit(path).query)
        self.assertEqual(query['ParentId'],['category'])
        self.assertEqual(query['Recursive'],['True'])
        self.assertEqual(query['MediaTypes'],['Video'])
    def test_container_detection_ignores_strm_hint(self):
        from server import detect_container
        self.assertEqual(detect_container(b'\x1a\x45\xdf\xa3xxxx','strm'),'mkv')
        self.assertEqual(detect_container(b'\x00\x00\x00\x18ftypisom','strm'),'mp4')
        self.assertEqual(detect_container(b'unknown','strm'),'')
    def test_head_uses_verified_size_without_cloud_request(self):
        self.login();p=self.client.post(self.url+'/api/play',json={'id':'1'}).json()
        before=len(Upstream.seen)
        r=self.client.head(self.url+p['url'])
        self.assertEqual(r.status_code,200)
        self.assertEqual(r.headers['Content-Length'],'10')
        self.assertEqual(len(Upstream.seen),before)
        self.assertTrue(self.app.plays[p['key']]['diagnostic']['requests'][-1]['cached'])
    def test_item_reads_full_overview_and_fallback(self):
        self.login()
        from unittest.mock import Mock
        mock=Mock(side_effect=[{'Id':'1','Name':'Film'},{'Id':'1','Overview':'Full synopsis','People':[{'Name':'Actor'}]}])
        self.app.emby.api=mock
        r=self.client.get(self.url+'/api/item?id=1')
        self.assertEqual(r.status_code,200)
        self.assertEqual(r.json()['Overview'],'Full synopsis')
        self.assertIn('Overview',mock.call_args_list[0].kwargs['params']['Fields'])
        self.assertEqual(mock.call_args_list[1].args[0],'/Items/1')
    def test_hk_video_fallback_rejected(self):
        self.login();Upstream.fallback=True;r=self.client.post(self.url+'/api/play',json={'id':'1'});self.assertEqual(r.status_code,400);self.assertIn('302',r.json()['error'])
    def test_cross_origin_and_unknown_session_rejected(self):
        self.assertEqual(requests.get(self.url+'/api/items').status_code,403)
        self.assertEqual(self.client.post(self.url+'/api/login',json={},headers={'Origin':'https://evil.example'}).status_code,403)
    def test_logout_invalidates_media(self):
        self.login();p=self.client.post(self.url+'/api/play',json={'id':'1'}).json();self.client.post(self.url+'/api/logout',json={});self.assertEqual(self.client.get(self.url+p['url']).status_code,401)
    def test_end_keeps_stream_available_for_replay(self):
        self.login();p=self.client.post(self.url+'/api/play',json={'id':'1'}).json()
        self.client.post(self.url+'/api/report',json={'key':p['key'],'event':'Playing','milliseconds':10})
        self.client.post(self.url+'/api/report',json={'key':p['key'],'event':'Stopped','milliseconds':100,'release':False})
        r=self.client.get(self.url+p['url'],headers={'Range':'bytes=0-1'})
        self.assertEqual(r.status_code,206)
        self.client.post(self.url+'/api/report',json={'key':p['key'],'event':'Playing','milliseconds':0})
        self.assertTrue(self.app.plays[p['key']]['started'])
    def test_range_not_honored_rejected(self):
        self.login();p=self.client.post(self.url+'/api/play',json={'id':'1'}).json();self.assertEqual(self.client.get(self.url+p['url'],headers={'Range':'bytes=1-2,4-5'}).status_code,400)

if __name__=='__main__':unittest.main()
