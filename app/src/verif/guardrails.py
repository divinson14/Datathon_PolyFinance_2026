"""Amazon Bedrock Guardrails : contrôle de la DEMANDE (source=INPUT) et de la RÉPONSE affichée (source=OUTPUT).

Code d'orchestration, sans LLM. L'appel AWS passe par bedrock_client (point d'appel unique à Bedrock).
- Guardrails n'est appelé qu'en MODE=bedrock ET si BEDROCK_GUARDRAIL_ID est défini ; sinon statut « local ».
- Chaque contrôle écrit une trace « Bedrock Guardrails » : action (NONE / GUARDRAIL_INTERVENED), politiques
  déclenchées (lues dans les assessments), identifiant et version du guardrail, latence.
- Si l'API échoue (droits, réseau…) : pas de plantage, trace « Guardrails indisponible » ; le garde-fou local
  (regex de l'Agent Profil, vérificateur de fidélité) reste en place.
Statuts renvoyés : bloque | admis | indisponible | local.
"""
from src import bedrock_client

INTERVENU = "GUARDRAIL_INTERVENED"
QUOI = {"INPUT": "demande", "OUTPUT": "réponse"}


def controler(journal, texte: str, source: str) -> dict:
    """Applique le guardrail à `texte`. Renvoie {statut, politiques, trace, detail}."""
    if not bedrock_client.guardrail_actif():
        return {"statut": "local", "politiques": [], "detections": [], "trace": None,
                "detail": "Bedrock Guardrails non configuré (MODE=local ou BEDROCK_GUARDRAIL_ID vide)"}
    gid, version = bedrock_client.config_guardrail()
    quoi = QUOI.get(source, source)
    try:
        r = bedrock_client.appliquer_guardrail(texte, source)
    except Exception as e:                       # droits IAM, réseau, guardrail inexistant… : la démo continue
        detail = f"{type(e).__name__} : {str(e)[:160]}"
        tid = journal.log(titre="Guardrails indisponible", agent="Bedrock Guardrails",
                          outil=f"ApplyGuardrail(source={source})", entrees=f"{quoi} · guardrail {gid} version {version}",
                          sortie=f"erreur {detail} → garde-fou local seulement",
                          source="Amazon Bedrock Guardrails", periode="exécution courante", controle=True)
        return {"statut": "indisponible", "politiques": [], "detections": [], "trace": tid, "detail": detail}
    bloque = r["action"] == INTERVENU
    politiques = r["politiques"] or (["politique non précisée"] if bloque else [])
    detections = r.get("detections") or []
    sortie = (f"action : {r['action']} · politiques déclenchées : {' ; '.join(politiques) if politiques else 'aucune'}"
              + (f" · {libelle_detections(detections)} (mode Detect, sans blocage)" if detections else "")
              + f" · latence {r['latence_ms']} ms")
    tid = journal.log(titre=f"Bedrock Guardrails · {quoi}", agent="Bedrock Guardrails",
                      outil=f"ApplyGuardrail(source={source})",
                      entrees=f"{quoi} ({len(texte)} caractères) · guardrail {r['id']} version {r['version']}",
                      sortie=sortie, source="Amazon Bedrock Guardrails (ApplyGuardrail)", periode="exécution courante",
                      controle=True)
    return {"statut": "bloque" if bloque else "admis", "politiques": politiques, "detections": detections,
            "trace": tid, "detail": f"guardrail {r['id']} version {r['version']}"}


def libelle_detections(detections: list[str]) -> str:
    """« détecté par Bedrock Guardrails : Transaction-reelle » (politiques en mode Detect, sans blocage)."""
    return "détecté par Bedrock Guardrails : " + ", ".join(detections)


def portee(g: dict) -> str:
    """Ce qui a réellement été vérifié, en clair, pour l'étape affichée à droite."""
    return {"admis": "vérifié par Bedrock Guardrails",
            "bloque": "bloqué par Bedrock Guardrails",
            "indisponible": "garde-fou local seulement (Bedrock Guardrails indisponible)",
            "local": "garde-fou local seulement"}[g["statut"]]


def texte_fiche(fiche: dict) -> str:
    """Texte réellement affiché d'une réponse de l'Explicabilité (intro, affirmations, limites)."""
    return "\n".join([fiche["intro"], *[l["texte"] for l in fiche["lignes"]], fiche["limites"]])


def fiche_remplacement(fiche: dict, politiques: list[str]) -> dict:
    """Message SÛR affiché à la place d'une réponse retenue par le guardrail (aucun chiffre, aucun conseil)."""
    return {"intro": "Cette réponse a été retenue par Bedrock Guardrails et n'est pas affichée "
                     f"({' ; '.join(politiques)}).",
            "lignes": [],
            "limites": "Simulation uniquement : aucune transaction réelle, aucun conseil financier personnalisé. "
                       "Les calculs et les verdicts restent consultables dans le journal d'audit.",
            "style": fiche.get("style"), "auteur": "Bedrock Guardrails (réponse retenue)"}
