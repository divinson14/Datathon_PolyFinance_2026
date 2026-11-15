"""Étape 4 : écrit le manifeste des données puis dépose les fichiers propres dans S3 (lus ensuite par l'application).

Prérequis : identifiants AWS configurés (aws configure ou rôle IAM) et variable S3_BUCKET.
Aucune clé dans le code.
Le manifeste (processed/manifeste.json) donne la version exacte des données : empreinte SHA-256,
taille et période de chaque CSV. L'application l'affiche et vérifie les empreintes à la lecture.
"""
import os
import boto3
from dotenv import load_dotenv
from commun import NOM_MANIFESTE, PROCESSED, RACINE, ecrire_manifeste

# Même fichier .env que l'application (app/.env) : un seul endroit pour S3_BUCKET et S3_PREFIX.
# load_dotenv() sans chemin chercherait dans data/scripts/, data/ puis la racine, jamais dans app/.
load_dotenv(RACINE.parent / "app" / ".env")
if not os.getenv("S3_BUCKET"):
    raise SystemExit("S3_BUCKET absent : ajoutez S3_BUCKET=<nom du bucket> dans app/.env.")
bucket = os.environ["S3_BUCKET"]
prefixe = os.getenv("S3_PREFIX", "processed/")

manifeste = ecrire_manifeste()
print(f"Manifeste : version {manifeste['version']} ({len(manifeste['fichiers'])} fichiers)")

s3 = boto3.client("s3", region_name=os.getenv("AWS_REGION", "us-east-1"))
for f in PROCESSED.glob("*.csv"):
    s3.upload_file(str(f), bucket, prefixe + f.name)
    print(f"→ s3://{bucket}/{prefixe}{f.name}")
# Le manifeste en DERNIER : il ne décrit jamais un fichier pas encore déposé.
s3.upload_file(str(PROCESSED / NOM_MANIFESTE), bucket, prefixe + NOM_MANIFESTE)
print(f"→ s3://{bucket}/{prefixe}{NOM_MANIFESTE}")
