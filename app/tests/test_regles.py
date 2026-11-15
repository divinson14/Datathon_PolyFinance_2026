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
    """Données ESG simulées : le test ne dépend pas du contenu réel de data/processed/esg_drapeaux.csv.
    La règle s'applique à TOUS les actifs : les FNB des tests reçoivent un statut par défaut (modifiable)."""
    import pandas as pd
    from src.regles import moteur
    drapeaux = {"XIU.TO": "conforme", "XBB.TO": "non applicable", **drapeaux}
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


def test_esg_conforme_compte_comme_sans_controverse(monkeypatch):
    _esg_simule(monkeypatch, {"TSLA": "conforme"})
    esg = _regle_esg({"TSLA": 0.05, "XIU.TO": 0.45, "XBB.TO": 0.5})
    assert esg["ok"] and not esg["manquant"] and not esg["neutre"]


def test_esg_non_applicable_neutre_seul(monkeypatch):
    """« non applicable » : ni ✅ confirmé, ni ⚠️ information manquante."""
    _esg_simule(monkeypatch, {"TSLA": "non applicable"})
    esg = _regle_esg({"TSLA": 0.05, "XBB.TO": 0.95})
    assert esg["ok"] and not esg["manquant"] and esg["neutre"]
    assert esg["valeur"] == "non applicable : TSLA, XBB.TO (portefeuille supposé)"


def test_esg_non_applicable_ignore_a_cote_d_un_titre_evalue(monkeypatch):
    _esg_simule(monkeypatch, {"TSLA": "non applicable", "FTS.TO": "non"})
    esg = _regle_esg({"TSLA": 0.05, "FTS.TO": 0.05, "XIU.TO": 0.4, "XBB.TO": 0.5})
    assert esg["ok"] and not esg["manquant"] and not esg["neutre"]
    assert esg["valeur"] == "aucune controverse relevée"


def test_esg_non_applicable_ne_masque_pas_un_manque_ni_une_controverse(monkeypatch):
    _esg_simule(monkeypatch, {"TSLA": "non applicable", "FTS.TO": "non évalué", "XOM": "oui"})
    esg = _regle_esg({"TSLA": 0.05, "FTS.TO": 0.05, "XIU.TO": 0.4, "XBB.TO": 0.5})
    assert esg["ok"] and esg["manquant"] and not esg["neutre"] and "TSLA" not in esg["valeur"]
    esg = _regle_esg({"TSLA": 0.05, "XOM": 0.05, "XIU.TO": 0.4, "XBB.TO": 0.5})
    assert not esg["ok"] and not esg["neutre"] and "XOM" in esg["valeur"]


def test_statuts_esg_des_donnees_reelles():
    """Contenu de data/processed/esg_drapeaux.csv (produit par data/scripts/02_construire_esg.py)."""
    from src.donnees.chargeur import charger_esg, donnees_fictives
    if donnees_fictives():
        import pytest
        pytest.skip("données fictives : pas de fichier ESG")
    esg = charger_esg().set_index("symbole")
    statut = esg["controverse"].to_dict()
    assert statut["ESGV"] == "conforme"
    assert all(statut[s] == "non applicable" for s in ("XBB.TO", "ZST.TO", "AGG", "TLT", "GLD"))
    assert all(statut[s] == "non évalué" for s in ("XIU.TO", "SPY", "QQQ", "BTC-USD", "ETH-USD", "JNJ"))
    oui = esg[esg["controverse"] == "oui"]
    assert set(oui.index) == {"ENB.TO", "CNQ.TO", "XOM"}
    assert oui["motif"].isin(["secteur énergie (règle de l'équipe)", "exclu par ESGV (Vanguard)"]).all()


def test_esg_s_applique_aux_fnb(monkeypatch):
    """FNB compris : « conforme » ✅, « non évalué » ⚠️ (jamais conforme), « oui » ❌."""
    _esg_simule(monkeypatch, {"FTS.TO": "non", "ESGV": "conforme", "SPY": "non évalué", "QQQ": "oui"})
    assert not _regle_esg({"FTS.TO": 0.1, "ESGV": 0.4, "XBB.TO": 0.5})["manquant"]
    esg = _regle_esg({"FTS.TO": 0.1, "SPY": 0.4, "XBB.TO": 0.5})
    assert esg["ok"] and esg["manquant"] and esg["valeur"] == "non évalué : SPY"
    assert not _regle_esg({"FTS.TO": 0.1, "QQQ": 0.4, "XBB.TO": 0.5})["ok"]


def test_esg_manque_du_portefeuille_suppose_signale_comme_tel(monkeypatch):
    """Mateo détient XIU.TO (non évalué) dans son portefeuille supposé : le manque est attribué à ce portefeuille."""
    _esg_simule(monkeypatch, {"XIU.TO": "non évalué", "TSLA": "non"})
    esg = _regle_esg({"TSLA": 0.05, "XIU.TO": 0.45, "XBB.TO": 0.5})
    assert esg["ok"] and esg["manquant"]
    assert esg["valeur"] == "non évalué : XIU.TO (portefeuille supposé)"


def test_mateo_donnees_reelles_xiu_en_information_manquante():
    """Données réelles : Mateo + Tesla → aucune violation ESG, mais XIU.TO (portefeuille supposé) non évalué."""
    from src.donnees.chargeur import donnees_fictives
    from src.orchestrateur import executer
    if donnees_fictives():
        import pytest
        pytest.skip("données fictives : pas de fichier ESG")
    res = executer("mateo", "Je veux mettre 10 % de mon portefeuille dans Tesla, mais je tiens aux critères ESG.")
    esg = next(r for r in res["verdicts"]["regles"] if r["regle"] == "Exclusions ESG")
    assert esg["ok"] and esg["manquant"] and "XIU.TO (portefeuille supposé)" in esg["valeur"]
    assert "TSLA" not in esg["valeur"] and res["verif"]["ok"]
