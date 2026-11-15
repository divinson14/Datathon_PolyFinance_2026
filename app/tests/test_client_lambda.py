import io
import json

from botocore.credentials import Credentials

from src import config
from src.outils import client_lambda
from src.traces.journal import Journal


def test_requete_lambda_signee_avec_aws_iam(monkeypatch):
    class Session:
        def get_credentials(self):
            return Credentials("identifiant-test", "secret-test")

    def envoyer(requete, timeout):
        assert requete.full_url == "https://exemple.lambda-url.us-east-1.on.aws/"
        assert requete.get_method() == "POST"
        signature = requete.get_header("Authorization")
        assert signature.startswith("AWS4-HMAC-SHA256 ")
        assert "/us-east-1/lambda/aws4_request" in signature
        assert json.loads(requete.data) == {"outil": "contexte_macro", "parametres": {}}
        assert timeout == 30
        return io.BytesIO(b'{"ok": true}')

    monkeypatch.setattr(client_lambda.boto3, "Session", Session)
    monkeypatch.setattr(client_lambda, "urlopen", envoyer)
    monkeypatch.setenv("AWS_REGION", "us-east-1")

    assert client_lambda._poster_signe(
        "https://exemple.lambda-url.us-east-1.on.aws/",
        {"outil": "contexte_macro", "parametres": {}},
    ) == {"ok": True}


def test_appel_lambda_importe_la_trace_dans_le_journal(monkeypatch):
    monkeypatch.setattr(config, "LAMBDA_OUTILS_URL", "https://exemple.lambda-url.us-east-1.on.aws/")
    charge = {}

    def poster(url, enveloppe):
        charge.update(url=url, enveloppe=enveloppe)
        return {
            "resultat": {"trace": "T-01", "vol": 0.12},
            "traces": [{
                "id": "T-01",
                "session": "session-lambda",
                "horodatage": "2026-01-01T00:00:00+00:00",
                "titre": "Profil de risque",
                "agent": "Agent Analyste",
                "outil": 'statistiques("TSLA")',
                "entrees": "actif : TSLA",
                "sortie": "volatilité annualisée : 12 %",
                "source": "données de démonstration",
                "periode": "historique",
            }],
        }

    monkeypatch.setattr(client_lambda, "_poster_signe", poster)
    journal = Journal()
    resultat = client_lambda.appeler_outil(journal, "statistiques", {"symbole": "TSLA"}, "Agent Analyste")

    assert charge["enveloppe"] == {
        "outil": "statistiques",
        "parametres": {"symbole": "TSLA"},
        "agent": "Agent Analyste",
    }
    assert resultat == {"trace": "T-01", "vol": 0.12}
    trace = journal.trouver(resultat["trace"])
    assert trace["outil"] == 'Lambda · statistiques("TSLA")'
    assert trace["trace_lambda"] == "T-01"

    resultat_suivant = client_lambda.appeler_outil(
        journal, "statistiques", {"symbole": "TSLA"}, "Agent Analyste"
    )
    assert resultat_suivant["trace"] == "T-02"
    assert journal.trouver("T-02")["trace_lambda"] == "T-01"
