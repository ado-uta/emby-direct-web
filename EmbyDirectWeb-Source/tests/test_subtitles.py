import unittest
from subtitles import subtitle_options, merge_subtitle_streams
class SubtitleTests(unittest.TestCase):
    def test_multiple_text_and_bitmap_tracks(self):
        streams=[{'Type':'Subtitle','Index':2,'IsExternal':True,'Codec':'srt','Language':'chi'},{'Type':'Subtitle','Index':3,'IsExternal':True,'Codec':'ass','DisplayTitle':'English ASS'},{'Type':'Subtitle','Index':4,'IsExternal':True,'Codec':'pgssub'},{'Type':'Audio','Index':1}]
        result=subtitle_options(streams)
        self.assertEqual(len(result),3)
        self.assertTrue(result[0]['supported']);self.assertEqual(result[1]['format'],'ass')
        self.assertFalse(result[2]['supported'])

class MergeSubtitleTests(unittest.TestCase):
    def test_external_detail_track_survives_nonempty_media_source(self):
        full={'MediaSources':[{'Id':'m','MediaStreams':[{'Type':'Video','Index':0}]}],'MediaStreams':[{'Type':'Subtitle','Index':2,'IsExternal':True,'Codec':'srt'}]}
        result=subtitle_options(merge_subtitle_streams([{'Type':'Audio','Index':1}],full,'m'))
        self.assertEqual([x['index'] for x in result],[2])
    def test_unrelated_source_not_merged_and_duplicate_tracks_combined(self):
        full={'MediaSources':[{'Id':'other','MediaStreams':[{'Type':'Subtitle','Index':5,'IsExternal':True,'Codec':'ass'}]}],'MediaStreams':[{'Type':'Subtitle','Index':2,'IsExternal':True,'Codec':'srt'}]}
        result=subtitle_options(merge_subtitle_streams([{'Type':'Subtitle','Index':2,'Codec':'srt'}],full,'m'))
        self.assertEqual(len(result),1);self.assertEqual(result[0]['index'],2)
