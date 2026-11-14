from src.formatage import money, pct
from src.outils import calculs
from src.traces.journal import Journal


def test_formatage():
    assert pct(-0.2512) == "-25,1 %"
    assert pct(0.30, 0) == "30 %"
    assert money(-50213) == "-50 200 $"


def test_poids_avec_position_somme_a_un():
    p = calculs.poids_avec_position({"XIU": 0.6, "XBB": 0.4}, "TSLA", 0.3)
    assert abs(sum(p.values()) - 1) < 1e-9 and abs(p["TSLA"] - 0.3) < 1e-9


def test_rejeu_et_traces():
    j = Journal()
    r = calculs.rejeu_2022(j, {"XIU": 0.6, "XBB": 0.4}, 200000, "test", "test")
    assert len(r["valeurs"]) == 13 and r["trace"] == "T-01"
    assert abs(r["perte"] - (r["final"] - 200000)) < 1e-6


def test_volatilite_augmente_avec_tesla():
    j = Journal()
    v0 = calculs.volatilite_portefeuille(j, {"XIU": 0.6, "XBB": 0.4}, "a", "t")["vol"]
    v1 = calculs.volatilite_portefeuille(j, calculs.poids_avec_position({"XIU": 0.6, "XBB": 0.4}, "TSLA", 0.3), "b", "t")["vol"]
    assert v1 > v0
