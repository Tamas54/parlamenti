import io
import json
import sys
import threading
import unittest
import urllib.error
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
import parlament_proxy as p
import kepviselok

DATA = {'metadata': {'fields': [{'name': 'id'}]}, 'rows': [['123']], 'response': {'totalSize': 1}}
RAW = json.dumps(DATA).encode()
URL = p.PROBE_URL


class ProxyTests(unittest.TestCase):
    def setUp(self):
        self.pool = p.Pool()
        self.pool.enabled = True
        self.ctx = patch.object(p, 'POOL', self.pool)
        self.ctx.start()
        self.addCleanup(self.ctx.stop)

    def test_direct_success_does_not_discover(self):
        with patch.object(p, 'read', return_value=RAW), patch.object(self.pool, 'working_proxy') as discovery:
            self.assertEqual(kepviselok._post(URL, {}), DATA)
            discovery.assert_not_called()

    def test_captcha_rotates_and_preserves_post(self):
        a, b = 'http://a:80', 'http://b:80'
        self.pool.note_ok(a)
        self.pool.note_ok(b)
        with patch.object(p, 'read', side_effect=[p.CaptchaHiba('blocked'), OSError('dead'), RAW]) as read:
            self.assertEqual(kepviselok._post(URL, {'q': 'teszt'}), DATA)
            self.assertEqual([c.args[3] for c in read.call_args_list], [None, a, b])
            self.assertTrue(all(json.loads(c.args[1]) == {'q': 'teszt'} for c in read.call_args_list))
        self.assertIn(a, self.pool._cooldown)
        self.assertNotIn(a, self.pool._memo)
        self.assertTrue(self.pool.status()['direct_cooldown'])

    def test_captcha_fallback_if_pool_empty(self):
        with patch.object(p, 'read', side_effect=p.CaptchaHiba('blocked')), patch.object(self.pool, 'working_proxy', return_value=None):
            with self.assertRaises(p.CaptchaHiba):
                kepviselok._post(URL, {})

    def test_disabled_pool_no_list_fetch(self):
        self.pool.enabled = False
        with patch.object(p, 'read', side_effect=p.CaptchaHiba('blocked')), patch.object(self.pool, 'candidates') as candidates:
            with self.assertRaises(p.CaptchaHiba):
                kepviselok._post(URL, {})
            candidates.assert_not_called()

    def test_permanent_http_error_not_retried(self):
        err = urllib.error.HTTPError(URL, 400, 'bad', {}, io.BytesIO())
        with patch.object(p, 'read', side_effect=err) as read:
            with self.assertRaises(p.UpstreamHiba):
                kepviselok._post(URL, {})
            self.assertEqual(read.call_count, 1)

    def test_json_html_rotates(self):
        self.pool.note_ok('http://a:80')
        with patch.object(p, 'read', side_effect=[b'<html>blocked</html>', RAW]):
            self.assertEqual(kepviselok._post(URL, {}), DATA)

    def test_get_uses_same_pool(self):
        self.pool.note_ok('http://a:80')
        with patch.object(p, 'read', side_effect=[p.CaptchaHiba(), b'<svg fill="#123456"/>']):
            self.assertIn('#123456', kepviselok._get_text('https://www.parlament.hu/icon'))

    def test_no_cooldown_reuse_and_scan_throttle(self):
        self.pool.note_failed('http://a:80')
        with patch.object(self.pool, 'candidates', return_value=['http://a:80']), patch.object(self.pool, 'probe') as probe:
            self.assertIsNone(self.pool.working_proxy())
            self.assertIsNone(self.pool.working_proxy())
            probe.assert_not_called()

    def test_rotation_expiration_and_recovery(self):
        with patch.object(p.time, 'monotonic', return_value=100):
            self.pool.note_ok('http://a:80')
        with patch.object(p.time, 'monotonic', return_value=101):
            self.pool.note_ok('http://b:80')
        with patch.object(p.time, 'monotonic', return_value=102):
            self.assertEqual(self.pool.cached(), 'http://a:80')
        with patch.object(p.time, 'monotonic', return_value=103):
            self.assertEqual(self.pool.cached(), 'http://b:80')
            self.pool.note_failed('http://b:80')
        with patch.object(p.time, 'monotonic', return_value=2000):
            self.assertIsNone(self.pool.cached())
            self.assertEqual(self.pool.status()['cooldown_count'], 0)

    def test_single_discovery_for_concurrent_callers(self):
        entered, release = threading.Event(), threading.Event()
        def probe(_):
            entered.set()
            release.wait(2)
            return True
        with patch.object(self.pool, 'candidates', return_value=['http://a:80']) as candidates, patch.object(self.pool, 'probe', side_effect=probe):
            with ThreadPoolExecutor(2) as ex:
                first = ex.submit(self.pool.working_proxy)
                self.assertTrue(entered.wait(2))
                second = ex.submit(self.pool.working_proxy)
                release.set()
                self.assertEqual(first.result(), 'http://a:80')
                self.assertEqual(second.result(), 'http://a:80')
            self.assertEqual(candidates.call_count, 1)

    def test_https_and_host_enforced(self):
        for url in ('http://www.parlament.hu/', 'https://example.com', 'https://www.parlament.hu:444/', 'https://user@www.parlament.hu/'):
            with self.subTest(url=url), self.assertRaises(ValueError):
                p.fetch(url)
        with self.assertRaises(ValueError):
            p.HTTPSOnly().redirect_request(None, None, 302, '', {}, 'http://www.parlament.hu/')

    def test_status_has_no_proxy_addresses(self):
        self.pool.note_ok('http://secret:password@host:80')
        self.assertNotIn('secret', json.dumps(self.pool.status()))

class FallbackTests(unittest.TestCase):
    def test_search_reports_snapshot_fallback_for_exhausted_pool(self):
        import tevekenyseg
        with patch.object(tevekenyseg, 'get_data', return_value={}), patch.object(tevekenyseg, '_post', side_effect=p.UpstreamHiba('no exits')):
            result = tevekenyseg.felszolalas_szoveg_kereses('iskola')
            self.assertIsNone(result['osszes'])
            self.assertIn('tárolt adatokban', result['figyelmeztetes'])
            self.assertNotIn('CAPTCHA', result['figyelmeztetes'])


if __name__ == '__main__':
    unittest.main()
