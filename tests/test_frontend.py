import json
import os
from pathlib import Path
import re
import socket
import subprocess
import sys
import tempfile
import time
import unittest
from urllib.error import HTTPError
from urllib.request import urlopen

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))
from local import validate_frontend


class FrontendFilesTests(unittest.TestCase):
    def test_all_referenced_assets_exist(self):
        validate_frontend()

    def test_incomplete_frontend_has_clear_startup_error(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / 'index.html').write_text('<script src="/assets/missing.js"></script>')
            with self.assertRaisesRegex(ValueError, 'Frontend files are missing'):
                validate_frontend(root)

    def test_missing_html_has_clear_startup_error(self):
        with tempfile.TemporaryDirectory() as folder:
            with self.assertRaisesRegex(ValueError, 'Frontend missing'):
                validate_frontend(Path(folder))

    def test_http_assets_and_missing_asset_response(self):
        with tempfile.TemporaryDirectory() as folder:
            with socket.socket() as available:
                available.bind(('127.0.0.1', 0))
                port = available.getsockname()[1]
            process = subprocess.Popen([sys.executable, '-u', str(ROOT / 'backend' / 'local.py'), '--port', str(port)], cwd=folder, env={**os.environ, 'DB_PATH': str(Path(folder) / 'http-test.db')}, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
            try:
                base = f'http://127.0.0.1:{port}'
                for attempt in range(50):
                    try:
                        with urlopen(base + '/api/health', timeout=1) as response:
                            self.assertEqual(json.load(response)['status'], 'ok')
                        break
                    except OSError:
                        if process.poll() is not None:
                            self.fail('Python server failed to start.')
                        time.sleep(.1)
                else:
                    self.fail('Server startup timed out.')
                with urlopen(base) as response:
                    html = response.read().decode()
                refs = re.findall(r'(?:src|href)=[\"\'](/[^\"\']+)[\"\']', html)
                self.assertGreaterEqual(len(refs), 3)
                for ref in refs:
                    with self.subTest(asset=ref):
                        with urlopen(base + ref) as response:
                            expected = 'text/css' if ref.endswith('.css') else 'text/javascript'
                            self.assertEqual(response.headers.get_content_type(), expected)
                            self.assertNotIn(b'<!doctype html>', response.read()[:100].lower())
                for ref in ['/assets/missing.js', '/assets/missing.css']:
                    with self.assertRaises(HTTPError) as caught:
                        urlopen(base + ref)
                    self.assertEqual(caught.exception.code, 404)
            finally:
                process.terminate()
                process.wait(timeout=5)
