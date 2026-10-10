import re
from urllib.parse import urlsplit, urlunsplit, urljoin, parse_qs

def validate_base(url):
    url=url.strip().rstrip('/')
    p=urlsplit(url)
    if p.scheme not in ('http','https') or not p.hostname or p.username or p.password or p.query or p.fragment:
        raise ValueError('请输入 http:// 或 https:// 开头的 Emby 地址，不要包含账号、查询参数或片段')
    _=p.port
    return url

def origin(url):
    p=urlsplit(url)
    return (p.hostname.lower(),p.port or (443 if p.scheme=='https' else 80))

def direct_location(base, location):
    target=urljoin(base+'/',location)
    p=urlsplit(target)
    if p.scheme not in ('http','https') or not p.hostname or p.username or p.password:
        raise ValueError('302 返回的地址无效')
    if p.hostname.lower()==urlsplit(base).hostname.lower():
        raise ValueError('302 未离开 Emby 服务，已阻止从 HK 读取视频')
    q={k.lower():v for k,v in parse_qs(p.query).items()}
    if p.path.lower().endswith(('.m3u8','.mpd')) or '/transcod' in p.path.lower() or q.get('static',['true'])[0].lower()=='false':
        raise ValueError('拒绝转码或自适应流地址，只允许原文件')
    return target

def validate_range(value):
    if not value: return None
    m=re.fullmatch(r'bytes=(\d*)-(\d*)',value)
    if not m or not any(m.groups()): raise ValueError('只支持单段字节 Range')
    start,end=m.groups()
    if (start and end and int(start)>int(end)) or (not start and int(end)==0): raise ValueError('Range 无效')
    return value

def playback_request(user_id):
    return dict(UserId=user_id,EnableDirectPlay=True,EnableDirectStream=False,EnableTranscoding=False,IsPlayback=True,AutoOpenLiveStream=False)
