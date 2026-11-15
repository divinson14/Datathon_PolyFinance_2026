"""Différentiel « Et si… » : compare l'analyse d'ORIGINE et l'analyse modifiée. Code pur, AUCUN LLM.

Une seule trace porte toutes les valeurs AVANT et APRÈS (formatées comme dans l'interface) :
l'Explicabilité ne peut citer que ces chiffres, et le vérificateur de fidélité les retrouve.
`origine` et `nouveau` ont les mêmes clés : gabarit, mandat, demande, alternative, verdicts
(le résultat d'executer() ou le contexte de rédaction).
"""
from src.config import CALCUL
from src.formatage import money, nombre, pct

LIMITES = [("poids_max_par_titre", "Poids max par titre"), ("part_risque_max_par_titre", "Part du risque max par titre"),
           ("volatilite_max", "Volatilité max du portefeuille"), ("pire_baisse_max", "Pire baisse max"),
           ("obligations_min", "Obligations minimum"), ("crypto_max", "Cryptoactifs max"),
           ("paris_effectifs_min", "Paris indépendants minimum")]


def _limite(gabarit: dict, cle: str) -> str:
    v = gabarit.get(cle)
    if v is None:
        return "non vérifié"
    return nombre(v) if cle == "paris_effectifs_min" else pct(v)


def _vue(r: dict) -> dict:
    """Valeurs comparées, déjà formatées (texte identique dans la trace, l'interface et l'explication)."""
    g, d, verd, alt = r["gabarit"], r["demande"], r["verdicts"], r["alternative"]
    b = d["bascule"]
    vue = {"Gabarit de tolérance": f"« {g['label']} »", "Horizon": r["mandat"]["profil"]["horizon"]}
    vue.update({libelle: _limite(g, cle) for cle, libelle in LIMITES})
    vue.update({
        "Part demandée": pct(r["mandat"]["demande"]["part"]),
        "Règles violées par la demande": (", ".join(x["regle"] for x in verd["violees"]) if verd["violees"] else "aucune"),
        "Facteur limitant (1re règle franchie)": (b["limitantes"][0] if b["limitantes"] else "aucun"),
        "Point de bascule": (pct(b["part_max"]) if b["base_conforme"] and b["part_max"] is not None
                             else "portefeuille actuel non conforme"),
        "Statut": verd["statut"],
        "Alternative au point de bascule": pct(alt["part"]) if alt else "aucune",
        f"Rejeu {CALCUL['annee_scenario']} · demande": f"{pct(d['rejeu']['rend'])} ({money(d['rejeu']['perte'])})",
        "Tensions du profil": " ; ".join(r["mandat"]["tensions"]) if r["mandat"]["tensions"] else "aucune",
    })
    return vue


def comparer(journal, origine: dict, nouveau: dict, libelle: str) -> dict:
    """Différentiel avant / après, journalisé. Renvoie {trace, lignes: [{element, avant, apres, change}], changements}."""
    a, n = _vue(origine), _vue(nouveau)
    lignes = [{"element": k, "avant": a[k], "apres": n[k], "change": a[k] != n[k]} for k in a]
    changes = [l for l in lignes if l["change"]]
    inchanges = [l for l in lignes if not l["change"]]
    sortie = " · ".join(f"{l['element']} : {l['avant']} → {l['apres']}" for l in changes) or "aucun changement"
    sortie += " · inchangé : " + " · ".join(f"{l['element']} = {l['avant']}" for l in inchanges) if inchanges else ""
    ov, nv = origine["verdicts"], nouveau["verdicts"]
    tid = journal.log(titre=f"Différentiel « Et si » · {libelle}", agent="Orchestrateur (code, sans LLM)",
                      outil="differentiel.comparer(analyse_origine, analyse_et_si)",
                      entrees=(f"{libelle} · origine : verdicts {ov['trace']}, point de bascule "
                               f"{origine['demande']['bascule']['trace']} · « Et si » : verdicts {nv['trace']}, "
                               f"point de bascule {nouveau['demande']['bascule']['trace']}"),
                      sortie=sortie, source="journal d'audit (analyse d'origine + analyse « Et si »)",
                      periode="exécution courante")
    return {"trace": tid, "lignes": lignes, "changements": [l["element"] for l in changes]}
