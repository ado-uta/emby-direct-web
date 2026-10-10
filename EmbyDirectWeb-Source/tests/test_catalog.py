import unittest
from catalog import query_items
class Fake:
    def __init__(self):self.calls=[]
    def api(self,route,params=None):
        self.calls.append(dict(params))
        items=[{'Id':'1','Genres':['Drama','Action']},{'Id':'2','Genres':['Drama']},{'Id':'3','Genres':['Action']}]
        if params.get('Genres'):items=[x for x in items if any(g in x['Genres'] for g in params['Genres'].split('|'))]
        start=params['StartIndex'];return {'Items':items[start:start+params['Limit']], 'TotalRecordCount':len(items)}
class CatalogTests(unittest.TestCase):
    def test_and_before_pagination(self):
        e=Fake();r=query_items(e,'u',{'genres':['Drama','Action'],'match':['and']})
        self.assertEqual([x['Id'] for x in r['Items']],['1']);self.assertEqual(r['TotalRecordCount'],1)
    def test_or_and_filters(self):
        e=Fake();r=query_items(e,'u',{'genres':['Drama','Action'],'match':['or'],'year':['2024'],'person':['p'],'sort':['rating']})
        self.assertEqual(r['TotalRecordCount'],3)
        self.assertEqual(e.calls[-1]['Genres'],'Drama|Action')
        self.assertEqual(e.calls[-1]['Years'],'2024')
        self.assertEqual(e.calls[-1]['PersonIds'],'p')
    def test_bad_sort(self):
        with self.assertRaises(ValueError):query_items(Fake(),'u',{'sort':['unknown']})

class PaginationTests(unittest.TestCase):
    def test_and_scans_later_pages_without_program_cache(self):
        class Pages:
            def __init__(self):self.calls=0
            def api(self,route,params=None):
                self.calls+=1
                all_items=[{'Id':str(i),'Genres':['Drama']+(['Action'] if i>=210 else [])} for i in range(280)]
                start=params['StartIndex'];return {'Items':all_items[start:start+params['Limit']],'TotalRecordCount':280}
        e=Pages();q={'genres':['Drama','Action'],'match':['and']}
        first=query_items(e,'u',q)
        self.assertEqual(first['TotalRecordCount'],70)
        self.assertEqual(len(first['Items']),60)
        second=query_items(e,'u',dict(q,start=['60']))
        self.assertEqual(len(second['Items']),10)
        self.assertEqual(second['Items'][0]['Id'],'270')
        self.assertEqual(e.calls,4)

class FilterFallbackTests(unittest.TestCase):
    def test_failed_filter_api_uses_all_metadata_pages(self):
        from catalog import filter_options
        class Emby:
            def api(self,path,params=None):
                if '/Filters' in path:raise ValueError('HTTP 404')
                start=params['StartIndex']
                return {'Items':[{'Genres':['Drama'] if start==0 else ['Action'],'ProductionYear':2024-start//500}]*(500 if start==0 else 1),'TotalRecordCount':501} if start<501 else {'Items':[],'TotalRecordCount':501}
        result=filter_options(Emby(),'u','category')
        self.assertEqual(set(result['Genres']),{'Drama','Action'})
        self.assertEqual(result['Years'],[2024,2023])
        self.assertEqual(result['Source'],'item-metadata')

class Genre500FallbackTests(unittest.TestCase):
    class BrokenGenreApi:
        def __init__(self):self.calls=[]
        def api(self,path,params=None):
            self.calls.append(dict(params))
            if params.get('Genres'):raise ValueError('Emby 接口返回 HTTP 500')
            items=[{'Id':str(i),'Genres':['Drama']+(['Action'] if i%2==0 else [])} for i in range(130)]
            start=params['StartIndex'];limit=min(params['Limit'],40)
            return {'Items':items[start:start+limit],'TotalRecordCount':len(items)}
    def test_single_genre_500_preserves_full_pagination(self):
        e=self.BrokenGenreApi()
        result=query_items(e,'u',{'genres':['Action'],'start':['60'],'parent':['movies'],'year':['2024'],'sort':['rating']})
        self.assertEqual(result['TotalRecordCount'],65)
        self.assertEqual([x['Id'] for x in result['Items']],['120','122','124','126','128'])
        for query in e.calls:
            self.assertEqual(query['ParentId'],'movies');self.assertEqual(query['Years'],'2024')
            self.assertEqual(query['SortBy'],'CommunityRating,SortName')
    def test_multi_and_500(self):
        e=self.BrokenGenreApi();result=query_items(e,'u',{'genres':['Drama','Action'],'match':['and']})
        self.assertEqual(result['TotalRecordCount'],65)
    def test_multi_or_500(self):
        e=self.BrokenGenreApi();result=query_items(e,'u',{'genres':['Drama','Action'],'match':['or']})
        self.assertEqual(result['TotalRecordCount'],130)
    def test_other_api_errors_remain_visible(self):
        class Denied:
            def api(self,*args,**kwargs):raise ValueError('Emby 接口返回 HTTP 403')
        with self.assertRaisesRegex(ValueError,'403'):query_items(Denied(),'u',{'genres':['Drama']})

class NoProgramCacheTests(unittest.TestCase):
    def test_metadata_is_not_retained_on_connection(self):
        e=Genre500FallbackTests.BrokenGenreApi()
        query_items(e,'u',{'genres':['Action']})
        self.assertEqual(set(vars(e)),{'calls'})
