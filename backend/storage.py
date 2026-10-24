import json
import os
import sqlite3


class Conflict(Exception):
    pass


class SQLiteStore:
    def __init__(self, path):
        self.path = path
        with self.connect() as db:
            db.execute('CREATE TABLE IF NOT EXISTS records (pk TEXT, sk TEXT, data TEXT, version INTEGER, PRIMARY KEY(pk, sk))')

    def connect(self):
        db = sqlite3.connect(self.path, timeout=15)
        db.execute('PRAGMA busy_timeout=15000')
        return db

    def get(self, pk, sk):
        with self.connect() as db:
            row = db.execute('SELECT data,version FROM records WHERE pk=? AND sk=?', (pk, sk)).fetchone()
        return (json.loads(row[0]), row[1]) if row else (None, None)

    def query(self, pk, cursor='', limit=100):
        with self.connect() as db:
            rows = db.execute('SELECT sk,data FROM records WHERE pk=? AND sk>? ORDER BY sk LIMIT ?', (pk, cursor, limit + 1)).fetchall()
        return [json.loads(r[1]) for r in rows[:limit]], rows[limit - 1][0] if len(rows) > limit else None

    def commit(self, changes):
        with self.connect() as db:
            db.execute('BEGIN IMMEDIATE')
            for pk, sk, data, expected in changes:
                row = db.execute('SELECT version FROM records WHERE pk=? AND sk=?', (pk, sk)).fetchone()
                if (row[0] if row else None) != expected:
                    raise Conflict()
                db.execute('INSERT OR REPLACE INTO records VALUES (?,?,?,?)', (pk, sk, json.dumps(data), (expected or 0) + 1))


class DynamoStore:
    def __init__(self, table):
        import boto3
        self.client = boto3.client('dynamodb')
        self.table = table

    def get(self, pk, sk):
        item = self.client.get_item(TableName=self.table, Key={'pk': {'S': pk}, 'sk': {'S': sk}}, ConsistentRead=True).get('Item')
        return (json.loads(item['data']['S']), int(item['version']['N'])) if item else (None, None)

    def query(self, pk, cursor='', limit=100):
        args = dict(TableName=self.table, KeyConditionExpression='pk = :pk', ExpressionAttributeValues={':pk': {'S': pk}}, Limit=limit, ConsistentRead=True)
        if cursor:
            args['ExclusiveStartKey'] = {'pk': {'S': pk}, 'sk': {'S': cursor}}
        result = self.client.query(**args)
        return [json.loads(i['data']['S']) for i in result['Items']], result.get('LastEvaluatedKey', {}).get('sk', {}).get('S')

    def commit(self, changes):
        writes = []
        for pk, sk, data, expected in changes:
            item = {'pk': {'S': pk}, 'sk': {'S': sk}, 'data': {'S': json.dumps(data)}, 'version': {'N': str((expected or 0) + 1)}}
            if 'expires' in data:
                item['expires'] = {'N': str(data['expires'])}
            put = dict(TableName=self.table, Item=item)
            if expected is None:
                put['ConditionExpression'] = 'attribute_not_exists(pk)'
            else:
                put.update(ConditionExpression='#v = :v', ExpressionAttributeNames={'#v': 'version'}, ExpressionAttributeValues={':v': {'N': str(expected)}})
            writes.append({'Put': put})
        try:
            self.client.transact_write_items(TransactItems=writes)
        except self.client.exceptions.TransactionCanceledException as e:
            reasons = e.response.get('CancellationReasons', [])
            if any(r.get('Code') in ('ConditionalCheckFailed', 'TransactionConflict') for r in reasons):
                raise Conflict() from e
            raise


def make_store():
    return DynamoStore(os.environ['TABLE_NAME']) if os.environ.get('TABLE_NAME') else SQLiteStore(os.environ.get('DB_PATH', 'banking.db'))
