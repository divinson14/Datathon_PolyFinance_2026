"""Agent Gouvernance : s'appuie sur le moteur de règles (déterministe) et formule la correction."""
from src.config import CALCUL
from src.formatage import pct
from src.regles.moteur import verifier_mandat


def verifier(journal, analyse: dict, symbole: str, gabarit: dict, univers, libelle: str,
             persona: dict | None = None) -> dict:
    v = verifier_mandat(journal, analyse["poids"], analyse["mesures"], gabarit, univers, libelle, persona)
    bascule = analyse.get("bascule")
    if not v["violees"]:
        v["consigne"] = None
    elif bascule and bascule["part_max"]:
        v["consigne"] = f"Teste {symbole} au point de bascule calculé ({pct(bascule['part_max'])})."
    else:
        v["consigne"] = f"Aucune part de {symbole} n'est compatible avec le mandat : ne pas proposer d'alternative."
    return v


def premiere_correction(part_demandee: float, bascule: dict) -> float | None:
    """Correction 1 : le point de bascule calculé par l'outil. None = aucune part compatible."""
    if not bascule["part_max"]:
        return None
    return min(part_demandee, bascule["part_max"])


def correction_suivante(part_actuelle: float) -> float | None:
    """Filet de sécurité si la vérification indépendante échoue : on recule d'un pas de la grille."""
    suivante = round(part_actuelle - CALCUL["pas_bascule"], 6)
    return suivante if suivante > 0 else None
