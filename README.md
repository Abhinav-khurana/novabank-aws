# NovaBank: Cloud Banking System on AWS

A full stack academic banking simulator with customer and administrator interfaces. Currency is INR; all money is simulated. This is a teaching application, not a financial service.

Start with `START_HERE.txt`. The complete ZIP includes the compiled frontend; npm is not required for local operation.

## Start here on Windows

1. Extract the ZIP completely.
2. Install Python 3.10 or newer if you do not already have it. In the Windows installer, enable **Add Python to PATH**.
3. Open the extracted `banking-system` folder and double click `start-windows.bat`.
4. Leave that terminal open. Open **http://localhost:8000** in your browser.
5. Click **Aarav**, **Meera**, or **Admin**, then **Sign in**.

Local demo password for all three accounts: `DemoBank2026!`

| Role | Email |
| --- | --- |
| Customer | aarav@novabank.demo |
| Customer | meera@novabank.demo |
| Administrator | admin@novabank.demo |

Account numbers are generated during seeding. View them in the administrator account table. Each seeded customer starts with ₹25,000. Newly registered accounts start with zero; the administrator can make demo deposits.

If double clicking does not work, open a terminal inside the project folder:

```powershell
python backend/local.py --seed
```

On macOS or Linux:

```bash
bash start.sh
```

No pip or npm packages are needed to run the included local build. Data is stored in `banking.db` in the project folder. Stop the server with Ctrl+C. To reset the local demo, stop the server, delete only that database, and start again with `--seed`.

## Features

* Customer registration and login; passwords stored as salted PBKDF2 hashes.
* Two hour revocable sessions; only token hashes are stored in the database.
* Per email login attempt limit of 10 attempts per 15 minute window.
* Balance dashboard, account status, and transaction totals.
* Atomic account transfers with optimistic concurrency checks.
* Duplicate request protection and rejection of changed duplicate requests.
* Beneficiary creation, updates, and removal.
* History filters and CSV statements with date and direction filters.
* Admin account status controls and demo cash deposits and withdrawals.
* Transaction register and audit trail.
* Responsive React interface with built frontend assets included.

## Architecture

The deployed application serves the React interface and Python API through one API Gateway HTTPS endpoint backed by Lambda. DynamoDB persists cloud data. CloudFormation provisions resources; IAM grants access and CloudWatch records logs. S3 stores the deployment archive. CloudFront is not used.

Locally, the Python server serves the included frontend build and uses SQLite.

## AWS deployment

Run `python aws/package.py` to generate `backend-api.zip` from the included frontend build and Python source.

Follow docs/AWS_SETUP.md and use aws/template-api.yaml. The Lambda entry point is web_handler.handler. Package backend/app.py, backend/storage.py, backend/lambda_handler.py and aws/web_handler.py at the archive root; copy frontend/dist into a web folder in that archive. Upload the archive to your private artifact bucket. Choose your own private seed password in Lambda; the local demo password is not the deployed password.

This academic deployment uses the account Free plan credits and allowances; usage is not guaranteed to remain free.

## Source development

The delivered frontend is already compiled. To edit it, use Node.js 22.12 or newer:

```bash
cd frontend
npm ci
npm run build
cd ..
python backend/local.py --seed
```

Rebuild after editing React or CSS. `npm run dev` is only a frontend development server; it needs separate API configuration. The simplest complete development loop is rebuild, then use the Python server on port 8000.

## Tests

```bash
python -m unittest discover -s tests -v
```

The main suite requires no external packages. To test the AWS DynamoDB adapter against a local AWS emulator:

```bash
python -m pip install boto3 "moto[dynamodb]"
python -m unittest discover -s tests -v
```

Emulator tests skip when those optional packages are absent. AWS deployment must still be verified in your own account using `python3 aws/smoke.py` and the browser demo checklist.

## Repository layout

```text
backend/              API, banking logic, SQLite and DynamoDB adapters
frontend/src/         React source and CSS
frontend/dist/        Ready to run compiled interface
aws/                  CloudFormation template, Lambda web handler and API smoke check
tests/                Banking and adapter verification
docs/                 AWS guide, demonstration, case study draft
start-windows.bat     Windows local launcher
start.sh              macOS and Linux local launcher
```

## Scope and limitations

This is a deliberately small academic application. It has no real bank integration, KYC, card processing, email verification, password recovery, regulatory controls, fraud system, or formal general ledger. Cash operations are explicitly simulated. The ledger is an application audit record, not an independently tamper resistant accounting system. Application users cannot edit it; the AWS account owner retains infrastructure access.

The session token is held in browser session storage. HTTPS is provided on AWS; local use is restricted to the loopback interface. Production banking would require a separate security design and independent review. Login limits are per email and do not constitute full abuse protection. AWS API throttling reduces traffic bursts but is not a spending cap.

The UI loads up to 5,000 records per collection for this demo. API collection endpoints support pagination; CSV export is capped at 5,000 ledger entries. Monetary values are positive integer paise in storage; floats are not used for balance updates. Transfer and cash operation limits are ₹10,00,000 per operation.

## Submission

Use **docs/DEMO_AND_SCREENSHOTS.md** for the evidence sequence. **docs/CASE_STUDY.md** is a draft matching the supplied five section template. Complete student details and the GitHub URL, deploy and capture actual AWS evidence, then finalize the report. Included application screenshots are from the tested local build and must not be described as AWS deployment proof.

Do not commit `banking.db`, `deployment.json`, `demo-credentials.txt`, AWS keys, or personal console screenshots. `.gitignore` excludes private runtime files. Fill the student details in the case study before publishing the repository.
