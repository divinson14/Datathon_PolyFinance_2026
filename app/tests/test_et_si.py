"""« Et si… » : une modification (tolérance, horizon, part) relancée sur une COPIE du mandat d'origine."""
import copy

import pytest

from src.orchestrateur import et_si, executer

TESLA = "Tout le monde parle de Tesla, je pense mettre 30 % dedans."


@pytest.fixture(scope="module")
def robert():
    return executer("robert", TESLA)


def _instantane(res):
    return copy.deepcopy({"mandat": res["mandat"], "traces": res["journal"].traces, "fiche": res["fiche"],
                          "verdicts": res["verdicts"]})


def _limites(res):
    g = res["gabarit"]
    return {k: v for k, v in g.items() if k not in ("id", "label")}


def test_analyse_d_origine_intacte(robert):
    avant = _instantane(robert)
    for parametre, valeur in (("tolerance", "modere"), ("part", 0.15), ("horizon", 10)):
        r = et_si(robert, parametre, valeur)
        assert r["et_si"]["parametre"] == parametre and r["origine"] is robert
        assert r["journal"] is not robert["journal"] and len(r["journal"].traces) > len(robert["journal"].traces)
    assert _instantane(robert) == avant


def test_robert_tolerance_moderee_point_de_bascule_plus_haut(robert):
    r = et_si(robert, "tolerance", "modere")
    assert r["gabarit"]["id"] == "modere" and robert["gabarit"]["id"] == "faible_a_modere"
    assert r["demande"]["bascule"]["part_max"] > robert["demande"]["bascule"]["part_max"]
    assert r["verif"]["ok"]


def test_robert_moitie_moins_nouvelle_analyse(robert):
    r = et_si(robert, "part", robert["mandat"]["demande"]["part"] / 2)
    assert r["mandat"]["demande"]["part"] == pytest.approx(0.15)
    assert r["demande"]["part"] == pytest.approx(0.15)
    assert r["gabarit"] == robert["gabarit"]
    assert r["demande"]["mesures"]["parts_risque"]["TSLA"] < robert["demande"]["mesures"]["parts_risque"]["TSLA"]


def test_robert_horizon_10_ans_limites_identiques_sans_tension(robert):
    r = et_si(robert, "horizon", 10)
    assert r["persona"]["horizon"] == "10 ans" and robert["persona"]["horizon"] == "3 à 5 ans"
    assert _limites(r) == _limites(robert)
    assert r["mandat"]["tensions"] == [] and robert["mandat"]["tensions"] == []
    assert r["demande"]["bascule"]["part_max"] == robert["demande"]["bascule"]["part_max"]


def test_profil_saisi_eleve_3_ans_horizon_10_ans_tension_retiree():
    saisie = {"age": 30, "tolerance": "eleve", "horizon_ans": 3, "objectif": "croissance", "esg": False}
    res = executer(None, "Je pense mettre 10 % dans Tesla.", profil_saisi=saisie)
    assert res["mandat"]["tensions"]
    r = et_si(res, "horizon", 10)
    assert r["mandat"]["tensions"] == []
    assert _limites(r) == _limites(res)


def test_et_si_refuse_depuis_un_autre_et_si_ou_un_arret(robert):
    r = et_si(robert, "part", 0.15)
    with pytest.raises(ValueError):
        et_si(r, "horizon", 10)
    arret = executer("robert", "Achète 10 actions Tesla pour moi.")
    assert arret["arret"]
    with pytest.raises(ValueError):
        et_si(arret, "part", 0.05)


def test_parametre_hors_liste_refuse(robert):
    with pytest.raises(ValueError):
        et_si(robert, "capital", 1)
