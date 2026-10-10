import unittest
from core import validate_base, direct_location, validate_range, playback_request

class PolicyTests(unittest.TestCase):
    def test_base_rejects_credentials_and_non_http(self):
        for url in ['file:///x','http://u:p@example.com','http://example.com/#x']:
            with self.subTest(url=url), self.assertRaises(ValueError): validate_base(url)
    def test_base_preserves_emby_prefix(self):
        self.assertEqual(validate_base(' https://example.com:8920/emby/ '),'https://example.com:8920/emby')
    def test_302_must_leave_server_origin(self):
        with self.assertRaises(ValueError): direct_location('https://hk.example/emby','/Videos/1/stream')
        with self.assertRaises(ValueError): direct_location('https://hk.example:8096','http://hk.example:9000/file')
        self.assertEqual(direct_location('https://hk.example/emby','https://cdn.115cdn.net/a?sign=abc'),'https://cdn.115cdn.net/a?sign=abc')
    def test_transcoding_url_rejected(self):
        for url in ['https://cdn.example/master.m3u8','https://cdn.example/video?Static=false']:
            with self.assertRaises(ValueError): direct_location('https://hk.example',url)
    def test_range(self):
        for value in ['bytes=0-1023','bytes=123-','bytes=-100']:
            self.assertEqual(validate_range(value),value)
        for value in ['bytes=0-1,3-4','x=1-2','bytes=9-2','bytes=-','bytes=0-1\r\nx: y']:
            with self.assertRaises(ValueError): validate_range(value)
    def test_no_server_transcode_or_remux(self):
        value=playback_request('u')
        self.assertEqual(value.get('UserId'),'u')
        self.assertTrue(value['EnableDirectPlay'])
        self.assertFalse(value['EnableDirectStream'])
        self.assertFalse(value['EnableTranscoding'])

if __name__=='__main__': unittest.main()
