"""Étape 3 : rapport de qualité, à copier dans la documentation technique."""
import pandas as pd
from commun import PROCESSED, REPORTS

prix = pd.read_csv(PROCESSED / "prix_cad_alignes.csv", parse_dates=["date"]).set_index("date")
journal = pd.read_csv(PROCESSED / "journal_nettoyage.csv")

lignes = ["# Rapport de qualité des données", "",
          f"- Période : {prix.index.min().date()} → {prix.index.max().date()}",
          f"- Jours de bourse : {len(prix)}", f"- Actifs : {prix.shape[1]}", "",
          "| Symbole | Première date | Manquants avant nettoyage | Manquants après |",
          "|---|---|---|---|"]
for _, r in journal.iterrows():
    premiere = prix[r["symbole"]].first_valid_index()
    lignes.append(f"| {r['symbole']} | {premiere.date() if premiere is not None else '—'} | "
                  f"{r['valeurs_manquantes_avant']} | {r['valeurs_manquantes_apres']} |")
lignes += ["", "## Traitements", "- Clôture ajustée (dividendes et fractionnements).",
           "- Crypto alignée sur le calendrier boursier.", "- Trous ≤ 3 jours de bourse : report de la dernière valeur.",
           "- Conversion USD → CAD au taux de la Banque du Canada du jour.", "",
           "## Limites", "- Biais de survie : l'univers ne contient que des actifs existants aujourd'hui.",
           "- Données quotidiennes seulement ; aucune donnée intrajournalière."]
(REPORTS / "rapport_qualite.md").write_text("\n".join(lignes), encoding="utf-8")
print("OK → reports/rapport_qualite.md")
