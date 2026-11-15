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


# ---------- Liste blanche (config/scenarios.yaml) et masquage des boutons ----------

def _options(res):
    from src.orchestrateur import options_et_si
    return {o["parametre"]: o["valeur"] for o in options_et_si(res)}


def test_boutons_robert(robert):
    assert _options(robert) == {"tolerance": "modere", "part": pytest.approx(0.15), "horizon": 10}


def test_boutons_masques_quand_sans_effet():
    amira = executer("amira", "Je pense mettre 20 % dans Nvidia.")
    assert "tolerance" not in _options(amira)             # déjà au niveau le plus élevé
    assert _options(amira)["horizon"] == 10               # « 15 ans et plus » n'inclut pas 10 ans
    mateo = executer("mateo", "Je veux mettre 10 % de mon portefeuille dans Tesla, mais je tiens aux critères ESG.")
    assert "horizon" not in _options(mateo)               # « 8 à 12 ans » inclut déjà 10 ans
    assert _options(mateo)["tolerance"] == "eleve"


def test_aucun_bouton_sous_un_et_si_ni_apres_un_arret(robert):
    assert _options(et_si(robert, "part", 0.15)) == {}
    assert _options(executer("robert", "Achète 10 actions Tesla pour moi.")) == {}


@pytest.mark.parametrize("parametre, valeur", [("tolerance", "extreme"), ("part", 0.0), ("part", 1.5),
                                               ("horizon", 0), ("horizon", 80), ("esg", True)])
def test_valeurs_hors_liste_blanche_refusees(robert, parametre, valeur):
    with pytest.raises(ValueError):
        et_si(robert, parametre, valeur)


# ---------- Différentiel (src/outils/differentiel.py) ----------

def _diff(r):
    return {l["element"]: l for l in r["differentiel"]["lignes"]}


def test_differentiel_trace_avec_avant_apres(robert):
    r = et_si(robert, "tolerance", "modere")
    trace = r["journal"].trouver(r["differentiel"]["trace"])
    assert trace["titre"].startswith("Différentiel « Et si »") and trace["agent"].startswith("Orchestrateur (code")
    d = _diff(r)
    assert d["Gabarit de tolérance"]["avant"] == "« Faible à modéré »" and d["Gabarit de tolérance"]["apres"] == "« Modéré »"
    assert d["Point de bascule"]["change"] and "Point de bascule" in r["differentiel"]["changements"]
    for l in d.values():                                  # chaque valeur citée est dans la trace
        assert l["avant"] in trace["sortie"] and l["apres"] in trace["sortie"]


def test_differentiel_horizon_seul_l_horizon_change(robert):
    r = et_si(robert, "horizon", 10)
    assert r["differentiel"]["changements"] == ["Horizon"]


def test_differentiel_moitie_moins(robert):
    r = et_si(robert, "part", 0.15)
    d = _diff(r)
    assert d["Part demandée"]["avant"] == "30 %" and d["Part demandée"]["apres"] == "15 %"
    assert not d["Gabarit de tolérance"]["change"] and not d["Point de bascule"]["change"]
