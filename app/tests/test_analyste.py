"""Agent Analyste (Strands) testé SANS appel AWS : un faux agent remplace _creer_agent
et appelle les outils comme le ferait le modèle."""
import pytest

from src import config
from src.agents import analyste
from src.config import GABARITS, PERSONAS
from src.donnees.chargeur import charger
from src.outils import calculs
from src.traces.journal import Journal

CLES = {"poids", "part", "stats", "macro", "mesures_base", "mesures", "vol", "bascule", "base", "rejeu",
        "extras", "raisonnement"}
PERSONA = PERSONAS["robert"]
GABARIT = GABARITS[PERSONA["risque"]]


class FauxAgent:
    """Imite strands.Agent : appelé avec la consigne, il exécute un « plan » d'appels d'outils et renvoie un texte."""

    def __init__(self, outils, plan, texte):
        self.outils = {o.tool_name: o for o in outils}
        self.plan, self.texte = plan, texte

    def __call__(self, consigne):
        for nom, *args in self.plan:
            self.outils[nom](*args)
        return self.texte


@pytest.fixture
def strands(monkeypatch):
    """Active le mode Strands et renvoie une fonction pour installer le faux agent."""
    monkeypatch.setattr(config, "MODE", "bedrock")
    monkeypatch.setattr(config, "ANALYSTE", "strands")

    def installer(plan, texte="Outils appelés.\nPART=0.3"):
        monkeypatch.setattr(analyste, "_creer_agent", lambda outils: FauxAgent(outils, plan, texte))
    return installer


def _demande(journal, part=0.30):
    _, univers, _ = charger()
    return analyste.analyser_demande(journal, PERSONA, "TSLA", part, GABARIT, univers)


def _agent_de(journal, tid):
    return journal.trouver(tid)["agent"]


def test_plan_fixe_en_mode_local():
    d = _demande(Journal())
    assert set(d) == CLES and d["extras"] == [] and d["raisonnement"] == ""


def test_mode_strands_cles_et_stress_test(strands):
    strands([("statistiques_actif",), ("contexte_taux_2022",), ("rejeu_2022", 0), ("volatilite_portefeuille", 0),
             ("rejeu_2022", 0.3), ("volatilite_portefeuille", 0.3), ("pire_fenetre_12_mois", 0.3)])
    j = Journal()
    d = _demande(j)
    assert set(d) == CLES
    assert d["vol"] is d["mesures"] and d["part"] == 0.3
    assert d["raisonnement"].endswith("PART=0.3")
    # le stress-test choisi par le modèle est dans les extras, avec une trace réelle
    assert len(d["extras"]) == 1
    libelle, valeur, tid = d["extras"][0]
    assert "Pire fenêtre de 12 mois" in libelle and valeur.endswith("%") and j.trouver(tid)
    # rien n'a été complété, sauf le point de bascule (qui n'est pas un outil du modèle)
    for cle in ("stats", "macro", "mesures_base", "mesures", "base", "rejeu"):
        assert not _agent_de(j, d[cle]["trace"]).endswith(analyste.COMPLETE), cle
    assert _agent_de(j, d["bascule"]["trace"]).endswith(analyste.COMPLETE)


def test_mode_strands_memes_valeurs_que_le_plan_fixe(strands):
    strands([("statistiques_actif",), ("contexte_taux_2022",), ("rejeu_2022", 0), ("volatilite_portefeuille", 0),
             ("rejeu_2022", 0.3), ("volatilite_portefeuille", 0.3)])
    d = _demande(Journal())
    config.MODE = "local"                         # remis par monkeypatch en fin de test
    f = _demande(Journal())
    assert d["rejeu"]["final"] == pytest.approx(f["rejeu"]["final"])
    assert d["mesures"]["vol"] == pytest.approx(f["mesures"]["vol"])
    assert d["bascule"]["part_max"] == f["bascule"]["part_max"]


def test_calcul_oublie_complete_par_l_orchestrateur(strands):
    strands([("statistiques_actif",), ("rejeu_2022", 0.3)])           # oublie macro, base, volatilités
    j = Journal()
    d = _demande(j)
    assert set(d) == CLES and d["extras"] == []
    assert not _agent_de(j, d["stats"]["trace"]).endswith(analyste.COMPLETE)
    assert not _agent_de(j, d["rejeu"]["trace"]).endswith(analyste.COMPLETE)
    for cle in ("macro", "mesures_base", "mesures", "base"):
        assert _agent_de(j, d[cle]["trace"]).endswith(analyste.COMPLETE), cle


def test_correction_jamais_au_dessus_de_la_part_precedente(strands):
    strands([("rejeu_2022", 0.5), ("volatilite_portefeuille", 0.5)], texte="Je propose plus.\nPART=0.5")
    j = Journal()
    a = analyste.analyser_alternative(j, PERSONA, "TSLA", 0.03, 2, consigne="Teste 3 %", part_precedente=0.30)
    assert a["part"] <= 0.30 and a["part"] == 0.03                   # part de repli déterministe
    assert any(t["titre"] == "Part proposée par le modèle écartée" for t in j.traces)
    assert _agent_de(j, a["rejeu"]["trace"]).endswith(analyste.COMPLETE)
    # le calcul fait à 50 % n'est pas perdu : il apparaît comme extra
    assert {lib for lib, _, _ in a["extras"]} == {"Rejeu 2022 · alternative 50 % TSLA", "Volatilité / pire baisse · alternative 50 % TSLA"}


def test_correction_part_du_modele_retenue(strands):
    strands([("rejeu_2022", 0.02), ("volatilite_portefeuille", 0.02)], texte="Plus prudent.\nPART=0.02")
    j = Journal()
    a = analyste.analyser_alternative(j, PERSONA, "TSLA", 0.03, 2, consigne="Teste 3 %", part_precedente=0.30)
    assert a["part"] == 0.02 and set(a) == {"poids", "part", "mesures", "vol", "rejeu", "extras", "raisonnement"}
    assert abs(a["poids"]["TSLA"] - 0.02) < 1e-9
    assert not _agent_de(j, a["rejeu"]["trace"]).endswith(analyste.COMPLETE)
    assert not _agent_de(j, a["mesures"]["trace"]).endswith(analyste.COMPLETE)


@pytest.mark.parametrize("texte", ["pas de ligne finale", "PART=abc", "PART=1.7", "PART=0.30"])
def test_correction_part_illisible_ou_non_plus_prudente(strands, texte):
    strands([], texte=texte)
    a = analyste.analyser_alternative(Journal(), PERSONA, "TSLA", 0.03, 2, part_precedente=0.30)
    assert a["part"] == 0.03


def test_repli_sur_le_plan_fixe_si_strands_echoue(monkeypatch):
    monkeypatch.setattr(config, "MODE", "bedrock")
    monkeypatch.setattr(config, "ANALYSTE", "strands")

    def en_panne(outils):
        raise RuntimeError("Bedrock indisponible")
    monkeypatch.setattr(analyste, "_creer_agent", en_panne)
    j = Journal()
    d = _demande(j)
    assert set(d) == CLES and d["extras"] == []
    repli = [t for t in j.traces if t["titre"] == "Repli sur le plan fixe"]
    assert len(repli) == 1 and "RuntimeError" in repli[0]["sortie"]
    assert "RuntimeError" in d["raisonnement"]
    assert not any(t["agent"].endswith(analyste.COMPLETE) for t in j.traces)   # plan fixe, rien de « complété »
    a = analyste.analyser_alternative(j, PERSONA, "TSLA", 0.03, 2, part_precedente=0.30)
    assert a["part"] == 0.03 and sum(t["titre"] == "Repli sur le plan fixe" for t in j.traces) == 2


def test_analyste_fixe_force_le_plan_fixe(monkeypatch):
    monkeypatch.setattr(config, "MODE", "bedrock")
    monkeypatch.setattr(config, "ANALYSTE", "fixe")
    monkeypatch.setattr(analyste, "_creer_agent", lambda outils: pytest.fail("Strands ne doit pas être appelé"))
    assert _demande(Journal())["raisonnement"] == ""


def test_pire_fenetre_12_mois_trace_et_coherence():
    j = Journal()
    r = calculs.pire_fenetre_12_mois(j, {"XIU.TO": 0.6, "XBB.TO": 0.4}, "test", "test")
    assert r["rend"] is not None and -1 < r["rend"] < 1 and r["debut"] < r["fin"]
    assert f"{r['debut']}" in j.trouver(r["trace"])["sortie"]
    # un actif seul : recalcul direct du pire rendement sur 252 jours de bourse
    prix, _, _ = charger()
    p = prix["XIU.TO"].ffill()
    p = p[p.index.dayofweek < 5]
    n = config.CALCUL["fenetre_stress_jours"]
    assert calculs.pire_fenetre_12_mois(Journal(), {"XIU.TO": 1.0}, "t", "t")["rend"] == pytest.approx(
        float((p.shift(-n) / p - 1).min()))
