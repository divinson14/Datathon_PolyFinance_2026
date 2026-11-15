"""Étape 2 : drapeaux ESG (pour Mateo).

Entrées :
- raw/added/esg_etf_holdings.csv : titres détenus par un FNB filtré ESG, relevés sur le site de l'émetteur.
  Colonnes : symbole, fnb (ESGV ou XESG), date_donnees (date du relevé de l'émetteur).
  Seule « symbole » est lue ici ; les deux autres assurent la traçabilité ligne par ligne.
- raw/added/esg_controverses.csv : table faite à la main (une ligne par actif de l'univers).
  Colonne « controverse » = statut : oui · non · conforme (FNB filtré ESG) · non applicable (obligations, or)
  · non évalué. Colonne « motif » (si oui) : « secteur énergie (règle de l'équipe) » ou « exclu par ESGV (Vanguard) ».
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
