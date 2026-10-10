"""Emby catalog queries; all filtering happens before pagination."""
import re,time
SORTS={'name':('SortName','Ascending'),'newest':('PremiereDate,SortName','Descending'),'added':('DateCreated,SortName','Descending'),'rating':('CommunityRating,SortName','Descending'),'year':('ProductionYear,SortName','Descending')}
class _TimedCatalog:
    def __init__(self,target):
        object.__setattr__(self,'_target',target)
        object.__setattr__(self,'metrics',{'upstreamMs':0,'upstreamRequests':0,'cacheHit':False})
    def __getattr__(self,name):return getattr(self._target,name)
    def __setattr__(self,name,value):setattr(self._target,name,value)
    def api(self,*args,**kwargs):
        at=time.perf_counter();self.metrics['upstreamRequests']+=1
        try:return self._target.api(*args,**kwargs)
        finally:self.metrics['upstreamMs']+=(time.perf_counter()-at)*1000

def query_items(emby,user,q):
    timed=_TimedCatalog(emby);at=time.perf_counter()
    result=_query_items(timed,user,q)
    duration=(time.perf_counter()-at)*1000
    metrics=dict(timed.metrics)
    metrics['localMs']=round(max(0,duration-metrics['upstreamMs']),2)
    metrics['upstreamMs']=round(metrics['upstreamMs'],2)
    metrics['totalMs']=round(duration,2)
    result=dict(result,CatalogTiming=metrics)
    return result

def _query_items(emby,user,q):
    first=lambda k,default='':q.get(k,[default])[0]
    start=max(0,int(first('start','0')))
    sort=first('sort','name')
    if sort not in SORTS:raise ValueError('排序方式无效')
    params={'Limit':60,'StartIndex':start,'Fields':'MediaSources,UserData,Overview,Genres,People,Taglines,SortName,DateCreated','SortBy':SORTS[sort][0],'SortOrder':SORTS[sort][1]}
    route=f'/Users/{user}/Items'
    if first('resume'):route+='/Resume';params['MediaTypes']='Video'
    if first('parent'):
        parent=first('parent')
        if not re.fullmatch(r'[A-Za-z0-9_-]{1,128}',parent):raise ValueError('媒体 ID 无效')
        params['ParentId']=parent
    if first('search'):params['SearchTerm']=first('search')[:200]
    genres=list(dict.fromkeys(g for g in q.get('genres',[]) if g))
    if len(genres)>20 or any(len(g)>200 or '|' in g for g in genres):raise ValueError('分类选择过多或名称无效')
    if genres:params['Genres']='|'.join(genres)
    if first('year'):
        year=first('year')
        if not re.fullmatch(r'[0-9]{4}',year):raise ValueError('年份无效')
        params['Years']=year
    if first('person'):
        person=first('person')
        if not re.fullmatch(r'[A-Za-z0-9_-]{1,128}',person):raise ValueError('演员 ID 无效')
        params['PersonIds']=person
    elif first('personName'):params['Person']=first('personName')[:200]
    if params.get('ParentId') or any(first(k) for k in ('search','year','person','personName','videos')) or genres:
        params.update(Recursive=True,MediaTypes='Video',IncludeItemTypes='Movie,Episode,Video')
    mode=first('match','or')
    if mode not in ('and','or'):raise ValueError('多选模式无效')
    try:
        if mode!='and' or len(genres)<2:return emby.api(route,params=params)
        return _scan_genre_items(emby,route,params,genres,mode,start,genres[0])
    except ValueError as error:
        if not genres or not re.search(r'HTTP 500\b',str(error)):raise
        # Some Emby/proxy combinations fail on the Genres parameter. Keep all
        # other server-side constraints and sort order; match genres on metadata.
        return _scan_genre_items(emby,route,params,genres,mode,start,None)


def _index_params(params,server_genre):
    scan=dict(params,Limit=200,StartIndex=0)
    scan.pop('Genres',None)
    if server_genre is not None:scan['Genres']=server_genre
    return scan

def _read_index(emby,route,scan):
    pairs=[];cursor=0
    while cursor<50000:
        scan['StartIndex']=cursor
        result=emby.api(route,params=scan);batch=result.get('Items',[])
        for item in batch:
            names=item.get('Genres') or [g.get('Name','') for g in item.get('GenreItems',[])]
            actual=frozenset(g.strip().casefold() for g in names if isinstance(g,str))
            pairs.append((item,actual))
        cursor+=len(batch);total=result.get('TotalRecordCount')
        if not batch or (total is not None and cursor>=total):break
    else:raise ValueError('分类候选超过五万部，请先限定媒体库或年份再筛选')
    return pairs

def _scan_genre_items(emby,route,params,genres,mode,start,server_genre):
    pairs=_read_index(emby,route,_index_params(params,server_genre))
    wanted={g.strip().casefold() for g in genres}
    items=[item for item,actual in pairs if (wanted.issubset(actual) if mode=='and' else bool(wanted&actual))]
    return {'Items':items[start:start+60],'TotalRecordCount':len(items),'QueryStrategy':'metadata-genre-fallback' if server_genre is None else 'genre-intersection'}


def filter_options(emby,user,parent=''):
    import requests
    params={'UserId':user,'IncludeItemTypes':'Movie,Episode,Video','MediaTypes':'Video'}
    if parent:params['ParentId']=parent
    errors=[]
    for route in ('/Items/Filters','/Items/Filters2'):
        try:
            data=emby.api(route,params=params)
            if 'Genres' not in data:raise ValueError('接口未返回分类字段')
            genres=sorted(set(g if isinstance(g,str) else g.get('Name','') for g in data.get('Genres',[])))
            years=sorted(set(int(y) for y in data.get('Years',[]) if str(y).isdigit()),reverse=True)
            result={'Genres':[g for g in genres if g],'Years':years,'Source':route}
            break
        except (ValueError,requests.RequestException) as error:errors.append(route+': '+str(error))
    else:
        genres=set();years=set();start=0
        scan={'Recursive':True,'MediaTypes':'Video','IncludeItemTypes':'Movie,Episode,Video','Fields':'Genres,ProductionYear','Limit':500,'EnableImages':False,'EnableUserData':False}
        if parent:scan['ParentId']=parent
        while start<50000:
            scan['StartIndex']=start
            data=emby.api(f'/Users/{user}/Items',params=scan);batch=data.get('Items',[])
            for item in batch:
                genres.update(item.get('Genres') or [g.get('Name','') for g in item.get('GenreItems',[])])
                year=item.get('ProductionYear')
                if str(year).isdigit():years.add(int(year))
            start+=len(batch)
            if not batch or start>=data.get('TotalRecordCount',start):break
        else:raise ValueError('分类回退候选超过五万部，请先选择具体媒体库')
        result={'Genres':sorted(g for g in genres if g),'Years':sorted(years,reverse=True),'Source':'item-metadata','CompatibilityErrors':errors}
    return result
