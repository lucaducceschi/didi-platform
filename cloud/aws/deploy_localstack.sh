#!/bin/bash
set -e

ENDPOINT="http://localhost:4566"
REGION="eu-central-1"

echo "=========================================================="
echo " DIDI Platform: Deploying Event-Driven S3/Lambda Pipeline "
echo " Environment: LocalStack ($0 Cost Emulation)              "
echo "=========================================================="

# Check if LocalStack is running
if ! curl -s "$ENDPOINT/_localstack/health" > /dev/null; then
    echo "LocalStack not running. Start it with: docker-compose up -d localstack"
    exit 1
fi

echo "[1/4] Creating S3 Buckets..."
aws --endpoint-url=$ENDPOINT --region=$REGION s3 mb s3://didi-articles-raw || true
aws --endpoint-url=$ENDPOINT --region=$REGION s3 mb s3://didi-articles-harmonized || true

echo "[2/4] Packaging Lambda Function..."
cd $(dirname "$0")
zip -q lambda_harmonizer.zip lambda_harmonizer.py

echo "[3/4] Creating IAM Role & Lambda Function in LocalStack..."
aws --endpoint-url=$ENDPOINT --region=$REGION lambda create-function \
    --function-name didi-harmonizer-fn \
    --runtime python3.11 \
    --role arn:aws:iam::000000000000:role/lambda-role \
    --handler lambda_harmonizer.lambda_handler \
    --zip-file fileb://lambda_harmonizer.zip \
    --environment "Variables={TARGET_BUCKET=didi-articles-harmonized}" || true

echo "[4/4] Configuring S3 Event Notification Trigger..."
aws --endpoint-url=$ENDPOINT --region=$REGION s3api put-bucket-notification-configuration \
    --bucket didi-articles-raw \
    --notification-configuration '{
        "LambdaFunctionConfigurations": [
            {
                "LambdaFunctionArn": "arn:aws:lambda:eu-central-1:000000000000:function:didi-harmonizer-fn",
                "Events": ["s3:ObjectCreated:*"]
            }
        ]
    }'

rm -f lambda_harmonizer.zip
echo "Deployment Complete! S3 -> Lambda -> S3 pipeline active on LocalStack."
