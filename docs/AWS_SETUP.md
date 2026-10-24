# AWS console deployment

NOVABANK: AWS CONSOLE DEPLOYMENT WITHOUT CLOUDFRONT

The existing React build and Python banking logic are reused. API Gateway
provides one HTTPS URL for the interface and API. DynamoDB stores data.
The existing private S3 bucket stores the Lambda deployment ZIP only.
No CloudShell, CloudFront, Node.js installation, or frontend rebuild is needed.
Resources use your AWS Free account plan credits at applicable usage rates.

1. Leave the failed novabank-demo stack alone until rollback finishes.
   It can be deleted once it reaches ROLLBACK_COMPLETE.

2. In S3, open YOUR_PRIVATE_ARTIFACT_BUCKET.
   Upload backend-api.zip directly into the bucket. Do not extract this ZIP.
   Leave public access blocked.

3. In CloudFormation in Mumbai, create a new standard stack.
   Upload template-api.yaml from this package.

   Stack name: novabank-api
   ArtifactBucket: YOUR_PRIVATE_ARTIFACT_BUCKET
   ArtifactKey: backend-api.zip

   Leave other stack options at defaults. Acknowledge IAM resource creation.
   Submit and wait for CREATE_COMPLETE. If a resource fails, read its Status
   reason before retrying. Other AWS services may still have account limits;
   removing CloudFront addresses the specific failure observed so far.

4. After CREATE_COMPLETE, open Outputs.
   Website is the app's HTTPS URL. FunctionName is the backend Lambda name.
   The compiled frontend is already in Lambda; no separate frontend upload
   or config.js edit is needed.

5. In Lambda, open the function named in FunctionName.
   Open Test and create a PRIVATE test event named SeedDemo with this JSON.
   REPLACE the password with your own private demo password first:

   {
     "action": "seed",
     "password": "REPLACE_WITH_YOUR_OWN_PASSWORD"
   }

   Use a password of 10 to 128 characters. Keep it private. Run Test once.
   A successful response contains created accounts and their account numbers.
   The three emails are admin@novabank.demo, aarav@novabank.demo, and
   meera@novabank.demo. They use the password you supplied in this test.
   Repeating this event will not reset existing passwords or add deposits.

6. Open Website from Outputs. Sign in with a seeded email and your password.
   Verify a transfer and administrator account controls. Cloud deployment
   is not complete until these real AWS checks pass.

CLEANUP AFTER MARKING
Delete the novabank-api CloudFormation stack to remove its database, API,
Lambda function, execution role and log group. This deletes cloud banking data.
Remove the deployment ZIPs and delete the separate artifact bucket when no
longer needed. The older failed stack and CloudFormation template upload
buckets should also be reviewed for cleanup.

This alternative does not use the original aws/deploy.py or cleanup.py,
which target the earlier CloudFront architecture.
