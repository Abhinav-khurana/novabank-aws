"""Optional browser check: pip install playwright && python -m playwright install chromium."""
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import time
from urllib.request import urlopen
import uuid

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'backend'))
from app import Bank
from storage import SQLiteStore
from playwright.sync_api import sync_playwright


def main():
    screenshots = ROOT / 'docs' / 'local-screenshots'
    screenshots.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory() as folder:
        db = str(Path(folder) / 'browser.db')
        bank = Bank(SQLiteStore(db))
        users = bank.seed('DemoBank2026!')
        admin, a, b = users
        for amount, note in [('1250', 'Shared apartment bills'), ('450', 'Weekend plans'), ('2100', 'Travel contribution')]:
            bank.move(a, {'toAccount': b['accountId'], 'amount': amount, 'note': note, 'requestId': str(uuid.uuid4())})
        process = subprocess.Popen([sys.executable, '-u', str(ROOT / 'backend' / 'local.py'), '--port', '8123'], cwd=ROOT, env={**os.environ, 'DB_PATH': db}, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        try:
            for _ in range(40):
                try:
                    urlopen('http://127.0.0.1:8123/api/health', timeout=1).close()
                    break
                except OSError:
                    time.sleep(.1)
            with sync_playwright() as p:
                browser = p.chromium.launch(headless=True, args=['--no-sandbox'])
                page = browser.new_page(viewport={'width': 1440, 'height': 1040}, device_scale_factor=1)
                errors = []
                page.on('pageerror', lambda e: errors.append(str(e)))
                page.goto('http://127.0.0.1:8123')
                page.get_by_role('heading', name='Good to see you again.').wait_for()
                page.screenshot(path=str(screenshots / '01-login.png'), full_page=True)
                page.get_by_role('button', name='Aarav', exact=True).click()
                page.get_by_role('button', name='Sign in', exact=True).click()
                page.get_by_role('heading', name='Hello, Aarav.').wait_for()
                page.screenshot(path=str(screenshots / '02-dashboard.png'), full_page=True)
                page.get_by_role('button', name='Beneficiaries', exact=True).click()
                page.get_by_label('Account number', exact=True).fill(b['accountId'])
                page.get_by_label('Nickname', exact=True).fill('Meera')
                page.get_by_role('button', name='Save beneficiary').click()
                page.get_by_role('status').filter(has_text='Beneficiary saved.').wait_for()
                page.screenshot(path=str(screenshots / '03-beneficiaries.png'), full_page=True)
                page.get_by_role('button', name='Send', exact=True).click()
                page.get_by_label('Amount in INR', exact=True).fill('1000')
                page.get_by_label('Note').fill('Project demonstration')
                page.get_by_role('button', name='Confirm transfer').click()
                page.get_by_role('status').filter(has_text='Transfer complete.').wait_for()
                page.screenshot(path=str(screenshots / '04-transfer.png'), full_page=True)
                page.get_by_label('Amount in INR', exact=True).fill('999999')
                page.get_by_role('button', name='Confirm transfer').click()
                page.get_by_role('alert').filter(has_text='Insufficient balance.').wait_for()
                page.screenshot(path=str(screenshots / '05-insufficient.png'), full_page=True)
                page.get_by_role('button', name='Transactions', exact=True).click()
                with page.expect_download() as download:
                    page.get_by_role('button', name='Export CSV').click()
                download.value.save_as(str(Path(folder) / 'statement.csv'))
                assert 'Project demonstration' in (Path(folder) / 'statement.csv').read_text()
                page.screenshot(path=str(screenshots / '06-history.png'), full_page=True)
                page.set_viewport_size({'width':390,'height':844})
                page.get_by_role('button', name='Overview', exact=True).click()
                page.screenshot(path=str(screenshots / '07-mobile.png'), full_page=True)
                assert page.evaluate('document.documentElement.scrollWidth <= innerWidth'), 'Mobile page overflow'
                page.set_viewport_size({'width':1440,'height':1040})
                page.get_by_role('button', name='Sign out', exact=True).click()
                page.get_by_role('button', name='Admin', exact=True).click()
                page.get_by_role('button', name='Sign in', exact=True).click()
                page.get_by_role('heading', name='Hello, Bank.').wait_for()
                page.get_by_role('button', name='Administration', exact=True).click()
                page.get_by_role('heading', name='Customer accounts').wait_for()
                row = page.get_by_role('row').filter(has_text=b['accountId']).filter(has_text='Meera Patel').first
                row.get_by_role('button', name='Freeze', exact=True).click()
                page.get_by_role('status').filter(has_text='Account status updated.').wait_for()
                row.get_by_role('button', name='Unfreeze', exact=True).wait_for()
                page.screenshot(path=str(screenshots / '08-administration.png'), full_page=True)
                page.locator('.cash-panel select').first.select_option(a['accountId'])
                page.get_by_label('Amount in INR', exact=True).fill('500')
                page.get_by_role('button', name='Confirm counter transaction').click()
                page.get_by_role('status').filter(has_text='Counter transaction completed.').wait_for()
                assert not errors, errors
                browser.close()
                print('PASS: login, dashboard, beneficiaries, transfer, rejection, CSV export, mobile layout, admin freeze, and counter deposit.')
                print('Local screenshots:', screenshots)
        finally:
            process.terminate()
            process.wait(timeout=5)


if __name__ == '__main__':
    main()
