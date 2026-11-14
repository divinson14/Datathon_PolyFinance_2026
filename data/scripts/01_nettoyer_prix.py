"""Étape 1 : prix propres, alignés et convertis en CAD.

Entrées  : raw/starter/prices_daily.csv, assets_universe.csv, fx_usdcad_daily.csv
Sorties  : processed/prix_cad_alignes.csv  (date + une colonne par symbole, en CAD)
           processed/univers_enrichi.csv   (symbole, nom, classe, devise, secteur, crypto)
           processed/journal_nettoyage.csv (ce qui a été corrigé, pour le rapport de qualité)

Choix documentés (à reporter dans docs/decisions.md) :
- On utilise la clôture AJUSTÉE (dividendes et fractionnements).
- Calendrier de référence = jours où les actions/FNB cotent. La crypto, qui cote 7 j/7,
  est ramenée à ces dates (sinon les corrélations sont faussées).
- Trous de 3 jours ouvrables au plus : report de la dernière valeur (ffill), consigné.
- Conversion USD → CAD avec le taux de la Banque du Canada du même jour
  (hypothèse : le taux est exprimé en CAD pour 1 USD — à vérifier dans sources_metadata.csv).
"""
import pandas as pd
from commun import trouver_colonne, lire_csv, PROCESSED

prix = lire_csv("prices_daily.csv")
univers = lire_csv("assets_universe.csv")
fx = lire_csv("fx_usdcad_daily.csv")

# --- Colonnes (adapter les listes si les noms diffèrent) ---
c_date = trouver_colonne(prix, ["date"], "date")
c_sym = trouver_colonne(prix, ["symbol", "symbole", "ticker"], "symbole")
c_adj = trouver_colonne(prix, ["adj_close", "adjusted_close", "adj close", "cloture_ajustee", "close_adj"], "clôture ajustée")
c_dev = trouver_colonne(prix, ["currency", "devise", "quote_currency"], "devise")

u_sym = trouver_colonne(univers, ["symbol", "symbole", "ticker"], "symbole (univers)")
u_nom = trouver_colonne(univers, ["name", "nom"], "nom")
u_cls = trouver_colonne(univers, ["asset_class", "classe", "classe_actif", "class"], "classe d'actif")
u_dev = trouver_colonne(univers, ["currency", "devise"], "devise (univers)")
u_sec = trouver_colonne(univers, ["sector", "secteur"], "secteur")

f_date = trouver_colonne(fx, ["date"], "date (fx)")
f_val = trouver_colonne(fx, ["usdcad", "fxusdcad", "rate", "value", "taux"], "taux USD/CAD")

prix[c_date] = pd.to_datetime(prix[c_date])
fx[f_date] = pd.to_datetime(fx[f_date])

# --- Univers enrichi ---
u = univers.rename(columns={u_sym: "symbole", u_nom: "nom", u_cls: "classe", u_dev: "devise", u_sec: "secteur"})
u["crypto"] = u["classe"].astype(str).str.lower().str.contains("crypto")
u[["symbole", "nom", "classe", "devise", "secteur", "crypto"]].to_csv(PROCESSED / "univers_enrichi.csv", index=False)

# --- Conversion en CAD ---
# Taux reporté sur TOUS les jours civils (fériés canadiens, fins de semaine pour la crypto)
# AVANT la fusion : un ffill sur la table longue mélangerait les symboles.
taux = fx.set_index(f_date)[f_val].sort_index()
taux = taux.reindex(pd.date_range(taux.index.min(), prix[c_date].max(), freq="D")).ffill()
prix = prix.merge(taux.rename("usdcad"), left_on=c_date, right_index=True, how="left")
est_usd = prix[c_dev].astype(str).str.upper().eq("USD")
prix["prix_cad"] = prix[c_adj].where(~est_usd, prix[c_adj] * prix["usdcad"])

# --- Table large : une colonne par symbole ---
large = prix.pivot_table(index=c_date, columns=c_sym, values="prix_cad").sort_index()

# --- Alignement sur le calendrier des marchés boursiers ---
cryptos = set(u.loc[u["crypto"], "symbole"])
non_crypto = [s for s in large.columns if s not in cryptos]
jours_bourse = large[non_crypto].dropna(how="all").index
avant = large.loc[jours_bourse].isna().sum()          # trous sur les seuls jours de bourse
# On réduit AVANT le report : sinon les fins de semaine (lignes crypto) comptent dans la limite
# et un congé de 2 jours de bourse collé à un week-end (ex. Noël TSX) dépasse les 3 jours.
large = large.loc[jours_bourse].ffill(limit=3)
apres = large.isna().sum()

journal = pd.DataFrame({"symbole": large.columns, "valeurs_manquantes_avant": avant.reindex(large.columns).values,
                        "valeurs_manquantes_apres": apres.values})
journal.to_csv(PROCESSED / "journal_nettoyage.csv", index=False)

large.index.name = "date"
large.to_csv(PROCESSED / "prix_cad_alignes.csv")
# --- Macro : copie filtrée (seules les séries quotidiennes, sans décalage de publication) ---
macro = lire_csv("macro_rates.csv")
quotidiennes = ["V39079", "BD.CDN.2YR.DQ.YLD", "BD.CDN.10YR.DQ.YLD", "DFF", "DGS2", "DGS10"]
macro[macro["series_id"].isin(quotidiennes)].to_csv(PROCESSED / "macro_quotidien.csv", index=False)
# Les séries mensuelles (IPC, chômage) sont datées au mois de référence et publiées des semaines
# plus tard : on ne les copie pas, pour ne jamais « voir le futur » dans une simulation.

print(f"OK : {large.shape[0]} jours × {large.shape[1]} actifs → processed/prix_cad_alignes.csv")
