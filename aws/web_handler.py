from pathlib import Path
from urllib.parse import unquote
from lambda_handler import handler as banking_handler

ROOT = Path(__file__).resolve().parent / 'web'
HEADERS = {
    'cache-control': 'no-store',
    'x-content-type-options': 'nosniff',
    'x-frame-options': 'DENY',
    'referrer-policy': 'strict-origin-when-cross-origin',
    'strict-transport-security': 'max-age=31536000',
}


def handler(event, context):
    if 'requestContext' not in event:
        return banking_handler(event, context)
    path = unquote(event.get('rawPath', '/'))
    if path.startswith('/api/'):
        return banking_handler(event, context)
    method = event['requestContext']['http']['method']
    if method not in ('GET', 'HEAD'):
        return {'statusCode': 405, 'headers': {**HEADERS, 'content-type': 'text/plain', 'allow': 'GET, HEAD'}, 'body': 'Method not allowed'}
    target = (ROOT / ('index.html' if path == '/' else path.lstrip('/'))).resolve()
    if not target.is_relative_to(ROOT.resolve()) or not target.is_file():
        return {'statusCode': 404, 'headers': {**HEADERS, 'content-type': 'text/plain'}, 'body': 'File not found'}
    content_type = {'.html': 'text/html; charset=utf-8', '.js': 'text/javascript; charset=utf-8', '.css': 'text/css; charset=utf-8', '.json': 'application/json', '.svg': 'image/svg+xml'}.get(target.suffix)
    if not content_type:
        return {'statusCode': 404, 'headers': {**HEADERS, 'content-type': 'text/plain'}, 'body': 'File not found'}
    return {'statusCode': 200, 'headers': {**HEADERS, 'content-type': content_type}, 'body': target.read_text(encoding='utf-8') if method == 'GET' else ''}
