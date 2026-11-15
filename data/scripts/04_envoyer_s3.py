"""Étape 4 : dépose les fichiers propres dans S3 (lus ensuite par l'application).

Prérequis : identifiants AWS configurés (aws configure ou rôle IAM) et variable S3_BUCKET.
Aucune clé dans le code.
"""
import os
import boto3
from dotenv import load_dotenv
from commun import PROCESSED, RACINE

# Même fichier .env que l'application (app/.env) : un seul endroit pour S3_BUCKET et S3_PREFIX.
# load_dotenv() sans chemin chercherait dans data/scripts/, data/ puis la racine, jamais dans app/.
load_dotenv(RACINE.parent / "app" / ".env")
if not os.getenv("S3_BUCKET"):
    raise SystemExit("S3_BUCKET absent : ajoutez S3_BUCKET=<nom du bucket> dans app/.env.")
bucket = os.environ["S3_BUCKET"]
prefixe = os.getenv("S3_PREFIX", "processed/")
s3 = boto3.client("s3", region_name=os.getenv("AWS_REGION", "us-east-1"))
for f in PROCESSED.glob("*.csv"):
    s3.upload_file(str(f), bucket, prefixe + f.name)
    print(f"→ s3://{bucket}/{prefixe}{f.name}")
