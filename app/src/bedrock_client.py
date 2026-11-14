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
        "inferenceConfig": {"maxTokens": max_tokens, "temperature": 0},
    }
    if os.getenv("BEDROCK_GUARDRAIL_ID"):
        params["guardrailConfig"] = {"guardrailIdentifier": os.environ["BEDROCK_GUARDRAIL_ID"],
                                     "guardrailVersion": os.getenv("BEDROCK_GUARDRAIL_VERSION", "DRAFT")}
    rep = _bedrock().converse(**params)
    # TODO équipe : journaliser rep["usage"] (jetons) et rep["metrics"]["latencyMs"] dans CloudWatch
    return rep["output"]["message"]["content"][0]["text"]


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
