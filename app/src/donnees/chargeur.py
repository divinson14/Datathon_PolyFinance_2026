"""Lecture des données propres produites par data/ (local ou S3), ou données de démo fictives."""
from functools import lru_cache
import io
import os

import numpy as np
import pandas as pd

from src.config import DONNEES, RACINE_REPO

DOSSIER_LOCAL = RACINE_REPO / "data" / "processed"


def _lire(nom: str) -> pd.DataFrame:
    if DONNEES == "s3":
        import boto3
        s3 = boto3.client("s3", region_name=os.getenv("AWS_REGION", "us-east-1"))
        obj = s3.get_object(Bucket=os.environ["S3_BUCKET"], Key=os.getenv("S3_PREFIX", "processed/") + nom)
        return pd.read_csv(io.BytesIO(obj["Body"].read()))
    return pd.read_csv(DOSSIER_LOCAL / nom)


def _demo():
    """Données FICTIVES pour développer avant que data/ soit prêt. Jamais pour la démo finale."""
    rng = np.random.default_rng(42)
    dates = pd.bdate_range("2021-11-12", "2026-11-12")
    actifs = ["TSLA", "XIU", "XBB"]
    vols = np.array([0.55, 0.12, 0.06])
    corr = np.array([[1, 0.45, 0.10], [0.45, 1, 0.30], [0.10, 0.30, 1]])
    chol = np.linalg.cholesky(corr)
    derive = {2022: np.array([-1.0, 0.0, -0.08])}
    rend = []
    for d in dates:
        mu = derive.get(d.year, np.array([0.25, 0.08, 0.02]))
        z = chol @ rng.standard_normal(3)
        rend.append(mu / 252 + vols / np.sqrt(252) * z)
    prix = pd.DataFrame(np.exp(np.cumsum(rend, axis=0)) * [300, 30, 30], index=dates, columns=actifs)
    prix.index.name = "date"
    univers = pd.DataFrame({
        "symbole": actifs,
        "nom": ["Tesla", "FNB actions canadiennes (exemple)", "FNB obligations canadiennes (exemple)"],
        "classe": ["Action", "FNB actions", "FNB obligations"],
        "devise": ["USD", "CAD", "CAD"], "secteur": ["Consommation discrétionnaire", "Diversifié", "Obligations"],
        "crypto": [False, False, False],
    })
    return prix, univers


@lru_cache(maxsize=1)
def charger():
    """Retourne (prix_cad, univers, source_libelle)."""
    if DONNEES == "demo" or (DONNEES == "local" and not (DOSSIER_LOCAL / "prix_cad_alignes.csv").exists()):
        prix, univers = _demo()
        return prix, univers, "DONNÉES FICTIVES de démonstration (data/processed/ absent)"
    prix = _lire("prix_cad_alignes.csv")
    prix["date"] = pd.to_datetime(prix["date"])
    prix = prix.set_index("date").sort_index()
    univers = _lire("univers_enrichi.csv")
    return prix, univers, "data/processed/prix_cad_alignes.csv (clôture ajustée, en CAD)"
