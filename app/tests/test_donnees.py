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


def test_manifeste_statut_version():
    """Le libellé de version dit toujours la vérité : absent, conforme ou modifié depuis le manifeste."""
    octets = b"date,SPY\r\n2026-11-13,100\r\n"
    manifeste = {"version": "abc123def456", "genere_le": "2026-11-15T12:00:00+00:00",
                 "fichiers": {"prix_cad_alignes.csv": {"sha256": chargeur.empreinte(octets.replace(b"\r\n", b"\n"))}}}
    # Fins de ligne \r\n (Windows) ou \n : même empreinte.
    assert "empreintes vérifiées" in chargeur.statut_version(manifeste, {"prix_cad_alignes.csv": octets})
    assert "abc123def456" in chargeur.statut_version(manifeste, {"prix_cad_alignes.csv": octets})
    modifie = chargeur.statut_version(manifeste, {"prix_cad_alignes.csv": octets + b"2026-11-14,101\n"})
    assert "ne correspond PAS" in modifie and "prix_cad_alignes.csv" in modifie
    assert "non vérifiée" in chargeur.statut_version(None, {"prix_cad_alignes.csv": octets})
