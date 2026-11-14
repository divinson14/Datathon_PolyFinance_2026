"""Outils de calcul DÉTERMINISTES. Le LLM ne calcule jamais : il appelle ces fonctions.
Chaque fonction écrit une trace et renvoie son ID. Ce sont elles qui iront dans AWS Lambda."""
import numpy as np
import pandas as pd

from src.donnees.chargeur import charger
from src.formatage import money, pct, poids_texte

JOURS = 252


def _source():
    return charger()[2]


def statistiques(journal, symbole: str, agent: str) -> dict:
    prix, _, _ = charger()
    s = prix[symbole].dropna()
    vol = float(np.log(s).diff().std() * np.sqrt(JOURS))
    pire = float((s / s.cummax() - 1).min())
    tid = journal.log(titre=f"Profil de risque · {symbole}", agent=agent, outil=f'statistiques("{symbole}")',
                      entrees=f"actif : {symbole}", sortie=f"volatilité annualisée : {pct(vol)} · pire baisse : {pct(pire)}",
                      source=_source(), periode=f"{s.index.min().date()} → {s.index.max().date()}")
    return {"trace": tid, "vol": vol, "pire_baisse": pire}


def rejeu_2022(journal, poids: dict, capital: float, libelle: str, agent: str) -> dict:
    prix, _, _ = charger()
    p = prix.loc["2022", list(poids)].ffill().dropna()
    valeur = (p / p.iloc[0]).mul(pd.Series(poids)).sum(axis=1) * capital      # achat-conservation
    try:
        mensuel = valeur.resample("ME").last()
    except ValueError:                                                          # pandas < 2.2
        mensuel = valeur.resample("M").last()
    valeurs = [capital] + [float(v) for v in mensuel]
    final = valeurs[-1]
    rend = final / capital - 1
    tid = journal.log(titre=f"Rejeu 2022 · {libelle}", agent=agent, outil="rejeu_2022(poids, capital)",
                      entrees=f"{poids_texte(poids)} · capital {money(capital)}",
                      sortie=f"rendement {pct(rend)} · perte {money(final - capital)} · valeur finale {money(final)}",
                      source=_source(), periode=f"{p.index.min().date()} → {p.index.max().date()}")
    return {"trace": tid, "valeurs": valeurs, "final": final, "rend": rend, "perte": final - capital}


def volatilite_portefeuille(journal, poids: dict, libelle: str, agent: str) -> dict:
    prix, _, _ = charger()
    r = prix[list(poids)].pct_change().dropna()
    vol = float((r @ pd.Series(poids)).std() * np.sqrt(JOURS))
    tid = journal.log(titre=f"Volatilité · {libelle}", agent=agent, outil="volatilite_portefeuille(poids)",
                      entrees=poids_texte(poids), sortie=f"volatilité annualisée : {pct(vol)}",
                      source=_source(), periode=f"{r.index.min().date()} → {r.index.max().date()}")
    return {"trace": tid, "vol": vol}


def contexte_macro(journal, agent: str) -> dict:
    # TODO équipe : lire la série dans macro_rates.csv au lieu de ce fait saisi à la main.
    tid = journal.log(titre="Contexte des taux en 2022", agent=agent, outil='contexte_macro("taux_directeur_canada")',
                      entrees="série : taux directeur de la Banque du Canada",
                      sortie="1re hausse le 2022-03-02 : 0,25 % → 0,50 %",
                      source="Banque du Canada (à relier à macro_rates.csv)", periode="2022")
    return {"trace": tid}


def poids_avec_position(base: dict, symbole: str, part: float) -> dict:
    """Ajoute une position et réduit le reste du portefeuille proportionnellement."""
    out = {k: v * (1 - part) for k, v in base.items()}
    out[symbole] = out.get(symbole, 0) + part
    return out
