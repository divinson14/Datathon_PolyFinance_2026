"""Outils de calcul DÉTERMINISTES. Le LLM ne calcule jamais : il appelle ces fonctions.
Chaque outil écrit une trace et renvoie son ID. Ce sont eux qui iront dans AWS Lambda.

Méthode commune (paramètres dans config/calcul.yaml) :
- prix de clôture ajustés, convertis en CAD (data/scripts/01) ;
- rendements HEBDOMADAIRES (vendredi) : neutralise les calendriers TSX, NYSE et crypto ;
- portefeuille à poids constants (rééquilibré chaque semaine) : hypothèse affichée.
"""
from functools import lru_cache

import numpy as np
import pandas as pd

from src.config import CALCUL
from src.donnees.chargeur import charger, charger_macro
from src.formatage import money, nombre, pct, poids_texte
from src.regles.moteur import evaluer_regles

EPS = 1e-12


def _source():
    return charger()[2]


@lru_cache(maxsize=1)
def rendements_hebdo() -> pd.DataFrame:
    prix, _, _ = charger()
    hebdo = prix.resample(CALCUL["frequence"]).last()
    return hebdo.pct_change(fill_method=None).iloc[1:].dropna(how="all")


def _periode(r: pd.DataFrame) -> str:
    return f"{r.index.min().date()} → {r.index.max().date()} · {len(r)} semaines"


def poids_avec_position(base: dict, symbole: str, part: float) -> dict:
    """Ajoute une position et réduit le reste du portefeuille proportionnellement."""
    out = {k: v * (1 - part) for k, v in base.items()}
    out[symbole] = out.get(symbole, 0) + part
    return out


# ---------- Mesures pures (aucune trace) ----------

def mesures(poids: dict) -> dict:
    """Volatilité, pire baisse, part du risque par ligne, paris indépendants, corrélation max.

    - Part du risque (contribution d'Euler) : w_i·(Σw)_i / w'Σw. La somme vaut 1.
    - Paris indépendants : ratio de participation des valeurs propres de diag(w)·Σ·diag(w),
      soit (Σλ)² / Σλ². Vaut N si N lignes indépendantes de même risque, 1 si un seul facteur domine.
    """
    w = pd.Series({s: float(v) for s, v in poids.items() if v > EPS})
    r = rendements_hebdo()[list(w.index)].dropna()
    cov = r.cov() * CALCUL["annualisation"]
    variance = float(w @ cov @ w)
    vol = float(np.sqrt(variance))
    parts = (w * (cov @ w) / variance) if variance > EPS else w * 0
    valeur = pd.concat([pd.Series([1.0]), (1 + r @ w).cumprod().reset_index(drop=True)])
    pire = float((valeur / valeur.cummax() - 1).min())
    pondere = np.diag(w.values) @ cov.values @ np.diag(w.values)
    vp = np.clip(np.linalg.eigvalsh(pondere), 0, None)
    paris = float(vp.sum() ** 2 / (vp ** 2).sum()) if vp.sum() > EPS else 1.0
    corr_max = None
    if len(w) >= 2:
        c = r.corr().where(~np.eye(len(w), dtype=bool)).stack()
        (a, b), rho = c.idxmax(), float(c.max())
        corr_max = (a, b, rho)
    return {"poids": dict(w), "vol": vol, "pire_baisse": pire, "parts_risque": dict(parts),
            "paris_effectifs": paris, "correlation_max": corr_max, "periode": _periode(r)}


# ---------- Outils journalisés ----------

def statistiques(journal, symbole: str, agent: str) -> dict:
    m = mesures({symbole: 1.0})
    tid = journal.log(titre=f"Profil de risque · {symbole}", agent=agent, outil=f'statistiques("{symbole}")',
                      entrees=f"actif : {symbole} (en CAD)",
                      sortie=f"volatilité annualisée : {pct(m['vol'])} · pire baisse : {pct(m['pire_baisse'])}",
                      source=_source(), periode=m["periode"])
    return {"trace": tid, "vol": m["vol"], "pire_baisse": m["pire_baisse"]}


def analyse_portefeuille(journal, poids: dict, libelle: str, agent: str) -> dict:
    """Mesures complètes d'un portefeuille, dont la part du RISQUE par ligne (≠ part des dollars)."""
    m = mesures(poids)
    parts = sorted(m["parts_risque"].items(), key=lambda kv: -kv[1])
    detail = " · ".join(f"{s} {pct(v)}" for s, v in parts)
    sortie = (f"volatilité annualisée : {pct(m['vol'])} · pire baisse : {pct(m['pire_baisse'])} · "
              f"paris indépendants : {nombre(m['paris_effectifs'])} · part du risque : {detail}")
    if m["correlation_max"]:
        a, b, rho = m["correlation_max"]
        sortie += f" · corrélation la plus forte : {a}/{b} {nombre(rho, 2)}"
    tid = journal.log(titre=f"Analyse du risque · {libelle}", agent=agent, outil="analyse_portefeuille(poids)",
                      entrees=poids_texte(poids), sortie=sortie, source=_source(), periode=m["periode"])
    return {"trace": tid, **m}


def volatilite_portefeuille(journal, poids: dict, libelle: str, agent: str) -> dict:
    """Conservé pour compatibilité (registre, Lambda) : délègue à analyse_portefeuille."""
    return analyse_portefeuille(journal, poids, libelle, agent)


def point_de_bascule(journal, base: dict, symbole: str, gabarit: dict, univers, agent: str,
                     persona: dict | None = None) -> dict:
    """Part maximale de `symbole` (ajoutée au portefeuille de base) qui respecte TOUTES les règles.

    Balaye une grille de 0 à 100 % (pas dans config/calcul.yaml) et note, pour chaque règle,
    la première part qui la franchit. part_max = None si le portefeuille de base viole déjà le mandat.
    """
    pas = CALCUL["pas_bascule"]
    grille = np.round(np.arange(0, 1 + pas / 2, pas), 6)
    premiere: dict[str, float] = {}          # règle -> première part qui la franchit
    part_max, limitantes, seuil = None, [], None
    courbe = []                              # courbe de bascule : part du risque en fonction du poids demandé
    for x in map(float, grille):
        poids = poids_avec_position(base, symbole, x)
        m = mesures(poids)
        violees = [r["regle"] for r in evaluer_regles(poids, m, gabarit, univers, persona) if not r["ok"]]
        courbe.append({"part": x, "part_risque": float(m["parts_risque"].get(symbole, 0.0)), "vol": m["vol"],
                       "conforme": not violees})
        for r in violees:
            premiere.setdefault(r, x)
        if not limitantes:
            if violees:
                limitantes, seuil = violees, x
            else:
                part_max = x
    base_conforme = seuil != 0.0

    if not base_conforme:
        sortie = "le portefeuille de base viole déjà le mandat : " + ", ".join(limitantes)
    else:
        sortie = f"point de bascule : {pct(part_max)} de {symbole}"
        if limitantes:
            sortie += f" · première règle franchie à {pct(seuil)} : {', '.join(limitantes)}"
        autres = [f"{r} à {pct(x)}" for r, x in sorted(premiere.items(), key=lambda kv: kv[1]) if r not in limitantes]
        if autres:
            sortie += " · autres seuils : " + ", ".join(autres)
    sortie += f" · courbe de bascule : {len(grille)} points calculés"
    tid = journal.log(titre=f"Point de bascule · {symbole}", agent=agent,
                      outil=f'point_de_bascule(base, "{symbole}", gabarit)',
                      entrees=f"base : {poids_texte(base)} · grille de 0 à 100 % par pas de {pct(pas)} · gabarit « {gabarit['label']} »",
                      sortie=sortie, source=f"{_source()} + config/gabarits_risque.yaml", periode=_periode(rendements_hebdo()))
    return {"trace": tid, "part_max": part_max, "limitantes": limitantes, "premiere_violation": premiere,
            "base_conforme": base_conforme, "courbe": courbe}


def rejeu_2022(journal, poids: dict, capital: float, libelle: str, agent: str) -> dict:
    """Rejeu achat-conservation sur l'année de scénario (config/calcul.yaml), en CAD, valeurs mensuelles."""
    annee = str(CALCUL["annee_scenario"])
    prix, _, _ = charger()
    p = prix.loc[annee, list(poids)].ffill().dropna()
    valeur = (p / p.iloc[0]).mul(pd.Series(poids)).sum(axis=1) * capital
    mensuel = valeur.resample("ME").last()
    valeurs = [capital] + [float(v) for v in mensuel]
    final = valeurs[-1]
    rend = final / capital - 1
    tid = journal.log(titre=f"Rejeu {annee} · {libelle}", agent=agent, outil=f"rejeu_{annee}(poids, capital)",
                      entrees=f"{poids_texte(poids)} · capital {money(capital)}",
                      sortie=f"rendement {pct(rend)} · perte {money(final - capital)} · valeur finale {money(final)}",
                      source=_source(), periode=f"{p.index.min().date()} → {p.index.max().date()}")
    return {"trace": tid, "valeurs": valeurs, "final": final, "rend": rend, "perte": final - capital}


def contexte_macro(journal, agent: str) -> dict:
    """Taux directeur de la Banque du Canada pendant l'année de scénario, lu dans macro_quotidien.csv.
    Série quotidienne publiée le jour même : aucune information « du futur »."""
    annee = CALCUL["annee_scenario"]
    serie = CALCUL["serie_taux_directeur"]
    macro = charger_macro()
    if macro is None:
        tid = journal.log(titre=f"Contexte des taux en {annee}", agent=agent, outil=f'contexte_macro("{serie}")',
                          entrees=f"série : {serie}", sortie="série macro indisponible (données de démonstration)",
                          source="aucune", periode=str(annee))
        return {"trace": tid, "disponible": False, "resume": None}
    s = macro[macro["series_id"] == serie].set_index("date")["value"].sort_index()
    s = s[str(annee)]
    hausses = s[s.diff() > 0]
    debut, fin = float(s.iloc[0]), float(s.iloc[-1])
    if len(hausses):
        d = hausses.index[0]
        avant = float(s[:d].iloc[-2])
        sortie = (f"1re hausse observée le {d.date()} : {nombre(avant, 2)} % → {nombre(float(hausses.iloc[0]), 2)} % · "
                  f"{len(hausses)} hausse(s) dans l'année · {nombre(debut, 2)} % → {nombre(fin, 2)} %")
    else:
        sortie = f"aucune hausse dans l'année · {nombre(debut, 2)} % → {nombre(fin, 2)} %"
    label = str(macro.loc[macro["series_id"] == serie, "label"].iloc[0])
    tid = journal.log(titre=f"Contexte des taux en {annee}", agent=agent, outil=f'contexte_macro("{serie}")',
                      entrees=f"série : {label}", sortie=sortie,
                      source="Banque du Canada, API Valet (data/processed/macro_quotidien.csv)", periode=str(annee))
    return {"trace": tid, "disponible": True, "debut": debut, "fin": fin, "nb_hausses": len(hausses), "resume": sortie}


def pire_fenetre_12_mois(journal, poids: dict, libelle: str, agent: str) -> dict:
    """Pire rendement sur une fenêtre glissante de N jours de bourse (N = fenetre_stress_jours, 252 ≈ 12 mois).

    Chaque fenêtre est rejouée en achat-conservation (comme le rejeu 2022) ; seuls les jours de semaine
    comptent comme jours de bourse (le prix du vendredi est reporté sur les jours fériés).
    """
    n = int(CALCUL["fenetre_stress_jours"])
    prix, _, _ = charger()
    p = prix[list(poids)].ffill().dropna()
    p = p[p.index.dayofweek < 5]
    if len(p) <= n:
        tid = journal.log(titre=f"Pire fenêtre de 12 mois · {libelle}", agent=agent, outil="pire_fenetre_12_mois(poids)",
                          entrees=poids_texte(poids), sortie=f"historique trop court ({len(p)} jours pour une fenêtre de {n})",
                          source=_source(), periode=f"{p.index.min().date()} → {p.index.max().date()}" if len(p) else "aucune")
        return {"trace": tid, "rend": None, "debut": None, "fin": None}
    rend = ((p.shift(-n) / p).mul(pd.Series(poids)).sum(axis=1) - 1).iloc[:-n]
    debut = rend.idxmin()
    fin = p.index[p.index.get_loc(debut) + n]
    pire = float(rend.min())
    tid = journal.log(titre=f"Pire fenêtre de 12 mois · {libelle}", agent=agent, outil="pire_fenetre_12_mois(poids)",
                      entrees=f"{poids_texte(poids)} · fenêtre glissante de {n} jours de bourse, achat-conservation",
                      sortie=f"pire rendement sur 12 mois : {pct(pire)} · du {debut.date()} au {fin.date()}",
                      source=_source(), periode=f"{p.index.min().date()} → {p.index.max().date()} · {len(rend)} fenêtres")
    return {"trace": tid, "rend": pire, "debut": str(debut.date()), "fin": str(fin.date())}
