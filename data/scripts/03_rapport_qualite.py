"""Étape 3 : rapport de qualité, à copier dans la documentation technique.

Entrées  : processed/prix_cad_alignes.csv, processed/journal_nettoyage.csv,
           raw/starter/fx_usdcad_daily.csv, raw/added/explications_variations.csv
Sortie   : reports/rapport_qualite.md
Contrôles automatiques : chaque contrôle affiche ✔ ou ✘ ; le script se termine en erreur (code 1) si un contrôle échoue.
"""
import sys

import pandas as pd
from commun import AJOUTS, PROCESSED, REPORTS, lire_csv, trouver_colonne

if hasattr(sys.stdout, "reconfigure"):          # console Windows (cp1252) : sinon ✔ / ✘ font planter print
    sys.stdout.reconfigure(encoding="utf-8")

# Seuils des contrôles (choix de l'équipe, documentés dans docs/decisions.md)
SEUIL_VARIATION = 0.15        # variation quotidienne à EXPLIQUER (événement réel ou erreur ?)
SEUIL_SUSPECT = 0.35          # au-delà : erreur de données probable (ex. fractionnement non ajusté)
TAUX_MIN, TAUX_MAX = 1.15, 1.55   # USD/CAD plausible sur 2021-2026 (CAD pour 1 USD)

prix = pd.read_csv(PROCESSED / "prix_cad_alignes.csv", parse_dates=["date"]).set_index("date")
journal = pd.read_csv(PROCESSED / "journal_nettoyage.csv")
fx = lire_csv("fx_usdcad_daily.csv")
taux = fx[trouver_colonne(fx, ["usdcad", "fxusdcad", "rate", "value", "taux"], "taux USD/CAD")]
explications = pd.read_csv(AJOUTS / "explications_variations.csv", parse_dates=["date"])

# --- Variations quotidiennes extrêmes (prix en CAD, jours de bourse) ---
rend = prix.pct_change(fill_method=None)
longues = rend.stack().rename("variation").reset_index()
longues.columns = ["date", "symbole", "variation"]
extremes = longues[longues["variation"].abs() > SEUIL_VARIATION].sort_values(["symbole", "date"])
extremes = extremes.merge(explications, on=["date", "symbole"], how="left")
extremes["statut"] = extremes["statut"].fillna("à expliquer")
suspects = extremes[extremes["variation"].abs() > SEUIL_SUSPECT]

# --- Contrôles automatiques : (réussi ?, libellé) ---
controles = [
    ((prix > 0).all().all(), "Tous les prix sont strictement positifs"),
    (prix.index.is_unique, "Aucune date en double"),
    (prix.index.is_monotonic_increasing, "Dates dans l'ordre chronologique"),
    (int(prix.isna().sum().sum()) == 0, "Aucune valeur manquante après nettoyage"),
    (TAUX_MIN < taux.min() and taux.max() < TAUX_MAX,
     f"Taux USD/CAD entre {taux.min():.3f} et {taux.max():.3f} (plausible : {TAUX_MIN} à {TAUX_MAX})"),
    (suspects.empty, f"Aucune variation quotidienne de plus de {SEUIL_SUSPECT:.0%} (erreur de données probable)"),
]

lignes = ["# Rapport de qualité des données", "",
          f"- Période : {prix.index.min().date()} → {prix.index.max().date()}",
          f"- Jours de bourse : {len(prix)}", f"- Actifs : {prix.shape[1]}", "",
          "## Contrôles automatiques", ""]
lignes += [f"- {'✔' if reussi else '✘'} {libelle}" for reussi, libelle in controles]
lignes += ["", "## Valeurs manquantes", "",
           "| Symbole | Première date | Manquants avant nettoyage | Manquants après |",
           "|---|---|---|---|"]
for _, r in journal.iterrows():
    premiere = prix[r["symbole"]].first_valid_index()
    lignes.append(f"| {r['symbole']} | {premiere.date() if premiere is not None else '—'} | "
                  f"{r['valeurs_manquantes_avant']} | {r['valeurs_manquantes_apres']} |")

a_expliquer = int((extremes["statut"] == "à expliquer").sum())
lignes += ["", f"## Variations quotidiennes de plus de {SEUIL_VARIATION:.0%}", "",
           f"{len(extremes)} variations repérées, dont {a_expliquer} encore à expliquer. Chacune est soit un événement réel "
           "(conservé tel quel), soit une erreur (à corriger). Les explications viennent de "
           "`raw/added/explications_variations.csv` ; « hypothèse à confirmer » = événement connu de l'équipe, "
           "source à ajouter. Crypto : la variation du lundi cumule celles de la fin de semaine "
           "(prix ramenés au calendrier boursier).", "",
           "| Date | Symbole | Variation | Explication | Statut |", "|---|---|---|---|---|"]
for _, r in extremes.iterrows():
    explication = r["explication"] if isinstance(r["explication"], str) else "—"
    lignes.append(f"| {r['date'].date()} | {r['symbole']} | {r['variation']:+.1%} | {explication} | {r['statut']} |")

lignes += ["", "## Traitements", "- Clôture ajustée (dividendes et fractionnements).",
           "- Crypto alignée sur le calendrier boursier.", "- Trous ≤ 3 jours de bourse : report de la dernière valeur.",
           "- Conversion USD → CAD au taux de la Banque du Canada du jour.", "",
           "## Limites", "- Biais de survie : l'univers ne contient que des actifs existants aujourd'hui.",
           "- Données quotidiennes seulement ; aucune donnée intrajournalière."]
(REPORTS / "rapport_qualite.md").write_text("\n".join(lignes) + "\n", encoding="utf-8")

for reussi, libelle in controles:
    print(f"{'✔' if reussi else '✘'} {libelle}")
print(f"{len(extremes)} variations > {SEUIL_VARIATION:.0%} ({a_expliquer} à expliquer)")
print("OK → reports/rapport_qualite.md")
if not all(reussi for reussi, _ in controles):
    sys.exit(1)
