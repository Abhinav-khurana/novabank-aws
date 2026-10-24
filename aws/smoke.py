import getpass
import json
from pathlib import Path
from urllib.request import Request, urlopen

state = json.loads((Path(__file__).resolve().parents[1] / 'deployment.json').read_text())
endpoint = state['outputs']['ApiEndpoint']


def api(path, method='GET', body=None, token=None):
    request = Request(endpoint + '/api' + path, method=method, headers={'Content-Type': 'application/json', **({'Authorization': 'Bearer ' + token} if token else {})}, data=json.dumps(body).encode() if body else None)
    with urlopen(request, timeout=30) as response:
        return json.load(response)


assert api('/health')['status'] == 'ok'
email = input('Demo account email: ').strip()
password = getpass.getpass('Demo password: ')
session = api('/login', 'POST', {'email': email, 'password': password})
me = api('/me', token=session['token'])
assert me['user']['email'] == email.lower()
api('/logout', 'POST', {}, session['token'])
print('PASS: AWS API, DynamoDB authentication, account lookup, and logout.')
print('Next verify a transfer and freeze/unfreeze in the website. Cloud deployment is not fully verified until these pass.')
