import pytest

from src import bedrock_client
from src.agents import profil
from src.config import PERSONAS
from src.donnees.chargeur import charger
from src.traces.journal import Journal

ROBERT = PERSONAS["robert"]          # capital 200 000 $
_, UNIVERS, _ = charger()


def ext(message, persona=ROBERT, journal=None):
    return profil.extraire(message, persona, UNIVERS, journal)


@pytest.mark.parametrize("message, symbole, part", [
    ("Je pense mettre 30 % dans Tesla.", "TSLA", 0.30),
    ("Tesla à 30%", "TSLA", 0.30),
    ("Et 3,5 % de TSLA ?", "TSLA", 0.035),
    ("10 pour cent en Nvidia", "NVDA", 0.10),
    ("5 % de Bitcoin", "BTC-USD", 0.05),
    ("Je veux 10 % dans l'or", "GLD", 0.10),
    ("Et si je mettais 20 % sur le Nasdaq ?", "QQQ", 0.20),
])
def test_extraction_actif_et_pourcentage(message, symbole, part):
    r = ext(message)
    if symbole not in set(UNIVERS["symbole"]):
        pytest.skip("actif absent des données de démo")
    assert r["symbole"] == symbole and r["part"] == pytest.approx(part) and r["informations_manquantes"] == []


def test_montant_converti_par_le_code():
    r = ext("Je voudrais placer 50 000 $ dans Tesla.")
    assert r["part"] == pytest.approx(0.25) and r["lecture"]["type"] == "montant"


def test_montant_egal_au_capital_n_est_pas_une_part():
    r = ext("J'ai 200 000 $ de côté, je pense à Tesla.")
    assert r["part"] is None and "part du portefeuille" in r["informations_manquantes"]


def test_pourcentage_prioritaire_sur_le_capital_cite():
    r = ext(ROBERT["message_exemple"])        # « J'ai 200 000 $ … mettre 30 % dedans »
    assert r["symbole"] == "TSLA" and r["part"] == pytest.approx(0.30)


def test_part_manquante_pose_une_question():
    r = ext("Je veux investir dans Tesla.")
    assert r["part"] is None and r["question"]


def test_plusieurs_actifs_ambigus():
    r = ext("Je veux mettre 10 % dans Tesla ou dans Nvidia.")
    assert r["symbole"] is None and "actif à analyser" in r["informations_manquantes"]


def test_part_superieure_a_100_refusee():
    r = ext("Je mets 150 % dans Tesla.")
    assert r["part"] is None and "part valide" in r["informations_manquantes"]


def test_mots_courants_pas_pris_pour_des_tickers():
    """« or » (conjonction), « td » ou « pg » en minuscules ne doivent pas déclencher un actif."""
    assert profil.actifs_mentionnes("or je pense que td et pg, c'est flou", UNIVERS) == []


def test_extraction_tracee():
    j = Journal()
    r = ext("Je voudrais placer 50 000 $ dans Tesla.", journal=j)
    t = j.trouver(r["trace"])
    assert t["titre"] == "Extraction de la demande" and "25 %" in t["sortie"] and "50 000 $" in t["sortie"]


def _faux_llm(monkeypatch, reponse):
    monkeypatch.setattr(bedrock_client, "actif", lambda: True)
    monkeypatch.setattr(bedrock_client, "appeler_json", lambda *a, **k: reponse)


def test_llm_chiffre_invente_rejete(monkeypatch):
    """Le LLM « recopie » un extrait qui n'est pas dans le message : rejeté, la part vient du code."""
    _faux_llm(monkeypatch, {"symbole": "TSLA", "symboles_mentionnes": ["TSLA"], "extrait_part": "25 %"})
    r = ext("Je veux mettre un tiers de mon argent dans le constructeur d'Elon Musk.")
    assert r["symbole"] == "TSLA" and r["part"] is None and "ABSENT" in r["methode"]


def test_llm_periphrase_acceptee(monkeypatch):
    _faux_llm(monkeypatch, {"symbole": "TSLA", "symboles_mentionnes": ["TSLA"], "extrait_part": "15 %"})
    r = ext("Je veux 15 % dans le constructeur de voitures électriques d'Elon Musk.")
    assert r["symbole"] == "TSLA" and r["part"] == pytest.approx(0.15)


def test_llm_symbole_hors_univers_ignore(monkeypatch):
    _faux_llm(monkeypatch, {"symbole": "BBD-B.TO", "symboles_mentionnes": ["BBD-B.TO"], "extrait_part": "10 %"})
    r = ext("Je veux 10 % dans Bombardier.")
    assert r["symbole"] is None and "actif" in r["informations_manquantes"]


# ---------- Mandat ----------

def test_mandat_persona_reprend_le_gabarit_de_config():
    from src.config import GABARITS
    m = profil.construire_mandat("robert")
    assert m["gabarit"]["volatilite_max"] == GABARITS["faible_a_modere"]["volatilite_max"]
    assert m["horizon_ans"] == {"min": 3.0, "max": 5.0} and not m["bloquant"] and m["tensions"] == []
    assert m["contraintes"]["exclusions_esg"] is False and profil.construire_mandat("mateo")["contraintes"]["exclusions_esg"]


def test_mandat_tolerance_jamais_deduite():
    m = profil.construire_mandat(saisie={"age": 26, "horizon_ans": 20, "objectif": "croissance"})
    assert m["bloquant"] and m["gabarit"] is None and "tolérance au risque" in m["informations_manquantes"]


def test_mandat_tension_horizon_court_signalee_pas_corrigee():
    m = profil.construire_mandat(saisie={"tolerance": "eleve", "horizon_ans": 3, "age": 30, "objectif": "x"})
    assert m["tensions"] and m["gabarit"]["id"] == "eleve"          # signalé, la tolérance reste celle saisie


def test_mandat_hypotheses_affichees_pour_profil_saisi():
    m = profil.construire_mandat(saisie={"tolerance": "modere", "horizon_ans": 10})
    assert m["profil"]["capital"] > 0 and any("capital fictif" in h for h in m["hypotheses"])
    assert {"âge", "objectif"} <= set(m["informations_manquantes"]) and not m["bloquant"]


def test_mandat_trace():
    j = Journal()
    m = profil.construire_mandat("amira", journal=j)
    assert j.trouver(m["trace"])["titre"] == "Construction du mandat"


def test_portefeuilles_types_conformes_a_leur_gabarit():
    from src.config import GABARITS, PROFIL
    from src.outils import calculs
    from src.regles.moteur import verifier_mandat
    _, univers, source = charger()
    if "FICTIVES" in source:
        pytest.skip("calibré sur les données réelles")
    for tol, pf in PROFIL["portefeuilles_types"].items():
        assert abs(sum(pf["poids"].values()) - 1) < 1e-9
        v = verifier_mandat(Journal(), pf["poids"], calculs.mesures(pf["poids"]), GABARITS[tol], univers, "type")
        assert v["violees"] == [], tol


def test_llm_indisponible_repli_local(monkeypatch):
    def panne(*a, **k):
        raise ConnectionError("Bedrock injoignable")
    monkeypatch.setattr(bedrock_client, "actif", lambda: True)
    monkeypatch.setattr(bedrock_client, "appeler_json", panne)
    r = ext("Je pense mettre 30 % dans Tesla.")
    assert r["symbole"] == "TSLA" and r["part"] == pytest.approx(0.30) and "repli" in r["methode"]


def test_bedrock_client_ignore_les_blocs_non_texte(monkeypatch):
    """Les modèles récents peuvent renvoyer un bloc de raisonnement AVANT le texte."""
    class FauxClient:
        def converse(self, **params):
            return {"output": {"message": {"content": [{"reasoningContent": {"reasoningText": {"text": "…"}}},
                                                       {"text": '{"symbole": "TSLA"}'}]}}, "stopReason": "end_turn"}
    monkeypatch.setenv("BEDROCK_MODELE_RAPIDE", "faux")
    monkeypatch.setattr(bedrock_client, "_bedrock", lambda: FauxClient())
    assert bedrock_client.appeler("x", modele="rapide") == '{"symbole": "TSLA"}'
