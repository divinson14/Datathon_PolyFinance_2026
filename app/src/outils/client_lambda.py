"""Client signé AWS pour appeler les outils de calcul déployés sur Lambda."""
import json
import re
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlsplit
from urllib.request import Request, urlopen

import boto3
from botocore.auth import SigV4Auth
from botocore.awsrequest import AWSRequest

from src import config


def _poster_signe(url: str, charge: dict) -> dict:
    """Envoie une requête JSON signée pour les URL Lambda protégées par AWS_IAM."""
    adresse = urlsplit(url)
    region_trouvee = re.search(r"\.lambda-url\.([a-z0-9-]+)\.on\.aws$", adresse.hostname or "")
    if adresse.scheme != "https" or region_trouvee is None:
        raise ValueError("L'URL doit être une URL de fonction AWS Lambda en HTTPS.")

    identifiants = boto3.Session().get_credentials()
    if identifiants is None:
        raise RuntimeError("Identifiants AWS absents : configure le rôle IAM ou aws configure.")

    corps = json.dumps(charge, ensure_ascii=False).encode("utf-8")
    requete = AWSRequest(
        method="POST",
        url=url,
        data=corps,
        headers={"Content-Type": "application/json"},
    )
    SigV4Auth(
        identifiants.get_frozen_credentials(),
        "lambda",
        region_trouvee.group(1),
    ).add_auth(requete)
    preparee = requete.prepare()
    demande = Request(
        preparee.url,
        data=preparee.body,
        headers=dict(preparee.headers.items()),
        method="POST",
    )

    try:
        with urlopen(demande, timeout=30) as reponse:
            contenu = reponse.read().decode("utf-8")
    except HTTPError as erreur:
        detail = erreur.read().decode("utf-8", errors="replace")
        raise RuntimeError(f"Réponse HTTP {erreur.code} de Lambda : {detail[:500]}") from erreur
    except URLError as erreur:
        raise RuntimeError(f"Impossible de joindre Lambda : {erreur.reason}") from erreur

    try:
        resultat = json.loads(contenu)
    except json.JSONDecodeError as erreur:
        raise RuntimeError("Lambda a renvoyé une réponse JSON illisible.") from erreur
    if not isinstance(resultat, dict):
        raise RuntimeError("Lambda a renvoyé une réponse qui n'est pas un objet JSON.")
    return resultat


def appeler_outil(journal: Any, outil: str, parametres: dict, agent: str) -> dict:
    """Appelle un outil Lambda et importe ses traces dans le journal de la session."""
    if not config.LAMBDA_OUTILS_URL:
        raise RuntimeError("L'URL des outils Lambda n'est pas configurée.")

    enveloppe = _poster_signe(
        config.LAMBDA_OUTILS_URL,
        {"outil": outil, "parametres": parametres, "agent": agent},
    )
    resultat = enveloppe.get("resultat")
    traces = enveloppe.get("traces")
    if not isinstance(resultat, dict) or not isinstance(traces, list):
        raise RuntimeError("Réponse Lambda invalide : résultat ou traces manquants.")

    identifiants_locaux = {}
    for trace_distante in traces:
        if not isinstance(trace_distante, dict):
            raise RuntimeError("Réponse Lambda invalide : une trace n'est pas un objet JSON.")
        identifiant_distant = trace_distante.get("id")
        champs = {
            cle: valeur
            for cle, valeur in trace_distante.items()
            if cle not in {"id", "session", "horodatage"}
        }
        champs["outil"] = f"Lambda · {champs.get('outil', 'outil de calcul')}"
        champs["trace_lambda"] = identifiant_distant
        champs["horodatage_lambda"] = trace_distante.get("horodatage")
        identifiants_locaux[identifiant_distant] = journal.log(**champs)

    identifiant_resultat = resultat.get("trace")
    if identifiant_resultat is not None:
        if identifiant_resultat not in identifiants_locaux:
            raise RuntimeError("La trace du résultat Lambda est absente de la réponse.")
        resultat["trace"] = identifiants_locaux[identifiant_resultat]
    return resultat
