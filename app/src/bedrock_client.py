"""Le SEUL endroit qui appelle Amazon Bedrock. En MODE=local, rien n'est appelé
et les agents utilisent leur version simulée (utile pour développer sans compte AWS)."""
import json
import os
import re
import time

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
    # Pas de guardrailConfig ici : Bedrock Guardrails contrôle la DEMANDE de l'utilisateur et la RÉPONSE affichée
    # (appliquer_guardrail, src/verif/guardrails.py). Les prompts internes des agents contiennent des consignes
    # (« aucun conseil personnalisé »…) qu'un sujet refusé bloquerait à tort (faux positifs). Voir docs/decisions.md.
    rep = _bedrock().converse(**params)
    # TODO équipe : journaliser rep["usage"] (jetons) et rep["metrics"]["latencyMs"] dans CloudWatch
    # La réponse peut contenir plusieurs blocs (raisonnement, texte…) dans n'importe quel ordre :
    # on garde uniquement les blocs de texte. Le raisonnement interne n'est ni lu ni exposé.
    if rep.get("stopReason") == "max_tokens":
        raise RuntimeError(f"réponse tronquée : limite de {max_tokens} jetons atteinte")
    blocs = rep["output"]["message"]["content"]
    texte_rep = "".join(b["text"] for b in blocs if "text" in b)
    if not texte_rep:
        raise RuntimeError(f"réponse sans bloc de texte (stopReason={rep.get('stopReason')}, "
                           f"blocs={[next(iter(b)) for b in blocs]})")
    return texte_rep


def appeler_json(texte: str, modele: str = "redaction", max_tokens: int = 1500) -> dict:
    """Appelle le modèle et extrait le premier objet JSON de la réponse.
    Lève une erreur EXPLICITE si la réponse est illisible : l'appelant affiche le motif au lieu d'un repli muet."""
    brut = appeler(texte, modele, max_tokens)
    m = re.search(r"\{.*\}", brut, re.S)
    if not m:
        raise ValueError(f"aucun JSON dans la réponse (début : {brut[:80]!r})")
    try:
        return json.loads(m.group(0))
    except json.JSONDecodeError as e:
        raise ValueError(f"JSON illisible ({e.msg}, position {e.pos})") from e


def modele_strands(role: str = "analyste"):
    """Modèle Bedrock pour un agent Strands (SDK AWS). Identifiants lus dans .env, jamais dans le code.
    Modèle : BEDROCK_MODELE_<ROLE> ou, à défaut, BEDROCK_MODELE_REDACTION."""
    from strands.models import BedrockModel
    model_id = os.getenv(f"BEDROCK_MODELE_{role.upper()}") or os.environ["BEDROCK_MODELE_REDACTION"]
    params = {"model_id": model_id, "region_name": os.getenv("AWS_REGION", "us-east-1")}
    # Pas de guardrail sur les appels internes de l'Analyste (même raison que dans appeler()).
    return BedrockModel(**params)


# ---------- Bedrock Guardrails (ApplyGuardrail) ----------

def config_guardrail() -> tuple[str, str] | None:
    """(identifiant, version) lus dans .env, ou None si BEDROCK_GUARDRAIL_ID est vide.
    Version vide ou absente → DRAFT (os.getenv(..., "DRAFT") renverrait "" pour une variable vide)."""
    gid = os.getenv("BEDROCK_GUARDRAIL_ID")
    return (gid, os.getenv("BEDROCK_GUARDRAIL_VERSION") or "DRAFT") if gid else None


def guardrail_actif() -> bool:
    """Bedrock Guardrails n'est appelé qu'en MODE=bedrock ET si un guardrail est configuré."""
    return actif() and config_guardrail() is not None


def _evaluations(assessments: list) -> list[tuple[str, str, bool]]:
    """(libellé, action, détecté) de chaque élément de politique des `assessments` d'ApplyGuardrail. Code pur.
    Mode « Block » : action ≠ NONE. Mode « Detect » (aucun blocage) : action = NONE et detected = true."""
    vus = []
    for a in assessments or []:
        sujets = (a.get("topicPolicy") or {}).get("topics", [])
        vus += [(f"sujet refusé « {t.get('name')} »", t.get("action", "NONE"), t.get("detected", False)) for t in sujets]
        filtres = (a.get("contentPolicy") or {}).get("filters", [])
        vus += [(f"filtre de contenu {f.get('type')} (confiance {f.get('confidence')})", f.get("action", "NONE"),
                 f.get("detected", False)) for f in filtres]
        mots = a.get("wordPolicy") or {}
        vus += [(f"mot interdit « {w.get('match')} »", w.get("action", "NONE"), w.get("detected", False))
                for w in mots.get("customWords", []) + mots.get("managedWordLists", [])]
        sensible = a.get("sensitiveInformationPolicy") or {}
        vus += [(f"information personnelle {p.get('type')}", p.get("action", "NONE"), p.get("detected", False))
                for p in sensible.get("piiEntities", [])]
        vus += [(f"motif sensible « {r.get('name')} »", r.get("action", "NONE"), r.get("detected", False))
                for r in sensible.get("regexes", [])]
        vus += [(f"ancrage contextuel {g.get('type')}", g.get("action", "NONE"), g.get("detected", False))
                for g in (a.get("contextualGroundingPolicy") or {}).get("filters", [])]
    return vus


def politiques_declenchees(assessments: list) -> list[str]:
    """Politiques qui ont AGI (action ≠ NONE : BLOCKED, ANONYMIZED…). Sans doublons, ordre conservé."""
    return list(dict.fromkeys(lib + (f" ({act})" if act not in ("BLOCKED", "NONE") else "")
                              for lib, act, _ in _evaluations(assessments) if act != "NONE"))


def detections_sans_blocage(assessments: list) -> list[str]:
    """Politiques en mode « Detect » qui ont DÉTECTÉ le texte sans agir (action = NONE, detected = true)."""
    return list(dict.fromkeys(lib.removeprefix("sujet refusé ").strip("« »") if lib.startswith("sujet refusé") else lib
                              for lib, act, detecte in _evaluations(assessments) if act == "NONE" and detecte))


def appliquer_guardrail(texte: str, source: str) -> dict:
    """ApplyGuardrail sur un texte (source = INPUT pour la demande, OUTPUT pour la réponse affichée).
    Renvoie {action, politiques (qui ont agi), detections (mode Detect, sans blocage), id, version, latence_ms}.
    Lève l'erreur AWS telle quelle (gérée par l'appelant)."""
    gid, version = config_guardrail()
    debut = time.perf_counter()
    rep = _bedrock().apply_guardrail(guardrailIdentifier=gid, guardrailVersion=version, source=source,
                                     content=[{"text": {"text": texte}}])
    assessments = rep.get("assessments")
    return {"action": rep.get("action", "NONE"), "politiques": politiques_declenchees(assessments),
            "detections": detections_sans_blocage(assessments),
            "id": gid, "version": version, "latence_ms": round((time.perf_counter() - debut) * 1000)}
