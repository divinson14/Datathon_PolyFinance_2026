"""Outils partagés par les scripts de préparation des données."""
from pathlib import Path
import pandas as pd

RACINE = Path(__file__).resolve().parents[1]          # dossier data/
RAW = RACINE / "raw" / "starter"
AJOUTS = RACINE / "raw" / "added"
PROCESSED = RACINE / "processed"
REPORTS = RACINE / "reports"


def trouver_colonne(df: pd.DataFrame, candidats: list[str], quoi: str) -> str:
    """Retrouve une colonne parmi plusieurs noms possibles (insensible à la casse).

    Les noms exacts du jeu de départ ne sont pas connus d'avance : vérifiez-les
    dans data/raw/starter/README.md et ajoutez-les aux listes de candidats si besoin.
    """
    bas = {c.lower().strip(): c for c in df.columns}
    for c in candidats:
        if c.lower() in bas:
            return bas[c.lower()]
    raise KeyError(
        f"Colonne « {quoi} » introuvable. Colonnes disponibles : {list(df.columns)}. "
        f"Ajoutez le bon nom à la liste des candidats dans le script."
    )


def lire_csv(nom: str) -> pd.DataFrame:
    chemin = RAW / nom
    if not chemin.exists():
        raise FileNotFoundError(
            f"{chemin} introuvable. Copiez les fichiers du jeu de départ du datathon dans data/raw/starter/."
        )
    return pd.read_csv(chemin)


# --- Manifeste des données : quelle version exacte des fichiers propres l'application lit ---
NOM_MANIFESTE = "manifeste.json"


def empreinte(octets: bytes) -> str:
    """SHA-256 du contenu, fins de ligne normalisées en \n.

    Git (core.autocrlf) peut écrire les CSV en \r\n sous Windows et en \n ailleurs : sans
    normalisation, un même fichier aurait deux empreintes. Même calcul dans app/src/donnees/chargeur.py.
    """
    import hashlib
    return hashlib.sha256(octets.replace(b"\r\n", b"\n")).hexdigest()


def ecrire_manifeste() -> dict:
    """Décrit chaque CSV de processed/ (empreinte, taille, période) et écrit processed/manifeste.json."""
    import json
    from datetime import datetime, timezone
    from io import BytesIO

    fichiers = {}
    for f in sorted(PROCESSED.glob("*.csv")):
        octets = f.read_bytes()
        df = pd.read_csv(BytesIO(octets))
        info = {"sha256": empreinte(octets), "lignes": len(df), "colonnes": df.shape[1]}
        if "date" in df.columns:
            dates = pd.to_datetime(df["date"])
            info["periode"] = {"debut": str(dates.min().date()), "fin": str(dates.max().date())}
        fichiers[f.name] = info
    # Version = empreinte de l'ensemble : change dès qu'un seul fichier change.
    ensemble = "\n".join(f"{nom}:{i['sha256']}" for nom, i in fichiers.items()).encode()
    manifeste = {
        "version": empreinte(ensemble)[:12],
        "genere_le": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "genere_par": "data/scripts/04_envoyer_s3.py",
        "fichiers": fichiers,
    }
    (PROCESSED / NOM_MANIFESTE).write_text(json.dumps(manifeste, ensure_ascii=False, indent=2) + "\n",
                                           encoding="utf-8")
    return manifeste
