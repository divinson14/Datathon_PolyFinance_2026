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
    journal = Journal()
    outil = OUTILS[event["outil"]]
    resultat = outil(journal, **event.get("parametres", {}))
    return {"statusCode": 200, "body": json.dumps({"resultat": resultat, "traces": journal.traces}, default=str, ensure_ascii=False)}
