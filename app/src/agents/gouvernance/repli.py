"""Textes DÉTERMINISTES de l'Agent Gouvernance : utilisés en MODE=local, et en repli si Bedrock échoue
ou si le LLM écrit un chiffre absent des traces. Mêmes clés que la réponse attendue du LLM."""
from src.formatage import pct

from .regles import CONFORME, CORRIGEABLE


def _liste(violees: list[dict]) -> str:
    return " ; ".join(f"{r['regle']} : {r['valeur']} pour une limite {r['limite']}" for r in violees)


def resume(jugement: dict) -> str:
    j = jugement
    v, b, s, lib = j["verdicts"], j["bascule"], j["symbole"], j["libelle"]
    n, k = len(v["regles"]), len(v["violees"])
    manquantes = (" Information manquante : " + ", ".join(f"{r['regle']} ({r['valeur']})" for r in v["manquantes"]) + "."
                  if v["manquantes"] else "")
    if j["statut"] == CONFORME:
        return f"{lib[:1].upper() + lib[1:]} : les {n} règles du mandat sont respectées (trace {v['trace']}).{manquantes}"
    if b and not b["base_conforme"]:
        return (f"Le portefeuille actuel supposé viole déjà le mandat ({', '.join(b['limitantes'])}, trace {b['trace']}) : "
                f"aucune part de {s} ne peut rendre l'ensemble conforme. Aucune alternative n'est proposée : "
                f"il faut d'abord revoir le portefeuille de base ou le profil.{manquantes}")
    debut = f"{lib[:1].upper() + lib[1:]} : {k} règle(s) violée(s) ({_liste(v['violees'])}, trace {v['trace']})."
    if j["statut"] == CORRIGEABLE:
        if j["alternative"]:
            return debut + manquantes
        return (f"{debut} Une part plus faible de {s} respecte le mandat : point de bascule à "
                f"{pct(b['part_max'])} (trace {b['trace']}).{manquantes}")
    trace_b = f" (trace {b['trace']})" if b else ""
    return f"{debut} Aucune part de {s} n'est compatible avec le mandat{trace_b} : aucune alternative n'est proposée.{manquantes}"


def formuler(jugement: dict) -> dict:
    """Réponse complète au format attendu du LLM, entièrement produite par le code."""
    return {"statut": jugement["statut"], "resume": resume(jugement), "consigne": jugement["consigne"],
            "tensions_profil": list(jugement["tensions"])}
