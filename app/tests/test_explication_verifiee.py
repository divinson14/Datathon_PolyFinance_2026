"""Aucun texte du LLM ne doit être affiché sans passer par le vérificateur de fidélité."""
from src import bedrock_client
from src.agents import explicabilite
from src.orchestrateur import executer, reformuler


def _fiche_llm_depuis_gabarit(contexte):
    """Faux LLM : renvoie le texte du gabarit (donc des chiffres justes) au format JSON attendu."""
    f = explicabilite._gabarit_texte(contexte, "avance")
    return {"intro": f["intro"], "lignes": f["lignes"], "limites": f["limites"]}


def test_reformulation_passe_par_le_verificateur(monkeypatch):
    res = executer("robert", "Je pense mettre 30 % dans Tesla.")
    appels = {"n": 0}

    def faux_llm(*a, **k):
        appels["n"] += 1
        fiche = _fiche_llm_depuis_gabarit(res["contexte"])
        if appels["n"] == 1:                                   # 1re rédaction : chiffre inventé
            fiche["lignes"][0]["texte"] += " Soit 42,7 % de hausse attendue."
        return fiche

    monkeypatch.setattr(bedrock_client, "actif", lambda: True)
    monkeypatch.setattr(bedrock_client, "appeler_json", faux_llm)
    n_etapes = len(res["etapes"])
    reformuler(res, "inter")
    nouvelles = res["etapes"][n_etapes:]
    assert any(e["agent"] == "Vérificateur de fidélité" and e["statut"] == "fail" for e in nouvelles)
    assert res["verif"]["ok"] and "42,7" not in str(res["fiche"])


def test_llm_indisponible_la_demo_continue(monkeypatch):
    def panne(*a, **k):
        raise ConnectionError("identifiants expirés")
    monkeypatch.setattr(bedrock_client, "actif", lambda: True)
    monkeypatch.setattr(bedrock_client, "appeler_json", panne)
    monkeypatch.setattr(bedrock_client, "guardrail_bloque", lambda m: False)
    res = executer("robert", "Je pense mettre 30 % dans Tesla.")
    assert not res["arret"] and res["verif"]["ok"] and "repli" in res["fiche"]["auteur"]
