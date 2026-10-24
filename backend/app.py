import csv
import hashlib
import hmac
import io
import json
import re
import secrets
import time
import uuid
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from storage import Conflict


class ApiError(Exception):
    def __init__(self, status, message):
        self.status, self.message = status, message


def now():
    return datetime.now(timezone.utc).isoformat()


def password_hash(password, salt=None):
    salt = salt or secrets.token_hex(16)
    return salt + ':' + hashlib.pbkdf2_hmac('sha256', password.encode(), salt.encode(), 310000).hex()


def money(value):
    try:
        if not isinstance(value, str) or not re.fullmatch(r'\d{1,9}(\.\d{1,2})?', value):
            raise ValueError()
        amount = Decimal(value) * 100
        if amount <= 0 or amount > 100000000:
            raise ValueError()
        return int(amount)
    except (InvalidOperation, ValueError):
        raise ApiError(400, 'Enter an amount from ₹0.01 to ₹10,00,000 with at most two decimal places.')


def required(body, key, maximum=150):
    value = body.get(key)
    if not isinstance(value, str) or not value.strip() or len(value) > maximum:
        raise ApiError(400, f'Provide a valid {key}.')
    return value.strip()


class Bank:
    def __init__(self, store):
        self.store = store

    def user_view(self, user):
        return {k: v for k, v in user.items() if k != 'password'}

    def create_user(self, name, email, password, role='customer'):
        if not re.fullmatch(r'[^\s@]+@[^\s@]+\.[^\s@]+', email) or len(email) > 150:
            raise ApiError(400, 'Enter a valid email address.')
        if len(password) < 10 or len(password) > 128:
            raise ApiError(400, 'Use a password containing 10 to 128 characters.')
        uid = uuid.uuid4().hex
        account_id = '91' + ''.join(secrets.choice('0123456789') for _ in range(10))
        user = dict(id=uid, name=name, email=email.lower(), password=password_hash(password), role=role, accountId=account_id, created=now())
        account = dict(id=account_id, userId=uid, name=name, balance=0, status='active', created=now())
        self.store.commit([('EMAIL', email.lower(), {'userId': uid}, None), ('USER', uid, user, None), ('ACCOUNT', account_id, account, None)])
        return user

    def seed(self, password):
        created = []
        for name, email, role in [('Bank Admin', 'admin@novabank.demo', 'admin'), ('Aarav Sharma', 'aarav@novabank.demo', 'customer'), ('Meera Patel', 'meera@novabank.demo', 'customer')]:
            existing, _ = self.store.get('EMAIL', email)
            if existing:
                continue
            user = self.create_user(name, email, password, role)
            created.append(self.user_view(user))
            if role == 'customer':
                self.move(user, {'accountId': user['accountId'], 'amount': '25000', 'kind': 'deposit', 'note': 'Opening demo deposit', 'requestId': str(uuid.uuid4())}, admin=True)
        return created

    def authenticate(self, headers):
        auth = headers.get('authorization', '')
        if not auth.startswith('Bearer '):
            raise ApiError(401, 'Please sign in.')
        key = hashlib.sha256(auth[7:].encode()).hexdigest()
        session, version = self.store.get('SESSION', key)
        if not session or session.get('revoked') or session['expires'] <= int(time.time()):
            raise ApiError(401, 'Your session expired. Please sign in again.')
        user, _ = self.store.get('USER', session['userId'])
        if not user:
            raise ApiError(401, 'Please sign in.')
        return user, key, session, version

    def login(self, body):
        email = required(body, 'email').lower()
        password = required(body, 'password', 128)
        window = int(time.time()) // 900
        rate_key = f'{email}:{window}'
        for _ in range(5):
            rate, version = self.store.get('LOGIN', rate_key)
            rate = rate or {'count': 0, 'expires': (window + 2) * 900}
            if rate['count'] >= 10:
                raise ApiError(429, 'Too many sign in attempts. Try again in 15 minutes.')
            rate['count'] += 1
            try:
                self.store.commit([('LOGIN', rate_key, rate, version)])
                break
            except Conflict:
                continue
        else:
            raise ApiError(429, 'Please try again shortly.')
        pointer, _ = self.store.get('EMAIL', email)
        user = self.store.get('USER', pointer['userId'])[0] if pointer else None
        stored = user['password'] if user else password_hash('dummy-password', '0' * 32)
        valid = hmac.compare_digest(stored, password_hash(password, stored.split(':')[0]))
        if not user or not valid:
            raise ApiError(401, 'Email or password is incorrect.')
        token = secrets.token_urlsafe(32)
        self.store.commit([('SESSION', hashlib.sha256(token.encode()).hexdigest(), {'userId': user['id'], 'expires': int(time.time()) + 7200}, None)])
        return {'token': token, 'user': self.user_view(user)}

    def move(self, user, body, admin=False):
        amount = money(body.get('amount'))
        request_id = required(body, 'requestId', 80)
        if not re.fullmatch(r'[a-zA-Z0-9-]{8,80}', request_id):
            raise ApiError(400, 'Invalid request ID.')
        kind = body.get('kind', 'transfer') if admin else 'transfer'
        if kind not in ('transfer', 'deposit', 'withdrawal') or (admin and kind == 'transfer'):
            raise ApiError(400, 'Invalid transaction type.')
        source = required(body, 'accountId') if admin else user['accountId']
        target = required(body, 'toAccount') if kind == 'transfer' else None
        if source == target:
            raise ApiError(400, 'Choose another account to transfer to.')
        note = body.get('note', '')
        if not isinstance(note, str) or len(note) > 140:
            raise ApiError(400, 'Notes must be at most 140 characters.')
        operation = dict(kind=kind, source=source, target=target, amount=amount, note=note)
        key = user['id'] + ':' + request_id
        for _ in range(8):
            previous, _ = self.store.get('REQUEST', key)
            if previous:
                if previous['operation'] != operation:
                    raise ApiError(409, 'This request ID was already used for a different transaction.')
                return previous['transaction']
            a, av = self.store.get('ACCOUNT', source)
            b, bv = self.store.get('ACCOUNT', target) if target else (None, None)
            if not a or (target and not b):
                raise ApiError(404, 'Account not found.')
            if a['status'] != 'active' or (b and b['status'] != 'active'):
                raise ApiError(409, 'Transactions are unavailable for frozen accounts.')
            if kind != 'deposit' and a['balance'] < amount:
                raise ApiError(400, 'Insufficient balance.')
            a['balance'] += amount if kind == 'deposit' else -amount
            if b:
                b['balance'] += amount
            timestamp = now()
            tx = dict(id=uuid.uuid4().hex, kind=kind, source=source, target=target, amount=amount, note=note, created=timestamp, actor=user['id'])
            sort_key = timestamp + '#' + tx['id']
            entry = dict(tx, direction='credit' if kind == 'deposit' else 'debit', balanceAfter=a['balance'], counterparty=b['name'] if b else 'Demo bank counter')
            audit = dict(id=tx['id'], actor=user['email'], action=kind, details=f'{source}' + (f' → {target}' if target else ''), created=timestamp)
            changes = [('ACCOUNT', source, a, av), ('TRANSACTION', sort_key, tx, None), ('LEDGER#' + source, sort_key, entry, None), ('REQUEST', key, {'operation': operation, 'transaction': tx}, None), ('AUDIT', sort_key, audit, None)]
            if b:
                changes.extend([('ACCOUNT', target, b, bv), ('LEDGER#' + target, sort_key, dict(tx, direction='credit', balanceAfter=b['balance'], counterparty=a['name']), None)])
            try:
                self.store.commit(changes)
                return tx
            except Conflict:
                continue
        raise ApiError(409, 'Accounts are busy. Retry the same transaction.')

    def handle(self, method, path, headers, body, query):
        if method == 'GET' and path == '/api/health':
            return {'status': 'ok', 'application': 'NovaBank', 'demo': True}
        if method == 'POST' and path == '/api/register':
            user = self.create_user(required(body, 'name', 80), required(body, 'email').lower(), required(body, 'password', 128))
            return {'user': self.user_view(user)}
        if method == 'POST' and path == '/api/login':
            return self.login(body)
        user, session_key, session, session_version = self.authenticate(headers)
        if method == 'POST' and path == '/api/logout':
            session['revoked'] = True
            self.store.commit([('SESSION', session_key, session, session_version)])
            return {'ok': True}
        if method == 'GET' and path == '/api/me':
            return {'user': self.user_view(user), 'account': self.store.get('ACCOUNT', user['accountId'])[0]}
        if method == 'POST' and path == '/api/transfers':
            return {'transaction': self.move(user, body)}
        if path == '/api/beneficiaries':
            partition = 'BENEFICIARY#' + user['id']
            if method == 'GET':
                rows, cursor = self.store.query(partition, query.get('cursor', ''))
                return {'items': [r for r in rows if not r.get('deleted')], 'cursor': cursor}
            if method == 'POST':
                aid = required(body, 'accountId')
                account, _ = self.store.get('ACCOUNT', aid)
                if not account or aid == user['accountId']:
                    raise ApiError(400, 'Enter another existing account number.')
                old, version = self.store.get(partition, aid)
                record = dict(accountId=aid, name=account['name'], nickname=required(body, 'nickname', 60), deleted=False)
                self.store.commit([(partition, aid, record, version)])
                return record
        if method == 'DELETE' and path.startswith('/api/beneficiaries/'):
            aid = path.rsplit('/', 1)[-1]
            partition = 'BENEFICIARY#' + user['id']
            item, version = self.store.get(partition, aid)
            if not item:
                raise ApiError(404, 'Beneficiary not found.')
            item['deleted'] = True
            self.store.commit([(partition, aid, item, version)])
            return {'ok': True}
        if method == 'GET' and path in ('/api/transactions', '/api/statement'):
            if path == '/api/statement':
                rows, cursor = [], ''
                while True:
                    page, cursor = self.store.query('LEDGER#' + user['accountId'], cursor)
                    rows.extend(page)
                    if not cursor:
                        break
                    if len(rows) >= 5000:
                        raise ApiError(400, 'Statement is too large for this demo. Use transaction pages.')
                return {'items': self.filter_rows(rows, query), 'accountId': user['accountId']}
            rows, cursor = self.store.query('LEDGER#' + user['accountId'], query.get('cursor', ''))
            return {'items': self.filter_rows(rows, query), 'cursor': cursor}
        if path.startswith('/api/admin/'):
            if user['role'] != 'admin':
                raise ApiError(403, 'Administrator access is required.')
            collections = {'/api/admin/accounts': 'ACCOUNT', '/api/admin/transactions': 'TRANSACTION', '/api/admin/audit': 'AUDIT'}
            if method == 'GET' and path in collections:
                rows, cursor = self.store.query(collections[path], query.get('cursor', ''))
                return {'items': rows, 'cursor': cursor}
            if method == 'POST' and path == '/api/admin/cash':
                return {'transaction': self.move(user, body, admin=True)}
            if method == 'PATCH' and path.startswith('/api/admin/accounts/'):
                aid = path.rsplit('/', 1)[-1]
                account, version = self.store.get('ACCOUNT', aid)
                if not account:
                    raise ApiError(404, 'Account not found.')
                if body.get('status') not in ('active', 'frozen'):
                    raise ApiError(400, 'Invalid account status.')
                account['status'] = body['status']
                stamp = now()
                audit = dict(id=uuid.uuid4().hex, actor=user['email'], action=account['status'], details=aid, created=stamp)
                self.store.commit([('ACCOUNT', aid, account, version), ('AUDIT', stamp + '#' + audit['id'], audit, None)])
                return {'account': account}
        raise ApiError(404, 'Endpoint not found.')

    def filter_rows(self, rows, query):
        start, end = query.get('from', ''), query.get('to', '')
        for value in (start, end):
            if value:
                try:
                    datetime.strptime(value, '%Y-%m-%d')
                except ValueError:
                    raise ApiError(400, 'Use dates in YYYY-MM-DD format.')
        if start and end and start > end:
            raise ApiError(400, 'The start date must precede the end date.')
        return [r for r in rows if (not start or r['created'][:10] >= start) and (not end or r['created'][:10] <= end) and (not query.get('direction') or r['direction'] == query['direction'])]


def dispatch(bank, method, path, headers, body=None, query=None):
    try:
        result = bank.handle(method, path, headers, body or {}, query or {})
        return 200, result
    except ApiError as e:
        return e.status, {'error': e.message}
    except Conflict:
        return 409, {'error': 'Record changed or email already exists. Refresh and try again.'}
