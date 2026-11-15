"""Données : l'application ne doit jamais tourner en silence sur les données FICTIVES de démonstration,
et chaque réponse doit dire que les montants sont en dollars canadiens."""
import pytest

from src import config
from src.agents import explicabilite
from src.donnees import chargeur
from src.orchestrateur import executer
from src.verif import fidelite


def test_donnees_reelles_en_mode_local():
    """Échoue si DONNEES=local mais que le chargeur est retombé sur la démo (data/processed/ absent ou incomplet)."""
    if config.DONNEES != "local":
        pytest.skip(f"DONNEES={config.DONNEES} : test réservé au mode local")
    prix, univers, source = chargeur.charger()
    assert not chargeur.donnees_fictives(), (
        "Données FICTIVES utilisées alors que DONNEES=local : lancer python data/scripts/01_nettoyer_prix.py")
    assert source != chargeur.LIBELLE_DEMO
    assert prix.shape[1] == len(univers) and not prix.isna().any().any()
    assert set(prix.columns) == set(univers["symbole"])


def test_mention_cad_dans_chaque_reponse():
    res = executer("robert", "Je pense mettre 30 % dans Tesla.")
    assert explicabilite.MENTION_CAD in res["fiche"]["limites"]
    assert explicabilite.MENTION_FICTIVES not in res["fiche"]["limites"] or chargeur.donnees_fictives()
    assert res["verif"]["ok"]
    for style in ("avance", "inter"):
        assert explicabilite.MENTION_CAD in explicabilite._gabarit_texte(res["contexte"], style)["limites"]


def test_mention_donnees_fictives_et_verificateur(monkeypatch):
    """Sur données fictives, l'explication le dit ; les mentions ne contiennent aucun chiffre à vérifier."""
    res = executer("robert", "Je pense mettre 30 % dans Tesla.")
    monkeypatch.setattr(explicabilite, "donnees_fictives", lambda: True)
    fiche = explicabilite._gabarit_texte(res["contexte"], "avance")
    assert fiche["limites"].startswith(explicabilite.MENTION_FICTIVES)
    assert explicabilite.MENTION_CAD in fiche["limites"]
    assert not fidelite.NUM_RE.findall(explicabilite.MENTION_FICTIVES + explicabilite.MENTION_CAD)
    assert fidelite.verifier(res["journal"], fiche, res["autorise"], 99)["ok"]


def test_mentions_non_dupliquees():
    fiche = explicabilite._mentions_obligatoires({"limites": explicabilite.MENTION_CAD + " Autre limite."})
    assert fiche["limites"].count(explicabilite.MENTION_CAD) == 1


def test_traces_de_calcul_en_cad():
    res = executer("robert", "Je pense mettre 30 % dans Tesla.")
    j = res["journal"]
    d = res["demande"]
    for tid in (d["rejeu"]["trace"], d["base"]["trace"], d["mesures"]["trace"]):
        assert "CAD" in j.trouver(tid)["sortie"], tid
