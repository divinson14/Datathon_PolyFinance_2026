"""Agent Analyste : choisit et appelle les outils de calcul.
Squelette : plan fixe. Étape suivante : « tool use » Bedrock avec prompts/analyste.md et outils/registre.py."""
from src.outils import calculs


def analyser_demande(journal, persona: dict, symbole: str, part: float, tentative: int = 1) -> dict:
    agent = f"Agent Analyste · tentative {tentative}"
    base = persona["portefeuille_suppose"]
    poids = calculs.poids_avec_position(base, symbole, part)
    lib = f"demande {round(part * 100)} % {symbole}"
    return {
        "poids": poids, "part": part,
        "stats": calculs.statistiques(journal, symbole, agent),
        "macro": calculs.contexte_macro(journal, agent),
        "base": calculs.rejeu_2022(journal, base, persona["capital"], "portefeuille actuel", agent),
        "rejeu": calculs.rejeu_2022(journal, poids, persona["capital"], lib, agent),
        "vol": calculs.volatilite_portefeuille(journal, poids, lib, agent),
    }


def analyser_alternative(journal, persona: dict, symbole: str, part: float, tentative: int) -> dict:
    agent = f"Agent Analyste · tentative {tentative}"
    poids = calculs.poids_avec_position(persona["portefeuille_suppose"], symbole, part)
    lib = f"alternative {round(part * 100)} % {symbole}"
    return {
        "poids": poids, "part": part,
        "rejeu": calculs.rejeu_2022(journal, poids, persona["capital"], lib, agent),
        "vol": calculs.volatilite_portefeuille(journal, poids, lib, agent),
    }
