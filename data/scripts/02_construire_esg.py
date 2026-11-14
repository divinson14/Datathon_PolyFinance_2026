"""Étape 2 : drapeaux ESG (pour Mateo).

Entrées :
- raw/added/esg_etf_holdings.csv : titres détenus par le FNB filtré ESG du jeu de départ,
  téléchargés depuis le site de l'émetteur (colonne « symbole » au minimum).
- raw/added/esg_controverses.csv : table faite à la main (une ligne par action de l'univers).
Sortie : processed/esg_drapeaux.csv

Limite à documenter : c'est la méthodologie d'un émetteur et une revue manuelle, pas une vérité absolue.
"""
import pandas as pd
from commun import AJOUTS, PROCESSED

univers = pd.read_csv(PROCESSED / "univers_enrichi.csv")
holdings = pd.read_csv(AJOUTS / "esg_etf_holdings.csv")
controverses = pd.read_csv(AJOUTS / "esg_controverses.csv")

dans_fnb = set(holdings["symbole"].astype(str).str.upper())
df = univers[["symbole", "nom", "classe", "secteur"]].copy()
df["dans_fnb_esg"] = df["symbole"].str.upper().isin(dans_fnb)
df = df.merge(controverses, on="symbole", how="left")
df["controverse"] = df["controverse"].fillna("non évalué")
df.to_csv(PROCESSED / "esg_drapeaux.csv", index=False)
print(f"OK : {len(df)} actifs → processed/esg_drapeaux.csv")
