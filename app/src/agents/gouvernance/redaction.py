"""Formulation du verdict par le LLM (MODE=bedrock, via src/bedrock_client.py). Le LLM ne JUGE pas :
- le statut est calculé par le code (regles.py) et écrase toujours celui que proposerait le LLM ;
- la consigne n'existe que si le code a jugé la demande corrigeable ;
- tout chiffre écrit par le LLM doit exister dans les traces (vérificateur de src/verif/) ;
- Bedrock en panne, JSON illisible ou chiffre introuvable → texte déterministe (repli.py) + trace « Repli Gouvernance ».
"""
import json
import re

from src import bedrock_client
from src.config import prompt
from src.formatage import pct
from src.verif import fidelite

from . import repli
from .regles import CORRIGEABLE

RE_TRACE = re.compile(r"\bT-\d+\b")      # les identifiants de trace (T-07) ne sont pas des chiffres à vérifier
MAX_TOKENS = 4000                        # marge pour les modèles à réflexion (le raisonnement consomme des jetons)


def _contexte(j: dict, persona: dict | None) -> dict:
    """Ce que le LLM reçoit : uniquement des valeurs DÉJÀ formatées par le code (aucun nombre brut)."""
    v, b = j["verdicts"], j["bascule"]
    return {
        "statut_calcule_par_le_code": j["statut"],
        "demande": j["libelle"], "symbole": j["symbole"],
        "verdicts": {"trace": v["trace"], "regles": [
            {"regle": r["regle"], "limite": r["limite"], "valeur": r["valeur"], "respectee": bool(r["ok"]),
             "information_manquante": bool(r.get("manquant"))} for r in v["regles"]]},
        "portefeuille_de_base_conforme": None if b is None else bool(b["base_conforme"]),
        "point_de_bascule": None if b is None else {
            "part_max": pct(b["part_max"]) if b["part_max"] is not None else None,
            "regles_franchies": b["limitantes"], "trace": b["trace"]},
        "consigne_de_reference": j["consigne"],
        "persona": {k: (persona or {}).get(k) for k in ("nom", "objectif", "preferences")},
        "tensions_detectees_par_le_code": j["tensions"],
    }


def _repli(journal, jugement: dict, raison: str) -> dict:
    journal.log(titre="Repli Gouvernance", agent="Agent Gouvernance", outil="formuler_verdict (LLM)",
                entrees=f"statut calculé par le code : {jugement['statut']}",
                sortie=f"{raison} → texte déterministe utilisé", source="code (repli.py)", periode="exécution courante")
    return {**repli.formuler(jugement), "auteur": f"code (repli : {raison})"}


def _lire(rep) -> dict | None:
    """Valide la forme du JSON du LLM. None si inutilisable."""
    if not isinstance(rep, dict) or not isinstance(rep.get("resume"), str) or not rep["resume"].strip():
        return None
    if rep.get("consigne") is not None and not isinstance(rep["consigne"], str):
        return None
    tensions = rep.get("tensions_profil") or []
    if not isinstance(tensions, list) or not all(isinstance(t, str) for t in tensions):
        return None
    return {"statut": rep.get("statut"), "resume": rep["resume"].strip(),
            "consigne": (rep.get("consigne") or "").strip() or None, "tensions_profil": [t.strip() for t in tensions if t.strip()]}


def formuler(journal, jugement: dict, persona: dict | None) -> dict:
    """{statut, resume, consigne, tensions_profil, auteur}. Le statut vient TOUJOURS de jugement['statut']."""
    if not bedrock_client.actif():
        return {**repli.formuler(jugement), "auteur": "code (MODE=local)"}

    ctx = _contexte(jugement, persona)
    traces = "\n".join(f"{t['id']} | {t['titre']} | entrées : {t['entrees']} | sortie : {t['sortie']}" for t in journal.traces)
    contexte_json = json.dumps(ctx, ensure_ascii=False)
    texte = prompt("gouvernance").replace("{contexte}", contexte_json).replace("{traces}", traces)
    try:
        rep = bedrock_client.appeler_json(texte, modele="redaction", max_tokens=MAX_TOKENS)
    except Exception as e:                     # identifiants, réseau, quota, modèle refusé…
        return _repli(journal, jugement, f"Bedrock indisponible ({type(e).__name__})")
    lu = _lire(rep)
    if lu is None:
        return _repli(journal, jugement, "réponse du LLM illisible (JSON attendu)")

    statut = jugement["statut"]                                    # jugement du code, jamais du LLM
    deterministe = repli.formuler(jugement)
    sortie = {
        "statut": statut,
        "resume": lu["resume"],
        "consigne": (lu["consigne"] or deterministe["consigne"]) if statut == CORRIGEABLE else None,
        # une tension détectée par le code n'est jamais perdue en route
        "tensions_profil": lu["tensions_profil"] or deterministe["tensions_profil"],
    }

    ecrit = " ".join([sortie["resume"], sortie["consigne"] or "", *sortie["tensions_profil"]])
    trouves, rejets = fidelite.chiffres_introuvables(journal, RE_TRACE.sub(" ", ecrit), contexte_json)
    if rejets:
        return _repli(journal, jugement, f"chiffre(s) introuvable(s) dans les traces : {', '.join(rejets)}")
    # Le résumé et les tensions sont lus par l'utilisateur : aucune formulation de conseil (config/garde_fous.yaml).
    # La consigne, elle, est une instruction interne à l'Analyste ; elle n'est pas soumise à ce contrôle.
    conseils = fidelite.formulations_de_conseil(" ".join([sortie["resume"], *sortie["tensions_profil"]]))
    if conseils:
        return _repli(journal, jugement, f"formulation(s) de conseil : {', '.join(conseils)}")

    note = (f" · statut proposé par le LLM « {lu['statut']} » ignoré" if lu["statut"] not in (None, statut) else "")
    journal.log(titre="Formulation Gouvernance · chiffres vérifiés", agent="Vérificateur (code, sans LLM)",
                outil="chiffres_introuvables(formulation, traces)",
                entrees=f"{len(trouves)} chiffre(s) extrait(s) de la formulation du LLM",
                sortie=f"{len(trouves)}/{len(trouves)} retrouvés dans les traces · statut calculé par le code : {statut}{note}",
                source="journal d'audit", periode="exécution courante")
    return {**sortie, "auteur": "llm"}
