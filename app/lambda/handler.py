"""Point d'entrée AWS Lambda : emballe les outils de calcul (même code que src/outils/).
Événement attendu : {"outil": "rejeu_2022", "parametres": {...}}

Déploiement (quand le reste est stable) : zipper app/src + ce fichier + dépendances,
handler = lambda/handler.handler, rôle IAM avec lecture S3 seulement (moindre privilège)."""
import json
import os
import sys

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.outils.registre import OUTILS
from src.traces.journal import Journal


def handler(event, context):
    try:
        # Supporte aussi bien un appel direct qu'un appel via URL de fonction Lambda (body stringifié)
        if "body" in event and isinstance(event["body"], str):
            event = json.loads(event["body"])

        nom_outil = event.get("outil")
        if not nom_outil or nom_outil not in OUTILS:
            return {
                "statusCode": 400,
                "body": json.dumps({"erreur": f"Outil '{nom_outil}' introuvable dans le registre."}, ensure_ascii=False)
            }

        journal = Journal()
        outil = OUTILS[nom_outil]
        
        # Récupération sécurisée des paramètres
        parametres = event.get("parametres", {})
        if "agent" in event and "agent" not in parametres:
            parametres["agent"] = event["agent"]

        resultat = outil(journal, **parametres)
        
        return {
            "statusCode": 200,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"resultat": resultat, "traces": journal.traces}, default=str, ensure_ascii=False)
        }
        
    except Exception as e:
        return {
            "statusCode": 500,
            "headers": {"Content-Type": "application/json"},
            "body": json.dumps({"erreur interne": str(e)}, ensure_ascii=False)
        }