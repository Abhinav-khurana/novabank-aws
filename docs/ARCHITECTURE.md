# Deployed architecture

Browser HTTPS requests reach API Gateway and invoke Lambda. Static frontend assets are served by web_handler.py; /api requests reach the Python banking service. DynamoDB stores application records. IAM controls service access; CloudWatch stores logs and metrics. CloudFormation provisions the stack. S3 holds the deployment archive. CloudFront is not used.
