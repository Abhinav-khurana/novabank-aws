import importlib.util
import os
import sys
import unittest
import uuid
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', 'backend'))

HAS_EMULATOR = bool(importlib.util.find_spec('moto') and importlib.util.find_spec('boto3'))


@unittest.skipUnless(HAS_EMULATOR, 'Install boto3 and moto[dynamodb] to run DynamoDB emulator tests.')
class DynamoTests(unittest.TestCase):
    def setUp(self):
        import boto3
        from moto import mock_aws
        self.mock = mock_aws()
        self.mock.start()
        self.old_region = os.environ.get('AWS_DEFAULT_REGION')
        os.environ['AWS_DEFAULT_REGION'] = 'ap-south-1'
        boto3.client('dynamodb').create_table(TableName='bank-test', BillingMode='PAY_PER_REQUEST', AttributeDefinitions=[{'AttributeName': k, 'AttributeType': 'S'} for k in ('pk','sk')], KeySchema=[{'AttributeName': 'pk', 'KeyType': 'HASH'}, {'AttributeName': 'sk', 'KeyType': 'RANGE'}])
        from storage import DynamoStore
        from app import Bank
        self.bank = Bank(DynamoStore('bank-test'))

    def tearDown(self):
        self.mock.stop()
        if self.old_region is None:
            os.environ.pop('AWS_DEFAULT_REGION', None)
        else:
            os.environ['AWS_DEFAULT_REGION'] = self.old_region

    def test_transaction_idempotency_and_persistence(self):
        from app import dispatch
        users = self.bank.seed('CloudPassword123!')
        a, b = [u for u in users if u['role'] == 'customer']
        token = self.bank.login({'email': a['email'], 'password': 'CloudPassword123!'})['token']
        headers = {'authorization': 'Bearer ' + token}
        body = {'amount': '25.50', 'toAccount': b['accountId'], 'requestId': str(uuid.uuid4())}
        first = dispatch(self.bank, 'POST', '/api/transfers', headers, body)
        second = dispatch(self.bank, 'POST', '/api/transfers', headers, body)
        self.assertEqual(first[0], 200)
        self.assertEqual(first, second)
        self.assertEqual(self.bank.store.get('ACCOUNT', a['accountId'])[0]['balance'], 2497450)
        self.assertEqual(self.bank.store.get('ACCOUNT', b['accountId'])[0]['balance'], 2502550)
        self.assertEqual(len(self.bank.store.query('LEDGER#' + b['accountId'])[0]), 2)

    def test_optimistic_conflict_rolls_back_all_changes(self):
        from storage import Conflict
        self.bank.store.commit([('X', 'a', {'value': 1}, None)])
        with self.assertRaises(Conflict):
            self.bank.store.commit([('X', 'a', {'value': 2}, 999), ('X', 'b', {'value': 3}, None)])
        self.assertIsNone(self.bank.store.get('X', 'b')[0])
        self.assertEqual(self.bank.store.get('X', 'a')[0]['value'], 1)

    def test_paginated_query_and_expiry_attribute(self):
        self.bank.store.commit([('TEST', str(i), {'value': i, 'expires': 2000000000}, None) for i in range(5)])
        first, cursor = self.bank.store.query('TEST', limit=2)
        second, _ = self.bank.store.query('TEST', cursor, limit=2)
        self.assertEqual([i['value'] for i in first + second], [0, 1, 2, 3])
        item = self.bank.store.client.get_item(TableName='bank-test', Key={'pk': {'S': 'TEST'}, 'sk': {'S': '0'}})['Item']
        self.assertEqual(item['expires']['N'], '2000000000')
