"""Lecture des données propres produites par data/ (local ou S3), ou données de démo fictives."""
from functools import lru_cache
import hashlib
import io
import json
import os

import numpy as np
import pandas as pd

from src.config import DONNEES, RACINE_REPO

DOSSIER_LOCAL = RACINE_REPO / "data" / "processed"
LIBELLE_DEMO = "DONNÉES FICTIVES de démonstration (data/processed/ absent)"
NOM_MANIFESTE = "manifeste.json"          # écrit par data/scripts/04_envoyer_s3.py

# Univers FICTIF de démonstration : mêmes symboles et classes que le jeu de départ,
# paramètres inventés (volatilité, rendement, sensibilité au facteur commun).
#            symbole     nom                         classe          devise  secteur                     vol   rend  beta
_DEMO = [("XIU.TO", "FNB actions canadiennes", "etf_equity", "CAD", "Broad market (Canada)", 0.14, 0.07, 0.9),
         ("SPY", "FNB S&P 500", "etf_equity", "USD", "Broad market (U.S.)", 0.16, 0.09, 1.0),
         ("QQQ", "FNB Nasdaq-100", "etf_equity", "USD", "Broad market (U.S. growth)", 0.22, 0.11, 1.0),
         ("ESGV", "FNB ESG É.-U.", "etf_equity", "USD", "Broad market (U.S., ESG)", 0.17, 0.09, 1.0),
         ("XBB.TO", "FNB obligations canadiennes", "etf_bond", "CAD", "Bonds (Canada)", 0.06, 0.02, 0.2),
         ("ZST.TO", "FNB obligations ultra-courtes", "etf_bond", "CAD", "Bonds (Canada ultra short)", 0.01, 0.03, 0.0),
         ("GLD", "FNB or", "etf_commodity", "USD", "Gold", 0.14, 0.05, 0.1),
         ("FTS.TO", "Fortis", "equity", "CAD", "Utilities", 0.16, 0.05, 0.4),
         ("JNJ", "Johnson & Johnson", "equity", "USD", "Health Care", 0.17, 0.04, 0.4),
         ("MSFT", "Microsoft", "equity", "USD", "Information Technology", 0.26, 0.12, 0.9),
         ("NVDA", "NVIDIA", "equity", "USD", "Information Technology", 0.50, 0.30, 1.0),
         ("SHOP.TO", "Shopify", "equity", "CAD", "Information Technology", 0.55, 0.10, 0.9),
         ("TSLA", "Tesla", "equity", "USD", "Consumer Discretionary", 0.60, 0.15, 0.8),
         ("BTC-USD", "Bitcoin", "crypto", "USD", "Crypto asset", 0.55, 0.20, 0.5),
         ("ETH-USD", "Ether", "crypto", "USD", "Crypto asset", 0.70, 0.15, 0.5)]


class DonneesS3Indisponibles(RuntimeError):
    """S3 demandé (DONNEES=s3) mais illisible. On s'arrête : jamais de repli silencieux vers le fictif."""


def _emplacement_s3() -> str:
    return f"s3://{os.getenv('S3_BUCKET', '?')}/{os.getenv('S3_PREFIX', 'processed/')}"


def _lire(nom: str) -> pd.DataFrame:
    return pd.read_csv(io.BytesIO(_lire_octets(nom)))


def _lire_octets(nom: str) -> bytes:
    """Contenu brut d'un fichier de data/processed/ (local) ou du bucket (S3). FileNotFoundError en local."""
    if DONNEES == "s3":
        import boto3
        from botocore.exceptions import BotoCoreError, ClientError, NoCredentialsError
        bucket = os.getenv("S3_BUCKET")
        if not bucket:
            raise DonneesS3Indisponibles("DONNEES=s3 mais S3_BUCKET est vide dans app/.env.")
        cle = os.getenv("S3_PREFIX", "processed/") + nom
        try:
            s3 = boto3.client("s3", region_name=os.getenv("AWS_REGION", "us-east-1"))
            obj = s3.get_object(Bucket=bucket, Key=cle)
        except NoCredentialsError as e:
            raise DonneesS3Indisponibles(
                "Identifiants AWS absents : collez ceux du Workshop dans le terminal ou app/.env.") from e
        except ClientError as e:
            code = e.response.get("Error", {}).get("Code", "?")
            raise DonneesS3Indisponibles(
                f"Lecture impossible de s3://{bucket}/{cle} ({code}) : bucket introuvable, fichier absent "
                f"(relancer data/scripts/04_envoyer_s3.py) ou accès refusé / identifiants expirés.") from e
        except BotoCoreError as e:
            raise DonneesS3Indisponibles(f"Erreur AWS en lisant s3://{bucket}/{cle} : {e}") from e
        return obj["Body"].read()
    return (DOSSIER_LOCAL / nom).read_bytes()


def empreinte(octets: bytes) -> str:
    """SHA-256, fins de ligne normalisées en \\n (même calcul que data/scripts/commun.py)."""
    return hashlib.sha256(octets.replace(b"\r\n", b"\n")).hexdigest()


@lru_cache(maxsize=1)
def charger_manifeste() -> dict | None:
    """Manifeste écrit par data/scripts/04_envoyer_s3.py (version, date, empreintes). None s'il est absent."""
    if _sans_donnees_reelles():
        return None
    try:
        return json.loads(_lire_octets(NOM_MANIFESTE))
    except (FileNotFoundError, DonneesS3Indisponibles):   # absent : la version est affichée « non vérifiée »
        return None


def statut_version(manifeste: dict | None, lus: dict[str, bytes]) -> str:
    """Compare les fichiers réellement lus au manifeste. Retourne un libellé à afficher, jamais muet."""
    if not manifeste:
        return "version non vérifiée (manifeste absent : relancer data/scripts/04_envoyer_s3.py)"
    attendus = manifeste.get("fichiers", {})
    differents = [nom for nom, octets in lus.items()
                  if attendus.get(nom, {}).get("sha256") != empreinte(octets)]
    if differents:
        return (f"⚠ ne correspond PAS au manifeste {manifeste.get('version', '?')} "
                f"({', '.join(differents)} modifié depuis) : relancer data/scripts/04_envoyer_s3.py")
    return f"version {manifeste.get('version', '?')} du {manifeste.get('genere_le', '?')[:10]}, empreintes vérifiées"


def _demo():
    """Données FICTIVES pour développer avant que data/ soit prêt. Jamais pour la démo finale."""
    rng = np.random.default_rng(42)
    dates = pd.bdate_range("2021-11-12", "2026-11-12")
    vols = np.array([a[5] for a in _DEMO])
    mu = np.array([a[6] for a in _DEMO])
    beta = np.array([a[7] for a in _DEMO])
    facteur = rng.standard_normal(len(dates))
    propre = rng.standard_normal((len(dates), len(_DEMO)))
    poids_f = np.clip(beta * 0.7, 0, 0.95)                       # part de variance liée au facteur commun
    z = facteur[:, None] * np.sqrt(poids_f) + propre * np.sqrt(1 - poids_f)
    annee_2022 = (dates.year == 2022)[:, None]
    derive = np.where(annee_2022, -0.25 * beta - 0.05, mu)       # 2022 : tout baisse, surtout le risqué
    rend = derive / 252 + vols / np.sqrt(252) * z
    prix = pd.DataFrame(100 * np.exp(np.cumsum(rend, axis=0)), index=dates, columns=[a[0] for a in _DEMO])
    prix.index.name = "date"
    univers = pd.DataFrame([a[:5] for a in _DEMO], columns=["symbole", "nom", "classe", "devise", "secteur"])
    univers["crypto"] = univers["classe"].eq("crypto")
    return prix, univers


def _sans_donnees_reelles() -> bool:
    return DONNEES == "demo" or (DONNEES == "local" and not (DOSSIER_LOCAL / "prix_cad_alignes.csv").exists())


@lru_cache(maxsize=1)
def charger():
    """Retourne (prix_cad, univers, source_libelle)."""
    if _sans_donnees_reelles():
        prix, univers = _demo()
        return prix, univers, LIBELLE_DEMO
    lus = {nom: _lire_octets(nom) for nom in ("prix_cad_alignes.csv", "univers_enrichi.csv")}
    prix = pd.read_csv(io.BytesIO(lus["prix_cad_alignes.csv"]))
    prix["date"] = pd.to_datetime(prix["date"])
    prix = prix.set_index("date").sort_index()
    univers = pd.read_csv(io.BytesIO(lus["univers_enrichi.csv"]))
    dossier = _emplacement_s3() if DONNEES == "s3" else "data/processed/"
    version = statut_version(charger_manifeste(), lus)
    return prix, univers, f"{dossier}prix_cad_alignes.csv (clôture ajustée, en CAD) · {version}"


def donnees_fictives() -> bool:
    """True si l'application tourne sur les données FICTIVES de démonstration (à signaler à l'utilisateur)."""
    return charger()[2] == LIBELLE_DEMO


@lru_cache(maxsize=1)
def charger_macro() -> pd.DataFrame | None:
    """Séries macro QUOTIDIENNES (date, series_id, value, label, source). None si indisponibles."""
    if _sans_donnees_reelles():
        return None
    try:
        macro = _lire("macro_quotidien.csv")
    except FileNotFoundError:               # local seulement ; en S3 l'erreur claire remonte
        return None
    macro["date"] = pd.to_datetime(macro["date"])
    return macro


@lru_cache(maxsize=1)
def charger_esg() -> pd.DataFrame | None:
    """Drapeaux ESG (symbole, controverse, source…) produits par data/scripts/02. None si absents."""
    if _sans_donnees_reelles():
        return None
    try:
        return _lire("esg_drapeaux.csv")
    except FileNotFoundError:               # local seulement ; en S3 l'erreur claire remonte
        return None
