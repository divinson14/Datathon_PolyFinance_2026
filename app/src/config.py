"""Chargement de la configuration : .env, gabarits, styles, personas."""
import json
import os
from pathlib import Path

import yaml
from dotenv import load_dotenv

APP = Path(__file__).resolve().parents[1]          # dossier app/
RACINE_REPO = APP.parent
load_dotenv(APP / ".env")

MODE = os.getenv("MODE", "local")                    # local | bedrock
DONNEES = os.getenv("DONNEES", "local")              # local | s3 | demo
TRACES = os.getenv("TRACES", "local")                # local | dynamodb
ANALYSTE = os.getenv("ANALYSTE", "strands")         # strands (agent qui choisit ses outils) | fixe (plan fixe)
MAX_TENTATIVES = 3


def _yaml(nom):
    with open(APP / "config" / nom, encoding="utf-8") as f:
        return yaml.safe_load(f)


GABARITS = _yaml("gabarits_risque.yaml")
CALCUL = _yaml("calcul.yaml")
STYLES = _yaml("styles_explication.yaml")
PERSONAS = {
    p.stem: json.loads(p.read_text(encoding="utf-8"))
    for p in sorted((APP / "config" / "personas").glob("*.json"))
}


def prompt(nom: str) -> str:
    return (APP / "prompts" / f"{nom}.md").read_text(encoding="utf-8")
