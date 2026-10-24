import base64
import json
import logging
from app import Bank, dispatch
from storage import make_store

bank = None


def handler(event, context):
    global bank
    bank = bank or Bank(make_store())
    # Bootstrap is only available through authenticated IAM Lambda invocation.
    # HTTP requests always carry requestContext and cannot enter this branch.
    if 'requestContext' not in event:
        if event.get('action') == 'seed' and isinstance(event.get('password'), str):
            return {'created': bank.seed(event['password'])}
        raise ValueError('Unsupported direct invocation')
    try:
        raw = event.get('body') or '{}'
        if event.get('isBase64Encoded'):
            raw = base64.b64decode(raw).decode()
        if len(raw) > 16384:
            status, payload = 413, {'error': 'Request is too large.'}
        else:
            body = json.loads(raw)
            if not isinstance(body, dict):
                raise ValueError()
            status, payload = dispatch(bank, event['requestContext']['http']['method'], event['rawPath'], {k.lower(): v for k, v in event.get('headers', {}).items()}, body, event.get('queryStringParameters') or {})
    except (ValueError, TypeError):
        status, payload = 400, {'error': 'Invalid JSON request.'}
    except Exception:
        logging.exception('Request failed; request_id=%s', context.aws_request_id if context else 'local')
        status, payload = 500, {'error': 'Server error. Retry shortly.'}
    return {'statusCode': status, 'headers': {'content-type': 'application/json', 'cache-control': 'no-store', 'x-content-type-options': 'nosniff'}, 'body': json.dumps(payload)}
