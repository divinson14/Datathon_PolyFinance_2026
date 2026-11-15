"""Agent Gouvernance testé SANS appel AWS : faux client Bedrock (monkeypatch de bedrock_client).
Le jugement (statut) vient toujours du code ; le LLM ne fait que formuler."""
import pytest

from src import bedrock_client, config
from src.agents import analyste, gouvernance
from src.config import GABARITS, PERSONAS
from src.donnees.chargeur import charger
from src.orchestrateur import executer
from src.traces.journal import Journal

ROBERT = PERSONAS["robert"]
GABARIT = GABARITS[ROBERT["risque"]]


@pytest.fixture(scope="module")
def univers():
    return charger()[1]


@pytest.fixture(scope="module")
def analyses(univers):
    """Analyses de Robert (plan fixe, MODE=local), calculées une fois : (journal, analyse) par cas."""
    cas = {"conforme": ("TSLA", 0.03), "corrigeable": ("TSLA", 0.30), "impossible": ("BTC-USD", 0.05)}
    out = {}
    for statut, (symbole, part) in cas.items():
        j = Journal()
        d = analyste.analyser_demande(j, ROBERT, symbole, part, GABARIT, univers)
        out[statut] = (j, d, symbole)
    if not out["corrigeable"][1]["bascule"]["base_conforme"]:
        pytest.skip("portefeuille de Robert non conforme sur ces données (données fictives ?) : "
                    "lancer data/scripts/01_nettoyer_prix.py")
    return out


def _verifier(analyses, univers, statut):
    j, d, symbole = analyses[statut]
    return j, gouvernance.verifier(j, d, symbole, GABARIT, univers, f"demande {symbole}", ROBERT)


@pytest.fixture
def faux_llm(monkeypatch):
    """Installe un faux Bedrock qui renvoie `reponse` (dict) ou lève l'exception donnée."""
    def installer(reponse):
        def appeler_json(*a, **k):
            if isinstance(reponse, Exception):
                raise reponse
            return reponse
        monkeypatch.setattr(bedrock_client, "actif", lambda: True)
        monkeypatch.setattr(bedrock_client, "appeler_json", appeler_json)
    return installer


# ---------- Le statut est calculé par le code, quoi que dise le LLM ----------

@pytest.mark.parametrize("attendu", ["conforme", "corrigeable", "impossible"])
@pytest.mark.parametrize("dit_par_le_llm", ["conforme", "corrigeable", "impossible"])
def test_statut_calcule_par_le_code(analyses, univers, faux_llm, attendu, dit_par_le_llm):
    faux_llm({"statut": dit_par_le_llm, "resume": "Résumé rédigé par le LLM, sans chiffre (voir trace T-01).",
              "consigne": "Teste une part plus faible.", "tensions_profil": []})
    j, v = _verifier(analyses, univers, attendu)
    assert v["statut"] == attendu and v["redaction"] == "llm"
    assert v["resume"].startswith("Résumé rédigé par le LLM")
    if attendu == "corrigeable":
        assert v["consigne"] == "Teste une part plus faible."
    else:
        assert v["consigne"] is None               # pas de consigne si le code ne juge pas la demande corrigeable
    controle = [t for t in j.traces if t["titre"] == "Formulation Gouvernance · chiffres vérifiés"][-1]
    assert f"statut calculé par le code : {attendu}" in controle["sortie"]


def test_statut_en_mode_local_sans_llm(analyses, univers):
    for attendu in ("conforme", "corrigeable", "impossible"):
        _, v = _verifier(analyses, univers, attendu)
        assert v["statut"] == attendu and v["redaction"] == "code (MODE=local)" and v["resume"]
    assert "point de bascule" in _verifier(analyses, univers, "corrigeable")[1]["consigne"]


def test_consigne_du_code_si_le_llm_n_en_donne_pas(analyses, univers, faux_llm):
    faux_llm({"statut": "corrigeable", "resume": "Deux règles sont franchies.", "consigne": None, "tensions_profil": []})
    _, v = _verifier(analyses, univers, "corrigeable")
    assert v["consigne"].startswith("Teste TSLA au point de bascule calculé")


# ---------- Vérification des chiffres et repli ----------

def test_chiffre_invente_declenche_le_repli(analyses, univers, faux_llm):
    faux_llm({"statut": "corrigeable", "resume": "Avec TSLA, la perte attendue serait de 42,7 % (trace T-03).",
              "consigne": None, "tensions_profil": []})
    j, v = _verifier(analyses, univers, "corrigeable")
    repli = [t for t in j.traces if t["titre"] == "Repli Gouvernance"][-1]
    assert "42,7" in repli["sortie"] and "introuvable" in repli["sortie"]
    assert "42,7" not in v["resume"] and v["redaction"].startswith("code (repli")
    assert v["statut"] == "corrigeable" and v["consigne"]           # le repli garde le jugement du code


def test_chiffre_des_traces_accepte(analyses, univers, faux_llm):
    _, d, _ = analyses["corrigeable"]
    from src.formatage import pct
    part = pct(d["mesures"]["parts_risque"]["TSLA"])
    faux_llm({"statut": "corrigeable", "resume": f"TSLA porterait {part} du risque (trace {d['mesures']['trace']}).",
              "consigne": None, "tensions_profil": []})
    _, v = _verifier(analyses, univers, "corrigeable")
    assert v["redaction"] == "llm" and part in v["resume"]


@pytest.mark.parametrize("panne", [ConnectionError("identifiants expirés"), TimeoutError("délai dépassé")])
def test_bedrock_en_panne_repli_deterministe_et_trace(analyses, univers, faux_llm, panne):
    faux_llm(panne)
    j, v = _verifier(analyses, univers, "corrigeable")
    repli = [t for t in j.traces if t["titre"] == "Repli Gouvernance"][-1]
    assert type(panne).__name__ in repli["sortie"]
    assert v["statut"] == "corrigeable" and v["resume"] and v["consigne"]


@pytest.mark.parametrize("reponse", [None, {"statut": "conforme"}, {"resume": "ok", "tensions_profil": "pas une liste"}])
def test_json_illisible_repli(analyses, univers, faux_llm, reponse):
    faux_llm(reponse)
    j, v = _verifier(analyses, univers, "conforme")
    assert v["redaction"].startswith("code (repli") and any(t["titre"] == "Repli Gouvernance" for t in j.traces)


# ---------- Filet de sécurité : base qui viole déjà le mandat ----------

def test_base_non_conforme_statut_impossible():
    v = {"violees": [{"regle": "Cryptoactifs"}], "regles": [], "manquantes": [], "trace": "T-01"}
    bascule = {"base_conforme": False, "part_max": None, "limitantes": ["Cryptoactifs"], "trace": "T-02"}
    assert gouvernance.calculer_statut(v, bascule) == "impossible"


def test_base_non_conforme_pas_de_boucle(monkeypatch):
    base = {s: w * 0.95 for s, w in ROBERT["portefeuille_suppose"].items()}
    base["BTC-USD"] = 0.05                          # crypto interdite pour Robert : la base viole déjà le mandat
    monkeypatch.setitem(config.PERSONAS, "robert", {**ROBERT, "portefeuille_suppose": base})
    res = executer("robert", "Je pense mettre 30 % dans Tesla.")
    assert not res["arret"]
    assert res["verdicts"]["statut"] == "impossible" and res["alternative"] is None
    assert not any(e["agent"].startswith("Agent Analyste · tentative 2") for e in res["etapes"])
    gouv = next(e for e in res["etapes"] if e["agent"] == "Agent Gouvernance")
    assert "viole déjà le mandat" in gouv["resume"] and gouv["consigne"] is None


# ---------- Tensions avec les préférences du persona ----------

def test_tension_robert_tesla(analyses, univers):
    _, v = _verifier(analyses, univers, "corrigeable")
    assert any("TSLA" in t and "établies" in t for t in v["tensions_profil"]), v["tensions_profil"]


def test_tension_robert_bitcoin(analyses, univers):
    _, v = _verifier(analyses, univers, "impossible")
    assert any("cryptoactif" in t.lower() for t in v["tensions_profil"]), v["tensions_profil"]


def test_pas_de_tension_sur_un_fnb_large(univers):
    j = Journal()
    d = analyste.analyser_demande(j, ROBERT, "XIU.TO", 0.05, GABARIT, univers)
    v = gouvernance.verifier(j, d, "XIU.TO", GABARIT, univers, "demande XIU", ROBERT)
    assert v["tensions_profil"] == []


def test_tensions_du_code_gardees_si_le_llm_les_oublie(analyses, univers, faux_llm):
    faux_llm({"statut": "corrigeable", "resume": "Conflits résumés.", "consigne": None, "tensions_profil": []})
    _, v = _verifier(analyses, univers, "corrigeable")
    assert v["redaction"] == "llm" and any("établies" in t for t in v["tensions_profil"])


def test_etape_gouvernance_affiche_resume_consigne_tensions():
    res = executer("robert", "Je pense mettre 30 % dans Tesla.")
    gouv = next(e for e in res["etapes"] if e["agent"] == "Agent Gouvernance")
    if res["verdicts"]["statut"] != "corrigeable":
        pytest.skip("données fictives : la demande n'est pas corrigeable")
    assert gouv["resume"] and gouv["consigne"] and gouv["tensions"]
