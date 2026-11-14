"""Agent Profil : extrait la demande. Il ne fixe AUCUN seuil (ils viennent de config/)."""
import json
import re

from src import bedrock_client
from src.config import prompt

MOTS_TRANSACTION = re.compile(r"\b(ach[eè]te[- ]?(le|la|les)?|passe (l'|un )?ordre|ex[ée]cute|vends)\b", re.I)


def demande_de_transaction(message: str) -> bool:
    """Garde-fou local, doublé par Bedrock Guardrails en mode bedrock."""
    if MOTS_TRANSACTION.search(message):
        return True
    return bedrock_client.actif() and bedrock_client.guardrail_bloque(message)


def _extraction_locale(message: str, univers) -> dict:
    symbole = None
    for _, a in univers.iterrows():
        mots = [str(a["symbole"])] + [m for m in re.split(r"\W+", str(a["nom"])) if len(m) > 3 and m[0].isupper()][:1]
        if any(re.search(rf"\b{re.escape(m)}\b", message, re.I) for m in mots):
            symbole = a["symbole"]
            break
    m = re.search(r"(\d{1,3}(?:[.,]\d+)?)\s*%", message)
    part = min(1.0, float(m.group(1).replace(",", ".")) / 100) if m else None
    manquants = [x for x, v in (("actif", symbole), ("part du portefeuille", part)) if v is None]
    return {"symbole": symbole, "part": part, "informations_manquantes": manquants}


def extraire(message: str, persona: dict, univers) -> dict:
    if not bedrock_client.actif():
        return _extraction_locale(message, univers)
    texte = (prompt("profil") + "\n\nMessage : " + message + "\nPersona : " + json.dumps(persona, ensure_ascii=False)
             + "\nSymboles de l'univers : " + ", ".join(univers["symbole"].astype(str)))
    rep = bedrock_client.appeler_json(texte, modele="rapide")
    if not rep or "symbole" not in rep:
        return _extraction_locale(message, univers)          # repli sûr si la réponse est illisible
    if rep.get("symbole") not in set(univers["symbole"]):
        rep["symbole"] = None
    return rep
