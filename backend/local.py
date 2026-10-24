import argparse
import json
import os
import re
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import parse_qs, urlsplit
from app import Bank, dispatch
from storage import SQLiteStore

ROOT = Path(__file__).resolve().parents[1] / 'frontend' / 'dist'


def validate_frontend(root=ROOT):
    index = root / 'index.html'
    if not index.is_file():
        raise ValueError('Frontend missing: extract the complete project ZIP, including frontend/dist.')
    html = index.read_text(encoding='utf-8')
    referenced = re.findall(r'(?:src|href)=[\"\'](/[^\"\']+)[\"\']', html)
    missing = [name for name in referenced if not (root / name.lstrip('/')).is_file()]
    if missing:
        raise ValueError('Frontend files are missing: ' + ', '.join(missing) + '. Extract the complete project ZIP into a fresh folder.')


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument('--seed', action='store_true')
    parser.add_argument('--port', type=int, default=8000)
    args = parser.parse_args()
    try:
        validate_frontend()
    except ValueError as error:
        raise SystemExit(str(error))
    db_path = os.environ.get('DB_PATH') or str(Path(__file__).resolve().parents[1] / 'banking.db')
    bank = Bank(SQLiteStore(db_path))
    if args.seed:
        bank.seed('DemoBank2026!')
        print('Local demo password: DemoBank2026!', flush=True)

    class Handler(BaseHTTPRequestHandler):
        def run_request(self):
            parsed = urlsplit(self.path)
            if not parsed.path.startswith('/api/'):
                target = (ROOT / parsed.path.lstrip('/')).resolve()
                if not target.is_relative_to(ROOT.resolve()):
                    self.send_error(403)
                    return
                if not target.is_file():
                    if parsed.path.startswith('/assets/') or target.suffix:
                        self.send_error(404, 'Static file not found. Check that frontend/dist was completely extracted.')
                        return
                    target = ROOT / 'index.html'
                if not target.is_file():
                    self.send_error(503, 'Frontend missing. Extract the complete project ZIP.')
                    return
                content_type = {'.html': 'text/html', '.js': 'text/javascript', '.css': 'text/css', '.svg': 'image/svg+xml', '.json': 'application/json'}.get(target.suffix, 'application/octet-stream')
                self.respond(200, target.read_bytes(), content_type)
                return
            try:
                size = int(self.headers.get('content-length', '0'))
                if size < 0 or size > 16384:
                    self.respond(413, b'{"error":"Request is too large."}')
                    return
                body = json.loads(self.rfile.read(size) or b'{}')
                if not isinstance(body, dict):
                    raise ValueError()
                status, data = dispatch(bank, self.command, parsed.path, {k.lower(): v for k, v in self.headers.items()}, body, {k: v[0] for k, v in parse_qs(parsed.query).items()})
                self.respond(status, json.dumps(data).encode())
            except (ValueError, TypeError):
                self.respond(400, b'{"error":"Invalid request."}')
            except Exception:
                import traceback
                traceback.print_exc()
                self.respond(500, b'{"error":"Server error."}')

        def respond(self, status, data, content_type='application/json'):
            self.send_response(status)
            self.send_header('Content-Type', content_type)
            self.send_header('Content-Length', str(len(data)))
            self.send_header('Cache-Control', 'no-store')
            self.send_header('X-Content-Type-Options', 'nosniff')
            self.end_headers()
            self.wfile.write(data)

        do_GET = run_request
        do_POST = run_request
        do_PATCH = run_request
        do_DELETE = run_request

    try:
        server = ThreadingHTTPServer(('127.0.0.1', args.port), Handler)
    except OSError as error:
        raise SystemExit(f'Cannot start on port {args.port}. Stop the previous server with Ctrl+C or use --port 8001. Details: {error}')
    print(f'Serving frontend: {ROOT}', flush=True)
    print(f'NovaBank ready: http://localhost:{args.port}', flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == '__main__':
    main()
