import concurrent.futures
import os
import sys
import tempfile
import unittest
import uuid
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))
from app import Bank, dispatch, money
from storage import SQLiteStore


class BankingTests(unittest.TestCase):
    def setUp(self):
        self.folder = tempfile.TemporaryDirectory()
        self.bank = Bank(SQLiteStore(os.path.join(self.folder.name, 'test.db')))
        self.admin = self.bank.create_user('Admin', 'admin@example.com', 'Password123!', 'admin')
        self.a = self.bank.create_user('Alice', 'alice@example.com', 'Password123!')
        self.b = self.bank.create_user('Bob', 'bob@example.com', 'Password123!')
        self.bank.move(self.admin, {'accountId': self.a['accountId'], 'amount': '1000', 'kind': 'deposit', 'requestId': str(uuid.uuid4())}, admin=True)
        token = self.bank.login({'email': 'alice@example.com', 'password': 'Password123!'})['token']
        self.headers = {'authorization': 'Bearer ' + token}

    def tearDown(self):
        self.folder.cleanup()

    def transfer(self, amount='100', request_id=None):
        return dispatch(self.bank, 'POST', '/api/transfers', self.headers, {'toAccount': self.b['accountId'], 'amount': amount, 'requestId': request_id or str(uuid.uuid4())})

    def balance(self, user):
        return self.bank.store.get('ACCOUNT', user['accountId'])[0]['balance']

    def test_transfer_balances_and_ledger(self):
        status, _ = self.transfer('123.45')
        self.assertEqual(status, 200)
        self.assertEqual(self.balance(self.a), 87655)
        self.assertEqual(self.balance(self.b), 12345)
        rows, _ = self.bank.store.query('LEDGER#' + self.b['accountId'])
        self.assertEqual(rows[0]['balanceAfter'], 12345)
        self.assertEqual(rows[0]['direction'], 'credit')

    def test_insufficient_balance_is_atomic(self):
        self.assertEqual(self.transfer('1000.01')[0], 400)
        self.assertEqual(self.balance(self.a), 100000)
        self.assertEqual(self.balance(self.b), 0)

    def test_duplicate_request_is_not_replayed(self):
        key = str(uuid.uuid4())
        first = self.transfer('100', key)
        second = self.transfer('100', key)
        self.assertEqual(first, second)
        self.assertEqual(self.balance(self.a), 90000)

    def test_duplicate_key_with_changed_amount_rejected(self):
        key = str(uuid.uuid4())
        self.transfer('100', key)
        self.assertEqual(self.transfer('200', key)[0], 409)

    def test_concurrent_duplicates_only_move_once(self):
        key = str(uuid.uuid4())
        with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
            results = list(pool.map(lambda _: self.transfer('100', key)[0], range(6)))
        self.assertTrue(all(s == 200 for s in results))
        self.assertEqual(self.balance(self.b), 10000)

    def test_concurrent_spending_cannot_overdraw(self):
        with concurrent.futures.ThreadPoolExecutor(max_workers=4) as pool:
            results = list(pool.map(lambda _: self.transfer('400')[0], range(4)))
        self.assertEqual(results.count(200), 2)
        self.assertEqual(self.balance(self.a) + self.balance(self.b), 100000)
        self.assertGreaterEqual(self.balance(self.a), 0)

    def test_frozen_recipient_cannot_receive(self):
        account, version = self.bank.store.get('ACCOUNT', self.b['accountId'])
        account['status'] = 'frozen'
        self.bank.store.commit([('ACCOUNT', account['id'], account, version)])
        self.assertEqual(self.transfer()[0], 409)
        self.assertEqual(self.balance(self.a), 100000)

    def test_customer_cannot_use_admin_routes(self):
        self.assertEqual(dispatch(self.bank, 'GET', '/api/admin/accounts', self.headers)[0], 403)
        self.assertEqual(dispatch(self.bank, 'POST', '/api/admin/cash', self.headers, {})[0], 403)

    def test_logout_revokes_session(self):
        self.assertEqual(dispatch(self.bank, 'POST', '/api/logout', self.headers)[0], 200)
        self.assertEqual(dispatch(self.bank, 'GET', '/api/me', self.headers)[0], 401)

    def test_invalid_password_rejected(self):
        self.assertEqual(dispatch(self.bank, 'POST', '/api/login', {}, {'email': 'alice@example.com', 'password': 'wrong'})[0], 401)

    def test_registration_cannot_escalate_role(self):
        status, result = dispatch(self.bank, 'POST', '/api/register', {}, {'name': 'Eve', 'email': 'eve@example.com', 'password': 'Password123!', 'role': 'admin'})
        self.assertEqual(status, 200)
        self.assertEqual(result['user']['role'], 'customer')
        self.assertNotIn('password', result['user'])

    def test_duplicate_email_rejected(self):
        self.assertEqual(dispatch(self.bank, 'POST', '/api/register', {}, {'name': 'Alice2', 'email': 'ALICE@example.com', 'password': 'Password123!'})[0], 409)

    def test_missing_account_and_self_transfer(self):
        body = {'toAccount': self.a['accountId'], 'amount': '10', 'requestId': str(uuid.uuid4())}
        self.assertEqual(dispatch(self.bank, 'POST', '/api/transfers', self.headers, body)[0], 400)
        body['toAccount'] = '000000000000'
        self.assertEqual(dispatch(self.bank, 'POST', '/api/transfers', self.headers, body)[0], 404)

    def test_money_rejects_invalid_inputs(self):
        for value in ['0', '-1', 'NaN', 'Infinity', '1.001', '1e2', '1000000.01', 100, True, None]:
            with self.subTest(value=value):
                with self.assertRaises(Exception):
                    money(value)
        self.assertEqual(money('0.01'), 1)
        self.assertEqual(money('1000000'), 100000000)

    def test_beneficiary_and_statement_isolation(self):
        result = dispatch(self.bank, 'POST', '/api/beneficiaries', self.headers, {'accountId': self.b['accountId'], 'nickname': 'Bob'})
        self.assertEqual(result[0], 200)
        self.assertEqual(dispatch(self.bank, 'GET', '/api/beneficiaries', self.headers)[1]['items'][0]['nickname'], 'Bob')
        self.assertEqual(len(dispatch(self.bank, 'GET', '/api/statement', self.headers)[1]['items']), 1)

    def test_session_expiry(self):
        user, key, session, version = self.bank.authenticate(self.headers)
        session['expires'] = 1
        self.bank.store.commit([('SESSION', key, session, version)])
        self.assertEqual(dispatch(self.bank, 'GET', '/api/me', self.headers)[0], 401)

    def test_login_rate_limit(self):
        for _ in range(9):
            dispatch(self.bank, 'POST', '/api/login', {}, {'email': 'alice@example.com', 'password': 'bad'})
        self.assertEqual(dispatch(self.bank, 'POST', '/api/login', {}, {'email': 'alice@example.com', 'password': 'Password123!'})[0], 429)

    def test_admin_withdrawal_and_audit(self):
        self.bank.move(self.admin, {'accountId': self.a['accountId'], 'amount': '50', 'kind': 'withdrawal', 'requestId': str(uuid.uuid4())}, admin=True)
        self.assertEqual(self.balance(self.a), 95000)
        self.assertEqual(len(self.bank.store.query('AUDIT')[0]), 2)


if __name__ == '__main__':
    unittest.main()
