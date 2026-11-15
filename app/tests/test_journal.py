"""Journal d'audit en mode DynamoDB, testé SANS AWS : une fausse table remplace boto3."""
import sys
import types

import pytest

from src.traces import journal as module_journal


class FausseTable:
    def __init__(self, panne=False):
        self.items, self.panne = [], panne

    def put_item(self, Item):
        if self.panne:
            raise ConnectionError("AccessDeniedException")
        self.items.append(Item)


@pytest.fixture
def dynamodb(monkeypatch, tmp_path):
    """Active TRACES=dynamodb avec une fausse table ; les fichiers locaux vont dans un dossier temporaire."""
    monkeypatch.setattr(module_journal, "TRACES", "dynamodb")
    monkeypatch.setattr(module_journal, "APP", tmp_path)

    def installer(table):
        faux_boto3 = types.SimpleNamespace(resource=lambda *a, **k: types.SimpleNamespace(Table=lambda nom: table))
        monkeypatch.setitem(sys.modules, "boto3", faux_boto3)
        return table
    return installer


def test_traces_ecrites_dans_dynamodb(dynamodb, tmp_path):
    table = dynamodb(FausseTable())
    j = module_journal.Journal()
    j.log(titre="Calcul", agent="test", outil="o", entrees="e", sortie="volatilité 18,4 %", source="s", periode="p",
          controle=True)
    assert len(table.items) == 1 and j.dynamodb_ok is True
    item = table.items[0]
    assert item["session"] == j.session and item["id"] == "T-01" and item["sortie"] == "volatilité 18,4 %"
    assert all(isinstance(v, str) for v in item.values())            # DynamoDB : uniquement des chaînes
    assert not (tmp_path / "traces_locales").exists()                 # pas de doublon local


def test_panne_dynamodb_la_trace_n_est_jamais_perdue(dynamodb, tmp_path):
    dynamodb(FausseTable(panne=True))
    j = module_journal.Journal()
    tid = j.log(titre="Calcul", agent="test", outil="o", entrees="e", sortie="s", source="s", periode="p")
    assert tid == "T-01" and j.trouver(tid) and j.dynamodb_ok is False   # l'analyse continue
    fichier = tmp_path / "traces_locales" / f"{j.session}.jsonl"
    assert fichier.exists() and "T-01" in fichier.read_text(encoding="utf-8")


def test_analyse_complete_en_mode_dynamodb(dynamodb):
    from src.orchestrateur import executer
    table = dynamodb(FausseTable())
    res = executer("robert", "Je pense mettre 30 % dans Tesla.")
    assert not res["arret"] and res["verif"]["ok"]
    assert [i["id"] for i in table.items] == [t["id"] for t in res["journal"].traces]
