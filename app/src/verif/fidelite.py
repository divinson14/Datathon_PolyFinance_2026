"""Vérificateur de fidélité : chaque chiffre écrit dans la réponse doit exister dans les traces.
Code pur, AUCUN LLM. C'est la garantie anti-hallucination."""
import re

NUM_RE = re.compile(r"\d{1,3}(?: \d{3})+(?:,\d+)?|\d+(?:,\d+)?")


def _norm(s: str) -> str:
    return f"{abs(float(s.replace(' ', '').replace(',', '.'))):.2f}"


def verifier(journal, fiche: dict, contexte_autorise: str, version: int) -> dict:
    corpus = " ".join(f"{t['entrees']} {t['sortie']}" for t in journal.traces) + " " + contexte_autorise
    autorises = {_norm(n) for n in NUM_RE.findall(corpus)}
    texte = " ".join([fiche["intro"], *[l["texte"] for l in fiche["lignes"]], fiche["limites"]])
    trouves = NUM_RE.findall(texte)
    rejets = [n for n in trouves if _norm(n) not in autorises]
    sortie = (f"{len(rejets)} chiffre(s) introuvable(s) : {', '.join(rejets)} → réponse rejetée" if rejets
              else f"{len(trouves)}/{len(trouves)} chiffres retrouvés dans les traces · 0 rejet")
    tid = journal.log(titre=f"Vérification de fidélité · version {version}", agent="Vérificateur (code, sans LLM)",
                      outil="verifier_fidelite(reponse, traces)", entrees=f"{len(trouves)} chiffres extraits de la réponse",
                      sortie=sortie, source="journal d'audit", periode="exécution courante")
    return {"trace": tid, "ok": not rejets, "total": len(trouves), "rejets": rejets}
