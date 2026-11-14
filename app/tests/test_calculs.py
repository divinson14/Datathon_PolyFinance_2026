import math

import pytest

from src.config import GABARITS, PERSONAS
from src.donnees.chargeur import charger
from src.formatage import money, nombre, pct
from src.outils import calculs
from src.traces.journal import Journal

BASE = {"XIU.TO": 0.6, "XBB.TO": 0.4}


def test_formatage():
    assert pct(-0.2512) == "-25,1 %"
    assert pct(0.30, 0) == "30 %"
    assert money(-50213) == "-50 200 $"
    assert nombre(0.8354, 2) == "0,84"


def test_poids_avec_position_somme_a_un():
    p = calculs.poids_avec_position(BASE, "TSLA", 0.3)
    assert abs(sum(p.values()) - 1) < 1e-9 and abs(p["TSLA"] - 0.3) < 1e-9


def test_parts_du_risque_somment_a_un():
    m = calculs.mesures(calculs.poids_avec_position(BASE, "TSLA", 0.1))
    assert math.isclose(sum(m["parts_risque"].values()), 1.0, abs_tol=1e-9)


def test_titre_volatil_porte_plus_de_risque_que_de_dollars():
    m = calculs.mesures(calculs.poids_avec_position(BASE, "TSLA", 0.1))
    assert m["parts_risque"]["TSLA"] > 0.1


def test_paris_effectifs_bornes():
    m = calculs.mesures({"XIU.TO": 0.25, "XBB.TO": 0.25, "GLD": 0.25, "TSLA": 0.25})
    assert 1.0 <= m["paris_effectifs"] <= 4.0
    assert math.isclose(calculs.mesures({"SPY": 1.0})["paris_effectifs"], 1.0)


def test_pire_baisse_negative_et_vol_augmente_avec_tesla():
    m0 = calculs.mesures(BASE)
    m1 = calculs.mesures(calculs.poids_avec_position(BASE, "TSLA", 0.3))
    assert m0["pire_baisse"] <= 0 and m1["vol"] > m0["vol"]


def test_rejeu_et_traces():
    j = Journal()
    r = calculs.rejeu_2022(j, BASE, 200000, "test", "test")
    assert len(r["valeurs"]) == 13 and r["trace"] == "T-01"
    assert abs(r["perte"] - (r["final"] - 200000)) < 1e-6


def test_point_de_bascule_coherent_avec_les_regles():
    """À part_max toutes les règles passent ; un pas plus loin, au moins une casse."""
    from src.regles.moteur import evaluer_regles
    _, univers, _ = charger()
    p = PERSONAS["robert"]
    g = GABARITS[p["risque"]]
    b = calculs.point_de_bascule(Journal(), p["portefeuille_suppose"], "TSLA", g, univers, "t", p)
    if not b["base_conforme"]:
        pytest.skip("portefeuille de base non conforme sur ces données (démo fictive ?)")
    assert b["base_conforme"] and b["part_max"] is not None and b["part_max"] < 0.30
    def violees(x):
        poids = calculs.poids_avec_position(p["portefeuille_suppose"], "TSLA", x)
        return [r for r in evaluer_regles(poids, calculs.mesures(poids), g, univers, p) if not r["ok"]]
    assert violees(b["part_max"]) == []
    assert violees(b["part_max"] + 0.005) != []


def test_bascule_nulle_pour_crypto_si_interdite():
    _, univers, _ = charger()
    p = PERSONAS["robert"]
    b = calculs.point_de_bascule(Journal(), p["portefeuille_suppose"], "BTC-USD", GABARITS[p["risque"]], univers, "t", p)
    assert not b["part_max"] and "Cryptoactifs" in b["premiere_violation"]
    assert b["premiere_violation"]["Cryptoactifs"] <= 0.005
