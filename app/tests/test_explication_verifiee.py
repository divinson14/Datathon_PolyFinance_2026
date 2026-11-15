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
    monkeypatch.setattr(bedrock_client, "guardrail_actif", lambda: False)
    res = executer("robert", "Je pense mettre 30 % dans Tesla.")
    assert not res["arret"] and res["verif"]["ok"] and "repli" in res["fiche"]["auteur"]


# ---------- Garde-fou anti-conseil (code pur) ----------

def test_formulations_de_conseil_detectees():
    from src.verif.fidelite import formulations_de_conseil as conseils
    assert conseils("Tu devrais mettre plutôt 3 % en Tesla.") == ["tu devrais"]
    assert "je vous recommande" in conseils("Je vous recommande de réduire.")
    assert conseils("Avec ton profil, la limite est atteinte à 3 %. Ce n'est pas un conseil financier.") == []


def test_reponse_avec_conseil_rejetee_puis_regeneree(monkeypatch):
    res = executer("robert", "Je pense mettre 30 % dans Tesla.")
    appels = {"n": 0}

    def faux_llm(*a, **k):
        appels["n"] += 1
        fiche = _fiche_llm_depuis_gabarit(res["contexte"])
        if appels["n"] == 1:                                   # 1re rédaction : chiffres justes mais un conseil
            fiche["lignes"][0]["texte"] += " Je te recommande de rester sous la limite."
        return fiche

    monkeypatch.setattr(bedrock_client, "actif", lambda: True)
    monkeypatch.setattr(bedrock_client, "appeler_json", faux_llm)
    reformuler(res, "inter")
    assert any("formulation(s) de conseil" in (e.get("note") or "") for e in res["etapes"])
    assert res["verif"]["ok"] and "recommande" not in str(res["fiche"])


def test_gabarits_sans_conseil_pour_les_trois_personas():
    from src.config import PERSONAS
    from src.verif.fidelite import formulations_de_conseil as conseils
    for pid, p in PERSONAS.items():
        res = executer(pid, p["message_exemple"])
        if res["arret"]:
            continue
        for style in ("avance", "inter"):
            f = explicabilite._gabarit_texte(res["contexte"], style)
            texte = " ".join([f["intro"], *[l["texte"] for l in f["lignes"]], f["limites"]])
            assert conseils(texte) == [], (pid, style, conseils(texte))


def test_resume_gouvernance_avec_conseil_remplace_par_le_repli(monkeypatch):
    """Le résumé de gouvernance est lu par l'utilisateur : un conseil du LLM → texte déterministe."""
    from src.agents import gouvernance
    from src.donnees.chargeur import charger
    res = executer("robert", "Je pense mettre 30 % dans Tesla.")
    monkeypatch.setattr(bedrock_client, "actif", lambda: True)
    monkeypatch.setattr(bedrock_client, "appeler_json", lambda *a, **k: {
        "statut": "corrigeable", "resume": "La demande dépasse le mandat. Je vous recommande de réduire TSLA.",
        "consigne": None, "tensions_profil": []})
    _, univers, _ = charger()
    v = gouvernance.verifier(res["journal"], res["demande"], "TSLA", res["gabarit"], univers, "test", res["persona"])
    assert v["redaction"].startswith("code (repli") and "conseil" in v["redaction"]
    assert "recommande" not in v["resume"]


def test_positions_du_persona_etiquetees_donnee_du_compte():
    """Les positions du persona sont une « Donnée du compte (fictif) » (réponse ET trace), et passent le vérificateur."""
    from src.verif import fidelite
    for pid, msg in (("robert", "Je pense mettre 30 % dans Tesla."), ("amira", "Je pense mettre 20 % dans Nvidia."),
                     ("mateo", "Je veux mettre 10 % de mon portefeuille dans Tesla, mais je tiens aux critères ESG.")):
        res = executer(pid, msg)
        for style in ("avance", "inter"):
            f = explicabilite._gabarit_texte(res["contexte"], style)
            compte = [l for l in f["lignes"] if l["tag"] == explicabilite.TAG_COMPTE]
            assert len(compte) == 1 and res["persona"]["portefeuille_suppose_libelle"] in compte[0]["texte"]
            assert compte[0]["traces"] == [res["mandat"]["trace"]]
            assert fidelite.verifier(res["journal"], f, res["autorise"], 90)["ok"], (pid, style)
        trace = res["journal"].trouver(res["mandat"]["trace"])
        assert "positions (donnée du compte, fictif)" in trace["sortie"]
