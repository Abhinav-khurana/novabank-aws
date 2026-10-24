# Demo and screenshots

Run the same sequence locally first, then repeat on the AWS website. Local screenshots prove application functionality; AWS console screenshots and the live URL establish deployment.

## Demonstration sequence

1. Sign in as admin. Open Administration and note Aarav and Meera's generated account numbers and balances.
2. Make a ₹500 demo deposit to Aarav. Show the changed balance and audit trail.
3. Sign out and sign in as Aarav. Add Meera as a beneficiary.
4. Transfer ₹1,000 to Meera with note `Project demonstration`.
5. Show Aarav's reduced balance, completed transaction, and reference number.
6. Sign in as Meera. Show the matching credit and increased balance. The two transfer references must match.
7. Sign in as Aarav and attempt more than the available balance. Show the insufficient balance message and unchanged balance.
8. Export the CSV statement and open it in Excel or another spreadsheet app.
9. Sign in as admin and freeze Meera's account.
10. As Aarav, attempt another transfer to Meera. Show the rejected transfer.
11. As admin, unfreeze Meera. Show the transaction register and audit trail.
12. Register a new customer. Show the zero balance, then fund the account through the admin counter.

## Required screenshots

| File suggestion | Evidence |
| --- | --- |
| 01_login.png | Login page |
| 02_dashboard.png | Customer dashboard with account and balance |
| 03_beneficiary.png | Saved beneficiary |
| 04_transfer.png | Successful transfer and reference |
| 05_recipient.png | Matching recipient credit |
| 06_insufficient.png | Insufficient funds rejection |
| 07_admin.png | Admin account table and counter |
| 08_frozen.png | Frozen account rejection |
| 09_statement.png | Opened CSV statement |
| 10_stack.png | CloudFormation stack CREATE_COMPLETE |
| 11_lambda.png | Deployed backend Lambda |
| 12_dynamodb.png | Accounts or ledger records in DynamoDB |
| 13_cloudformation.png | Completed CloudFormation stack and resources |
| 14_api_logs.png | API route and CloudWatch log group |
| 15_github.png | Repository with student details and README |

Retain screenshots of actual results. Do not claim the cloud is deployed until the AWS deployment and its smoke checks pass.

## Viva essentials

**What makes this full stack?** React is the frontend, Python implements the API and banking rules, and DynamoDB stores persistent data on AWS.

**What happens during a transfer?** The backend validates the session and amount, reads both accounts, checks their status and balance, then commits the two balances, two ledger records, transaction register, duplicate request record, and audit entry together.

**What prevents simultaneous requests from overspending?** Each account record has a version. A transaction only commits if the versions still match what was read. Conflicting requests retry using fresh balances.

**What prevents duplicate transfers?** A unique request ID and operation fingerprint are saved in the same transaction. The same request returns its prior result; a changed operation with the same ID is rejected.

**Why DynamoDB?** It supports managed persistence and transactions without running a database server. Its composite keys separate accounts, sessions, beneficiaries, and ledger records.

**Why Lambda?** It runs the backend when requests arrive; there is no always running app server to manage.

**What does S3 do?** It stores the Lambda deployment archive. API Gateway and Lambda serve the compiled website over HTTPS.

**How are passwords protected?** They are salted and hashed using PBKDF2 with SHA256 and 310,000 iterations. Password hashes are excluded from API responses.

**Is it a real banking platform?** It is an academic simulator with demo funds and simplified accounting. It does not connect to payment networks or process real deposits.
