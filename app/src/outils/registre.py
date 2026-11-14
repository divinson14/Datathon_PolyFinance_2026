"""Liste des outils exposés à l'Agent Analyste (et à Lambda).
Étape suivante : décrire ces outils en JSON Schema pour le « tool use » de l'API Converse de Bedrock."""
from src.outils import calculs

OUTILS = {
    "statistiques": calculs.statistiques,
    "rejeu_2022": calculs.rejeu_2022,
    "volatilite_portefeuille": calculs.volatilite_portefeuille,
    "analyse_portefeuille": calculs.analyse_portefeuille,
    "point_de_bascule": calculs.point_de_bascule,
    "contexte_macro": calculs.contexte_macro,
}
