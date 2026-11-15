"""« Et si j'acceptais plus de risque ? » : executer() relancé sur une COPIE du profil (tolérance au niveau suivant)."""
import copy

from src import config
from src.orchestrateur import executer, plus_de_risque


def test_plus_de_risque_mandat_d_origine_intact():
    res = executer("robert", "Tout le monde parle de Tesla, je pense mettre 30 % dedans.")
    avant = copy.deepcopy({"mandat": res["mandat"], "traces": res["journal"].traces, "fiche": res["fiche"]})
    persona_avant = copy.deepcopy(config.PERSONAS["robert"])

    n = plus_de_risque(res)

    # analyse, mandat, journal d'origine et persona de référence : inchangés
    assert copy.deepcopy({"mandat": res["mandat"], "traces": res["journal"].traces, "fiche": res["fiche"]}) == avant
    assert config.PERSONAS["robert"] == persona_avant
    assert n["journal"] is not res["journal"] and n["mandat"] is not res["mandat"]
    # le scénario : tolérance suivante, même demande, bandeau écrit par le code à partir des deux points de bascule
    assert res["gabarit"]["id"] == "faible_a_modere" and n["gabarit"]["id"] == "modere"
    assert n["mandat"]["demande"]["part"] == res["mandat"]["demande"]["part"]
    assert n["demande"]["bascule"]["part_max"] > res["demande"]["bascule"]["part_max"]
    assert n["scenario_fictif"] == ("Scénario fictif — tolérance « Modéré » au lieu de « Faible à modéré » : "
                                    "part acceptable 3 % → 4 %")
    assert n["verif"]["ok"]
