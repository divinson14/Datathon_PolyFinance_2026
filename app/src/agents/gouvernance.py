"""Agent Gouvernance : s'appuie sur le moteur de règles (déterministe) et formule la correction."""
from src.regles.moteur import verifier_mandat


def verifier(journal, analyse: dict, symbole: str, gabarit: dict, univers, libelle: str) -> dict:
    v = verifier_mandat(journal, analyse["poids"], symbole, analyse["rejeu"], analyse["vol"], gabarit, univers, libelle)
    v["consigne"] = (f"Trouve la plus grande position en {symbole} conforme au mandat." if v["violees"] else None)
    return v


def prochaine_part(part_actuelle: float, gabarit: dict, premiere_correction: bool) -> float:
    """Stratégie de correction : d'abord le poids max autorisé, puis on réduit par pas de 2 points."""
    if premiere_correction:
        return min(part_actuelle, gabarit["poids_max_par_titre"])
    return max(0.0, round(part_actuelle - 0.02, 4))
