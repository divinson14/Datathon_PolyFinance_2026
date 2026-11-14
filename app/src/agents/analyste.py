"""Agent Analyste : choisit et appelle les outils de calcul.
Squelette : plan fixe. Étape suivante : « tool use » Bedrock avec prompts/analyste.md et outils/registre.py."""
from src.formatage import pct
from src.outils import calculs


def analyser_demande(journal, persona: dict, symbole: str, part: float, gabarit: dict, univers,
                     tentative: int = 1) -> dict:
    agent = f"Agent Analyste · tentative {tentative}"
    base = persona["portefeuille_suppose"]
    poids = calculs.poids_avec_position(base, symbole, part)
    lib = f"demande {pct(part)} {symbole}"
    mesures = calculs.analyse_portefeuille(journal, poids, lib, agent)
    return {
        "poids": poids, "part": part,
        "stats": calculs.statistiques(journal, symbole, agent),
        "macro": calculs.contexte_macro(journal, agent),
        "mesures_base": calculs.analyse_portefeuille(journal, base, "portefeuille actuel", agent),
        "mesures": mesures,
        "vol": mesures,                                     # alias : {"vol", "trace"}
        "bascule": calculs.point_de_bascule(journal, base, symbole, gabarit, univers, agent, persona),
        "base": calculs.rejeu_2022(journal, base, persona["capital"], "portefeuille actuel", agent),
        "rejeu": calculs.rejeu_2022(journal, poids, persona["capital"], lib, agent),
    }


def analyser_alternative(journal, persona: dict, symbole: str, part: float, tentative: int) -> dict:
    agent = f"Agent Analyste · tentative {tentative}"
    poids = calculs.poids_avec_position(persona["portefeuille_suppose"], symbole, part)
    lib = f"alternative {pct(part)} {symbole}"
    mesures = calculs.analyse_portefeuille(journal, poids, lib, agent)
    return {
        "poids": poids, "part": part, "mesures": mesures, "vol": mesures,
        "rejeu": calculs.rejeu_2022(journal, poids, persona["capital"], lib, agent),
    }
