"""Bedrock Guardrails (entrée et sortie) testé SANS AWS : un faux client remplace bedrock-runtime.
Seul le guardrail est « actif » ; les agents restent en mode local."""
import pytest

from src import bedrock_client
from src.orchestrateur import executer
from src.traces.journal import Journal
from src.verif import fidelite

LEGITIME = "Je pense mettre 30 % dans Tesla."
NONE = {"action": "NONE", "assessments": []}
SUJET_REFUSE = {"action": "GUARDRAIL_INTERVENED", "outputs": [{"text": "Bloqué."}], "assessments": [
    {"topicPolicy": {"topics": [{"name": "Transactions réelles", "type": "DENY", "action": "BLOCKED"}]}}]}
FILTRE = {"action": "GUARDRAIL_INTERVENED", "assessments": [
    {"contentPolicy": {"filters": [{"type": "MISCONDUCT", "confidence": "HIGH", "action": "BLOCKED"}]}}]}


class FauxClient:
    """Imite bedrock-runtime.apply_guardrail : une réponse (ou une erreur) par source INPUT / OUTPUT."""

    def __init__(self, reponses):
        self.reponses, self.appels = reponses, []

    def apply_guardrail(self, **kw):
        self.appels.append(kw)
        r = self.reponses[kw["source"]]
        if isinstance(r, Exception):
            raise r
        return r


@pytest.fixture
def guardrail(monkeypatch):
    """Active un guardrail factice (ID défini, version vide → DRAFT) et renvoie une fonction pour installer le client."""
    monkeypatch.setenv("BEDROCK_GUARDRAIL_ID", "gr-test")
    monkeypatch.setenv("BEDROCK_GUARDRAIL_VERSION", "")
    monkeypatch.setattr(bedrock_client, "guardrail_actif", lambda: True)

    def installer(entree, sortie=NONE):
        faux = FauxClient({"INPUT": entree, "OUTPUT": sortie})
        monkeypatch.setattr(bedrock_client, "_bedrock", lambda: faux)
        return faux
    return installer


def _trace(res, titre):
    return next(t for t in res["journal"].traces if t["titre"].startswith(titre))


def test_entree_bloquee_par_guardrail_arret(guardrail):
    faux = guardrail(SUJET_REFUSE)
    res = executer("robert", LEGITIME)
    assert res["arret"]
    e = res["etapes"][-1]
    assert e["agent"] == "Bedrock Guardrails" and e["statut"] == "fail"
    assert e["texte"].startswith("Demande bloquée par Bedrock Guardrails : sujet refusé « Transactions réelles »")
    t = _trace(res, "Bedrock Guardrails · demande")
    assert "GUARDRAIL_INTERVENED" in t["sortie"] and "latence" in t["sortie"]
    assert "gr-test version DRAFT" in t["entrees"] and t["id"] == e["trace"]
    assert [a["source"] for a in faux.appels] == ["INPUT"] and faux.appels[0]["guardrailVersion"] == "DRAFT"


def test_sortie_bloquee_message_sur(guardrail):
    faux = guardrail(NONE, FILTRE)
    res = executer("robert", LEGITIME)
    assert not res["arret"]
    assert res["etapes"][0]["texte"].endswith("vérifié par Bedrock Guardrails")
    f = res["fiche"]
    assert f["auteur"].startswith("Bedrock Guardrails") and f["lignes"] == []
    assert "filtre de contenu MISCONDUCT" in f["intro"]
    assert not fidelite.NUM_RE.findall(f["intro"] + f["limites"])            # aucun chiffre dans le message sûr
    sortie = [e for e in res["etapes"] if e["agent"] == "Bedrock Guardrails" and e["statut"] == "fail"]
    assert sortie and sortie[0]["texte"].startswith("Réponse retenue par Bedrock Guardrails")
    assert "GUARDRAIL_INTERVENED" in _trace(res, "Bedrock Guardrails · réponse")["sortie"]
    assert [a["source"] for a in faux.appels] == ["INPUT", "OUTPUT"]


def test_api_en_erreur_repli_sur_le_garde_fou_local(guardrail):
    guardrail(PermissionError("AccessDeniedException"), PermissionError("AccessDeniedException"))
    res = executer("robert", LEGITIME)
    assert not res["arret"] and res["verif"]["ok"]                          # pas de plantage
    e = res["etapes"][0]
    assert e["agent"] == "Garde-fou local" and e["statut"] == "warn"
    assert "garde-fou local seulement (Bedrock Guardrails indisponible)" in e["texte"]
    assert "AccessDeniedException" in _trace(res, "Guardrails indisponible")["sortie"]
    assert res["fiche"]["auteur"] != "Bedrock Guardrails (réponse retenue)"
    # le garde-fou local bloque toujours une transaction réelle
    bloque = executer("robert", "Achète-le pour moi : 30 % de Tesla.")
    assert bloque["arret"] and bloque["etapes"][-1]["texte"].startswith("Demande bloquée")


def test_entree_et_sortie_admises(guardrail):
    faux = guardrail(NONE, NONE)
    res = executer("robert", LEGITIME)
    assert not res["arret"] and res["etapes"][0]["statut"] == "ok"
    assert "action : NONE" in _trace(res, "Bedrock Guardrails · demande")["sortie"]
    assert any(e["texte"] == "Réponse vérifiée par Bedrock Guardrails avant affichage" for e in res["etapes"])
    assert len(faux.appels) == 2


def test_sans_guardrail_garde_fou_local_seulement(monkeypatch):
    monkeypatch.setattr(bedrock_client, "_bedrock", lambda: pytest.fail("Bedrock ne doit pas être appelé"))
    res = executer("robert", LEGITIME)
    assert res["etapes"][0]["agent"] == "Garde-fou local"
    assert res["etapes"][0]["texte"].endswith("garde-fou local seulement")
    assert not any("Guardrails" in t["titre"] for t in res["journal"].traces)


def test_politiques_lues_dans_les_assessments():
    assessments = [{
        "topicPolicy": {"topics": [{"name": "Conseil personnalisé", "action": "BLOCKED"},
                                   {"name": "Autre", "action": "NONE"}]},
        "contentPolicy": {"filters": [{"type": "PROMPT_ATTACK", "confidence": "HIGH", "action": "BLOCKED"}]},
        "wordPolicy": {"customWords": [{"match": "garanti", "action": "BLOCKED"}], "managedWordLists": []},
        "sensitiveInformationPolicy": {"piiEntities": [{"type": "EMAIL", "match": "x@y.z", "action": "ANONYMIZED"}]},
    }]
    assert bedrock_client.politiques_declenchees(assessments) == [
        "sujet refusé « Conseil personnalisé »", "filtre de contenu PROMPT_ATTACK (confiance HIGH)",
        "mot interdit « garanti »", "information personnelle EMAIL (ANONYMIZED)"]
    assert bedrock_client.politiques_declenchees([]) == []


def test_chiffres_des_traces_guardrails_jamais_acceptes_par_le_verificateur():
    j = Journal()
    j.log(titre="Bedrock Guardrails · demande", agent="Bedrock Guardrails", outil="ApplyGuardrail(source=INPUT)",
          entrees="demande", sortie="action : NONE · latence 4321 ms", source="s", periode="p", controle=True)
    _, rejets = fidelite.chiffres_introuvables(j, "Un rendement de 4321 %.", "")
    assert rejets == ["4321"]


# ---------- Mode « Detect » en entrée (sujets refusés détectés sans blocage) ----------

DETECTE = {"action": "NONE", "assessments": [
    {"topicPolicy": {"topics": [{"name": "Transaction-reelle", "type": "DENY", "action": "NONE", "detected": True}]}}]}


def test_detect_ordre_reel_bloque_par_la_regle_en_code(guardrail):
    guardrail(DETECTE)
    res = executer("robert", "Achète-le pour moi.")
    assert res["arret"]
    e = res["etapes"][-1]
    assert e["agent"] == "Garde-fou local" and e["texte"].startswith("Demande bloquée")
    assert "détecté par Bedrock Guardrails : Transaction-reelle" in e["note"]
    t = _trace(res, "Bedrock Guardrails · demande")
    assert "action : NONE" in t["sortie"] and "détecté par Bedrock Guardrails : Transaction-reelle" in t["sortie"]


def test_detect_simulation_legitime_admise(guardrail):
    guardrail(DETECTE, NONE)
    res = executer("robert", "Je veux mettre 10 % dans Tesla.")
    assert not res["arret"]
    e = res["etapes"][0]
    assert e["statut"] == "ok" and e["texte"].endswith("vérifié par Bedrock Guardrails")
    assert "détecté par Bedrock Guardrails : Transaction-reelle" in e["note"]


def test_detections_lues_dans_les_assessments():
    assert bedrock_client.detections_sans_blocage(DETECTE["assessments"]) == ["Transaction-reelle"]
    assert bedrock_client.politiques_declenchees(DETECTE["assessments"]) == []
    assert bedrock_client.detections_sans_blocage(SUJET_REFUSE["assessments"]) == []
