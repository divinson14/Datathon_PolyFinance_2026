"""Liste des outils de calcul exposés à Lambda.
L'Agent Analyste (Strands) les emballe dans des outils @tool : voir src/agents/analyste.py."""
from src.outils import calculs

OUTILS = {
    "statistiques": calculs.statistiques,
    "rejeu_2022": calculs.rejeu_2022,
    "volatilite_portefeuille": calculs.volatilite_portefeuille,
    "analyse_portefeuille": calculs.analyse_portefeuille,
    "point_de_bascule": calculs.point_de_bascule,
    "contexte_macro": calculs.contexte_macro,
    "pire_fenetre_12_mois": calculs.pire_fenetre_12_mois,
}
