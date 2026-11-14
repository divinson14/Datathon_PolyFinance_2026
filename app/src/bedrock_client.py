"""Le SEUL endroit qui appelle Amazon Bedrock. En MODE=local, rien n'est appelé
et les agents utilisent leur version simulée (utile pour développer sans compte AWS)."""
import json
import os
import re

from src.config import MODE

_client = None


def actif() -> bool:
    return MODE == "bedrock"


def _bedrock():
    global _client
    if _client is None:
        import boto3
        _client = boto3.client("bedrock-runtime", region_name=os.getenv("AWS_REGION", "us-east-1"))
    return _client


def appeler(texte: str, modele: str = "redaction", max_tokens: int = 1500) -> str:
    """Appel simple via l'API Converse. modele = 'rapide' (Profil) ou 'redaction' (Explicabilité)."""
    model_id = os.environ["BEDROCK_MODELE_RAPIDE" if modele == "rapide" else "BEDROCK_MODELE_REDACTION"]
    params = {
        "modelId": model_id,
        "messages": [{"role": "user", "content": [{"text": texte}]}],
        "inferenceConfig": {"maxTokens": max_tokens},
    }
    # Les modèles Claude récents refusent `temperature` (ValidationException « deprecated for this model »).
    # On ne l'envoie que si BEDROCK_TEMPERATURE est défini (modèles plus anciens). Le déterminisme ne repose
    # de toute façon pas sur le LLM : les chiffres viennent du code et le vérificateur contrôle le texte.
    if os.getenv("BEDROCK_TEMPERATURE"):
        params["inferenceConfig"]["temperature"] = float(os.environ["BEDROCK_TEMPERATURE"])
    if os.getenv("BEDROCK_GUARDRAIL_ID"):
        params["guardrailConfig"] = {"guardrailIdentifier": os.environ["BEDROCK_GUARDRAIL_ID"],
                                     "guardrailVersion": os.getenv("BEDROCK_GUARDRAIL_VERSION", "DRAFT")}
    rep = _bedrock().converse(**params)
    # TODO équipe : journaliser rep["usage"] (jetons) et rep["metrics"]["latencyMs"] dans CloudWatch
    # La réponse peut contenir plusieurs blocs (raisonnement, texte…) dans n'importe quel ordre :
    # on garde uniquement les blocs de texte. Le raisonnement interne n'est ni lu ni exposé.
    blocs = rep["output"]["message"]["content"]
    texte_rep = "".join(b["text"] for b in blocs if "text" in b)
    if not texte_rep:
        raise RuntimeError(f"réponse sans bloc de texte (stopReason={rep.get('stopReason')}, "
                           f"blocs={[next(iter(b)) for b in blocs]})")
    return texte_rep


def appeler_json(texte: str, modele: str = "redaction") -> dict | None:
    """Appelle le modèle et extrait le premier objet JSON de la réponse (None si illisible)."""
    brut = appeler(texte, modele)
    m = re.search(r"\{.*\}", brut, re.S)
    try:
        return json.loads(m.group(0)) if m else None
    except json.JSONDecodeError:
        return None


def guardrail_bloque(texte: str) -> bool:
    """True si Bedrock Guardrails intervient sur l'entrée."""
    if not os.getenv("BEDROCK_GUARDRAIL_ID"):
        return False
    rep = _bedrock().apply_guardrail(
        guardrailIdentifier=os.environ["BEDROCK_GUARDRAIL_ID"],
        guardrailVersion=os.getenv("BEDROCK_GUARDRAIL_VERSION", "DRAFT"),
        source="INPUT", content=[{"text": {"text": texte}}])
    return rep.get("action") == "GUARDRAIL_INTERVENED"
