from src.config import GABARITS
from src.donnees.chargeur import charger
from src.regles.moteur import verifier_mandat
from src.traces.journal import Journal
from src.verif import fidelite


def _verdict(poids, rend, vol, gabarit):
    _, univers, _ = charger()
    return verifier_mandat(Journal(), poids, "TSLA", {"rend": rend}, {"vol": vol}, GABARITS[gabarit], univers, "test")


def test_robert_30_pourcent_viole_le_poids_max():
    v = _verdict({"TSLA": 0.3, "XIU": 0.42, "XBB": 0.28}, -0.25, 0.20, "faible_a_modere")
    assert {"Poids max par titre", "Volatilité du portefeuille", "Perte en 2022"} <= {r["regle"] for r in v["violees"]}


def test_alternative_conforme():
    v = _verdict({"TSLA": 0.05, "XIU": 0.57, "XBB": 0.38}, -0.11, 0.09, "faible_a_modere")
    assert v["violees"] == []


def test_verificateur_rejette_un_chiffre_invente():
    j = Journal()
    j.log(titre="t", agent="a", outil="o", entrees="TSLA 30 %", sortie="rendement -25,1 %", source="s", periode="p")
    ok = {"intro": "30 %", "lignes": [{"texte": "-25,1 %"}], "limites": ""}
    faux = {"intro": "30 %", "lignes": [{"texte": "-28,2 %"}], "limites": ""}
    assert fidelite.verifier(j, ok, "", 1)["ok"]
    assert not fidelite.verifier(j, faux, "", 2)["ok"]
