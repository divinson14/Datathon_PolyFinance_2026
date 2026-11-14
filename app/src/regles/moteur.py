"""Moteur de règles : compare une allocation au mandat. Code pur, AUCUN LLM."""
from src.formatage import pct, poids_texte

EPS = 1e-9


def verifier_mandat(journal, poids: dict, symbole: str, rejeu: dict, vol: dict, gabarit: dict,
                    univers, libelle: str) -> dict:
    cryptos = set(univers.loc[univers["crypto"].astype(bool), "symbole"])
    part_crypto = sum(w for s, w in poids.items() if s in cryptos)
    g = gabarit
    regles = [
        {"regle": "Poids max par titre", "limite": pct(g["poids_max_par_titre"]), "valeur": pct(poids[symbole]),
         "ok": poids[symbole] <= g["poids_max_par_titre"] + EPS},
        {"regle": "Volatilité du portefeuille", "limite": "≤ " + pct(g["volatilite_max"]), "valeur": pct(vol["vol"]),
         "ok": vol["vol"] <= g["volatilite_max"] + EPS},
        {"regle": "Perte en 2022", "limite": "≥ " + pct(g["perte_max_toleree"]), "valeur": pct(rejeu["rend"]),
         "ok": rejeu["rend"] >= g["perte_max_toleree"] - EPS},
        {"regle": "Cryptoactifs", "limite": "≤ " + pct(g["crypto_max"]), "valeur": pct(part_crypto),
         "ok": part_crypto <= g["crypto_max"] + EPS},
        # TODO Mateo : règle d'exclusion ESG à partir de data/processed/esg_drapeaux.csv
    ]
    violees = [r for r in regles if not r["ok"]]
    sortie = (f"{len(violees)} règle(s) violée(s) : " + ", ".join(f"{r['regle']} ({r['valeur']} vs {r['limite']})" for r in violees)
              if violees else f"{len(regles)} règles sur {len(regles)} respectées")
    tid = journal.log(titre=f"Verdicts · {libelle}", agent="Agent Gouvernance (moteur de règles, sans LLM)",
                      outil="verifier_mandat(allocation, gabarit)", entrees=f"{poids_texte(poids)} · gabarit « {g['label']} »",
                      sortie=sortie, source="config/gabarits_risque.yaml", periode="exécution courante")
    return {"trace": tid, "regles": regles, "violees": violees}
