"""Moteur de règles : compare une allocation et ses mesures au mandat. Code pur, AUCUN LLM.

- evaluer_regles : fonction pure (aucune trace), réutilisée par la grille du point de bascule.
- verifier_mandat : même évaluation, journalisée (une trace par verdict).
"""
from src.config import CALCUL
from src.donnees.chargeur import charger_esg
from src.formatage import nombre, pct, poids_texte

EPS = 1e-9


def _classes(univers) -> dict:
    return dict(zip(univers["symbole"].astype(str), univers["classe"].astype(str)))


def _max_titre(valeurs: dict, titres: set) -> tuple[str | None, float]:
    candidats = {s: v for s, v in valeurs.items() if s in titres}
    if not candidats:
        return None, 0.0
    s = max(candidats, key=candidats.get)
    return s, candidats[s]


# Statuts ESG (colonne « controverse » de esg_drapeaux.csv) :
ESG_CONTROVERSE = {"oui"}                       # viole la règle (❌)
ESG_SANS_CONTROVERSE = {"non", "conforme"}      # respecte la règle (« conforme » = FNB filtré ESG)
ESG_NON_APPLICABLE = {"non applicable"}         # NEUTRE : ni confirmé conforme, ni information manquante
# Tout le reste (« non évalué », titre absent du fichier) = information manquante (⚠️), jamais conforme.


def _regle_esg(poids: dict, base: dict | None = None) -> dict:
    """Exclusions ESG, appliquée à TOUS les actifs détenus (actions, crypto ET FNB).
    - « oui » (controverse importante) viole la règle ;
    - « non » / « conforme » la respectent ;
    - « non applicable » (obligations, or) est NEUTRE : ni confirmé conforme, ni information manquante ;
    - tout le reste (« non évalué », absent du fichier) est une information manquante, jamais déclaré conforme.
    `base` = portefeuille supposé du persona : les actifs qui en viennent sont signalés comme tels, pour ne pas
    laisser croire que le manque concerne la demande."""
    esg = charger_esg()
    drapeaux = {} if esg is None else dict(zip(esg["symbole"].astype(str),
                                               esg["controverse"].astype(str).str.strip().str.lower()))
    base = base or {}
    detenus = [s for s, w in poids.items() if w > EPS]
    statut = {s: drapeaux.get(s, "non évalué") for s in detenus}
    exclus = [s for s in detenus if statut[s] in ESG_CONTROVERSE]
    neutres = [s for s in detenus if statut[s] in ESG_NON_APPLICABLE]
    evalues = [s for s in detenus if statut[s] in ESG_SANS_CONTROVERSE]
    inconnus = [s for s in detenus if s not in exclus + neutres + evalues]

    def _liste(symboles):
        return ", ".join(f"{s} (portefeuille supposé)" if base.get(s, 0) > EPS else s for s in symboles)

    if exclus:
        valeur = "controverse importante : " + _liste(exclus)
    elif inconnus:
        valeur = "non évalué : " + _liste(inconnus)
    elif evalues:
        valeur = "aucune controverse relevée"
    elif neutres:
        valeur = "non applicable : " + _liste(neutres)
    else:
        valeur = "aucune controverse relevée"
    return {"regle": "Exclusions ESG", "limite": "aucune controverse importante", "valeur": valeur,
            "ok": not exclus, "manquant": bool(inconnus) and not exclus,
            "neutre": bool(neutres) and not (exclus or inconnus or evalues)}


def evaluer_regles(poids: dict, mesures: dict, gabarit: dict, univers, persona: dict | None = None) -> list[dict]:
    """Liste des règles {regle, limite, valeur, ok[, manquant]}. Pure : aucune trace, aucun LLM."""
    g = gabarit
    classes = _classes(univers)
    titres = {s for s, c in classes.items() if c in CALCUL["classes_titres"]}
    poids = {s: w for s, w in poids.items() if w > EPS}

    s_poids, w_max = _max_titre(poids, titres)
    s_risque, r_max = _max_titre(mesures["parts_risque"], titres)
    part_oblig = sum(w for s, w in poids.items() if classes.get(s) == CALCUL["classe_obligations"])
    part_crypto = sum(w for s, w in poids.items() if classes.get(s) == "crypto")

    regles = [
        {"regle": "Poids max par titre", "limite": "≤ " + pct(g["poids_max_par_titre"]),
         "valeur": f"{s_poids} {pct(w_max)}" if s_poids else "aucun titre individuel",
         "ok": w_max <= g["poids_max_par_titre"] + EPS},
        {"regle": "Part du risque max par titre", "limite": "≤ " + pct(g["part_risque_max_par_titre"]),
         "valeur": f"{s_risque} {pct(r_max)}" if s_risque else "aucun titre individuel",
         "ok": r_max <= g["part_risque_max_par_titre"] + EPS},
        {"regle": "Volatilité du portefeuille", "limite": "≤ " + pct(g["volatilite_max"]), "valeur": pct(mesures["vol"]),
         "ok": mesures["vol"] <= g["volatilite_max"] + EPS},
        {"regle": "Pire baisse sur 5 ans", "limite": "≥ " + pct(g["pire_baisse_max"]), "valeur": pct(mesures["pire_baisse"]),
         "ok": mesures["pire_baisse"] >= g["pire_baisse_max"] - EPS},
        {"regle": "Obligations minimum", "limite": "≥ " + pct(g["obligations_min"]), "valeur": pct(part_oblig),
         "ok": part_oblig >= g["obligations_min"] - EPS},
        {"regle": "Cryptoactifs", "limite": "≤ " + pct(g["crypto_max"]), "valeur": pct(part_crypto),
         "ok": part_crypto <= g["crypto_max"] + EPS},
    ]
    if g.get("paris_effectifs_min") is not None:
        regles.append({"regle": "Paris indépendants minimum", "limite": "≥ " + nombre(g["paris_effectifs_min"]),
                       "valeur": nombre(mesures["paris_effectifs"]),
                       "ok": mesures["paris_effectifs"] >= g["paris_effectifs_min"] - EPS})
    if persona and persona.get("exclusions_esg"):
        regles.append(_regle_esg(poids, persona.get("portefeuille_suppose")))
    return regles


def verifier_mandat(journal, poids: dict, mesures: dict, gabarit: dict, univers, libelle: str,
                    persona: dict | None = None) -> dict:
    regles = evaluer_regles(poids, mesures, gabarit, univers, persona)
    violees = [r for r in regles if not r["ok"]]
    manquantes = [r for r in regles if r.get("manquant")]
    sortie = (f"{len(violees)} règle(s) violée(s) : " + ", ".join(f"{r['regle']} ({r['valeur']} vs {r['limite']})" for r in violees)
              if violees else f"{len(regles)} règles sur {len(regles)} respectées")
    if manquantes:
        sortie += " · information manquante : " + ", ".join(f"{r['regle']} ({r['valeur']})" for r in manquantes)
    tid = journal.log(titre=f"Verdicts · {libelle}", agent="Agent Gouvernance (moteur de règles, sans LLM)",
                      outil="verifier_mandat(allocation, gabarit)", entrees=f"{poids_texte(poids)} · gabarit « {gabarit['label']} »",
                      sortie=sortie, source="config/gabarits_risque.yaml", periode="exécution courante")
    return {"trace": tid, "regles": regles, "violees": violees, "manquantes": manquantes}
