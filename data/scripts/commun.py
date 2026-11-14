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
