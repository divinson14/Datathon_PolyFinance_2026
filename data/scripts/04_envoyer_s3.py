"""Étape 4 : dépose les fichiers propres dans S3 (lus ensuite par l'application).

Prérequis : identifiants AWS configurés (aws configure ou rôle IAM) et variable S3_BUCKET.
Aucune clé dans le code.
"""
import os
import boto3
from dotenv import load_dotenv
from commun import PROCESSED

load_dotenv()
bucket = os.environ["S3_BUCKET"]
prefixe = os.getenv("S3_PREFIX", "processed/")
s3 = boto3.client("s3", region_name=os.getenv("AWS_REGION", "us-east-1"))
for f in PROCESSED.glob("*.csv"):
    s3.upload_file(str(f), bucket, prefixe + f.name)
    print(f"→ s3://{bucket}/{prefixe}{f.name}")
