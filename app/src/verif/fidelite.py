"""Vérificateur de fidélité. Code pur, AUCUN LLM. Deux contrôles sur chaque réponse :

1. Chiffres : chaque nombre écrit doit exister dans les traces (garantie anti-hallucination).
2. Formulation : aucune expression de conseil (config/garde_fous.yaml). Le système décrit des
   limites, il ne dit pas quoi faire.
Une réponse qui échoue à l'un OU l'autre est rejetée puis régénérée.
Les fonctions pures (chiffres_introuvables, formulations_de_conseil) servent aussi à l'Agent Gouvernance.
"""
import re
import unicodedata

from src.config import GARDE_FOUS

NUM_RE = re.compile(r"\d{1,3}(?: \d{3})+(?:,\d+)?|\d+(?:,\d+)?")


def _norm(s: str) -> str:
    return f"{abs(float(s.replace(' ', '').replace(',', '.'))):.2f}"


def _sans_accents(texte: str) -> str:
    return unicodedata.normalize("NFKD", texte).encode("ascii", "ignore").decode().replace("’", "'").lower()


def chiffres_introuvables(journal, texte: str, contexte_autorise: str) -> tuple[list[str], list[str]]:
    """(chiffres trouvés dans `texte`, chiffres absents des traces et du contexte autorisé). Pure : aucune trace."""
    corpus = " ".join(f"{t['entrees']} {t['sortie']}" for t in journal.traces) + " " + contexte_autorise
    autorises = {_norm(n) for n in NUM_RE.findall(corpus)}
    trouves = NUM_RE.findall(texte)
    return trouves, [n for n in trouves if _norm(n) not in autorises]


def formulations_de_conseil(texte: str) -> list[str]:
    """Expressions de conseil présentes dans le texte (mot entier, sans accents ni majuscules). Pure."""
    norm = _sans_accents(texte)
    return [e for e in GARDE_FOUS["expressions_conseil"]
            if re.search(rf"(?<![\w]){re.escape(_sans_accents(e))}(?![\w])", norm)]


def verifier(journal, fiche: dict, contexte_autorise: str, version: int) -> dict:
    texte = " ".join([fiche["intro"], *[l["texte"] for l in fiche["lignes"]], fiche["limites"]])
    trouves, rejets = chiffres_introuvables(journal, texte, contexte_autorise)
    conseils = formulations_de_conseil(texte)
    morceaux = []
    if rejets:
        morceaux.append(f"{len(rejets)} chiffre(s) introuvable(s) : {', '.join(rejets)}")
    if conseils:
        morceaux.append(f"{len(conseils)} formulation(s) de conseil : {', '.join(conseils)}")
    sortie = (" · ".join(morceaux) + " → réponse rejetée" if morceaux
              else f"{len(trouves)}/{len(trouves)} chiffres retrouvés dans les traces · 0 formulation de conseil")
    tid = journal.log(titre=f"Vérification de fidélité · version {version}", agent="Vérificateur (code, sans LLM)",
                      outil="verifier_fidelite(reponse, traces, garde_fous)",
                      entrees=f"{len(trouves)} chiffres extraits de la réponse",
                      sortie=sortie, source="journal d'audit · config/garde_fous.yaml", periode="exécution courante")
    return {"trace": tid, "ok": not rejets and not conseils, "total": len(trouves), "rejets": rejets,
            "conseils": conseils, "motif": " · ".join(morceaux)}
