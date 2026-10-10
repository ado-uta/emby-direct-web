"""Portable Windows tray launcher; HTTP service remains local-only."""
import argparse
import ctypes
import json
import sys
import threading
import webbrowser
from pathlib import Path
import requests
from server import AppServer

def self_test(output):
    import pystray
    from PIL import Image
    icon=pystray.Icon('test',Image.new('RGBA',(16,16)))
    assert icon.name=='test'
    server=AppServer(('127.0.0.1',0))
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    base=f'http://127.0.0.1:{server.server_port}'
    try:
        with requests.Session() as s:
            s.trust_env=False
            r=s.get(base+'/?launch='+server.launch_key,timeout=5);r.raise_for_status();assert 'Direct Web' in r.text
            for path in ['/app.js','/vendor/avplayer.js','/wasm/decode/h264-simd.wasm','/wasm/decode/ac3-simd.wasm']:
                r=s.get(base+path,timeout=5);r.raise_for_status();assert len(r.content)>100
            r=requests.get(base+'/api/items',timeout=5);assert r.status_code==403
        Path(output).write_text(json.dumps({'ok':True,'checks':['bootstrap-cookie','web-assets','wasm-resources','unauthenticated-rejection']}),encoding='utf-8')
    except Exception as e:
        Path(output).write_text(json.dumps({'ok':False,'error':str(e)}),encoding='utf-8');raise
    finally:server.shutdown();server.server_close()

def main():
    parser=argparse.ArgumentParser();parser.add_argument('--self-test');args=parser.parse_args()
    if args.self_test:self_test(args.self_test);return
    import pystray
    from PIL import Image,ImageDraw
    try:
        server=AppServer(('127.0.0.1',18765))
    except OSError:
        # Do not terminate another application using this port.
        server=AppServer(('127.0.0.1',0))
    threading.Thread(target=server.serve_forever,daemon=True).start()
    url=f'http://127.0.0.1:{server.server_port}/?launch={server.launch_key}'
    def open_page(*_):webbrowser.open(url)
    def stop(icon,*_):server.shutdown();server.server_close();icon.stop()
    image=Image.new('RGBA',(64,64),(13,17,23,255));draw=ImageDraw.Draw(image);draw.rounded_rectangle((4,4,60,60),radius=14,fill=(114,224,177));draw.polygon([(24,17),(24,47),(46,32)],fill=(13,17,23))
    icon=pystray.Icon('EmbyDirectWeb',image,'Emby Direct Web · 本机播放器',menu=pystray.Menu(pystray.MenuItem('打开播放网页',open_page,default=True),pystray.MenuItem('退出程序',stop)))
    open_page();icon.run()

if __name__=='__main__':
    try:main()
    except Exception as error:
        if '--self-test' in sys.argv:raise
        ctypes.windll.user32.MessageBoxW(0,'启动失败：'+str(error),'Emby Direct Web',0x10)
