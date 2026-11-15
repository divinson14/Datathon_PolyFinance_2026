import pytest

from src.config import GABARITS, PERSONAS
from src.donnees.chargeur import charger
from src.outils import calculs
from src.regles.moteur import evaluer_regles, verifier_mandat
from src.traces.journal import Journal
from src.verif import fidelite


def _mesures(vol, pire, parts):
    return {"vol": vol, "pire_baisse": pire, "parts_risque": parts, "paris_effectifs": 3.0}


def _violees(poids, mesures, gabarit, persona=None):
    _, univers, _ = charger()
    return {r["regle"] for r in evaluer_regles(poids, mesures, GABARITS[gabarit], univers, persona) if not r["ok"]}


def test_robert_30_pourcent_viole_poids_et_part_du_risque():
    poids = {"TSLA": 0.3, "XIU.TO": 0.2, "XBB.TO": 0.5}
    v = _violees(poids, _mesures(0.18, -0.28, {"TSLA": 0.9, "XIU.TO": 0.08, "XBB.TO": 0.02}), "faible_a_modere")
    assert {"Poids max par titre", "Part du risque max par titre", "Volatilité du portefeuille", "Pire baisse sur 5 ans"} <= v


def test_part_du_risque_viole_meme_si_le_poids_est_petit():
    """Cœur de la thèse : 5 % des dollars peut dépasser la limite de part du risque."""
    poids = {"TSLA": 0.05, "XIU.TO": 0.25, "XBB.TO": 0.7}
    v = _violees(poids, _mesures(0.06, -0.10, {"TSLA": 0.30, "XIU.TO": 0.5, "XBB.TO": 0.2}), "faible_a_modere")
    assert v == {"Part du risque max par titre"}


def test_fnb_non_soumis_aux_limites_par_titre():
    poids = {"XIU.TO": 0.5, "XBB.TO": 0.5}
    assert _violees(poids, _mesures(0.07, -0.10, {"XIU.TO": 0.85, "XBB.TO": 0.15}), "faible_a_modere") == set()


def test_crypto_interdite_pour_profil_prudent():
    poids = {"BTC-USD": 0.01, "XIU.TO": 0.49, "XBB.TO": 0.5}
    assert "Cryptoactifs" in _violees(poids, _mesures(0.07, -0.1, {"BTC-USD": 0.05, "XIU.TO": 0.8, "XBB.TO": 0.15}), "faible_a_modere")


def _esg_simule(monkeypatch, drapeaux: dict):
    """Données ESG simulées : le test ne dépend pas du contenu réel de data/processed/esg_drapeaux.csv."""
    import pandas as pd
    from src.regles import moteur
    monkeypatch.setattr(moteur, "charger_esg",
                        lambda: pd.DataFrame({"symbole": list(drapeaux), "controverse": list(drapeaux.values())}))


def _regle_esg(poids):
    _, univers, _ = charger()
    regles = evaluer_regles(poids, _mesures(0.07, -0.1, {s: 1 / len(poids) for s in poids}),
                            GABARITS["modere"], univers, PERSONAS["mateo"])
    return next(r for r in regles if r["regle"] == "Exclusions ESG")


def test_esg_non_evalue_signale_comme_manquant_pas_comme_conforme(monkeypatch):
    _esg_simule(monkeypatch, {"FTS.TO": "non"})                      # TSLA absent des données ESG
    esg = _regle_esg({"TSLA": 0.05, "XIU.TO": 0.45, "XBB.TO": 0.5})
    assert esg["ok"] and esg["manquant"] and "TSLA" in esg["valeur"]


def test_esg_controverse_viole_la_regle(monkeypatch):
    _esg_simule(monkeypatch, {"TSLA": "oui"})
    esg = _regle_esg({"TSLA": 0.05, "XIU.TO": 0.45, "XBB.TO": 0.5})
    assert not esg["ok"] and "TSLA" in esg["valeur"]


def test_esg_sans_controverse_conforme(monkeypatch):
    _esg_simule(monkeypatch, {"TSLA": "non"})
    esg = _regle_esg({"TSLA": 0.05, "XIU.TO": 0.45, "XBB.TO": 0.5})
    assert esg["ok"] and not esg["manquant"]


def test_portefeuilles_supposes_conformes_a_leur_profil():
    """Le portefeuille de départ de chaque persona doit respecter son propre mandat (sinon la démo est incohérente)."""
    _, univers, source = charger()
    if "FICTIVES" in source:
        pytest.skip("calibré sur les données réelles : lancer data/scripts/01_nettoyer_prix.py")
    for p in PERSONAS.values():
        base = p["portefeuille_suppose"]
        assert abs(sum(base.values()) - 1) < 1e-9
        v = verifier_mandat(Journal(), base, calculs.mesures(base), GABARITS[p["risque"]], univers, "base", p)
        assert v["violees"] == [], (p["id"], v["violees"])


def test_verificateur_rejette_un_chiffre_invente():
    j = Journal()
    j.log(titre="t", agent="a", outil="o", entrees="TSLA 30 %", sortie="rendement -25,1 %", source="s", periode="p")
    ok = {"intro": "30 %", "lignes": [{"texte": "-25,1 %"}], "limites": ""}
    faux = {"intro": "30 %", "lignes": [{"texte": "-28,2 %"}], "limites": ""}
    assert fidelite.verifier(j, ok, "", 1)["ok"]
    assert not fidelite.verifier(j, faux, "", 2)["ok"]
