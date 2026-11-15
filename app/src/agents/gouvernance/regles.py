"""Jugement DÉTERMINISTE de l'Agent Gouvernance. Code pur, AUCUN LLM.

- verdicts : moteur de règles existant (src/regles/moteur.py), une trace par verdict ;
- statut (conforme / corrigeable / impossible) : calculé ici, jamais par le LLM ;
- consigne de repli pour l'Analyste et parts de correction (point de bascule, puis un pas de grille) ;
- tensions entre la demande et les préférences TEXTUELLES du persona (config/tensions_profil.yaml).
Le LLM (redaction.py) ne fait que formuler autour de ce qui est calculé ici.
"""
import re
import unicodedata

from src.config import CALCUL, TENSIONS_PROFIL
from src.donnees.chargeur import charger_esg
from src.formatage import pct
from src.regles.moteur import verifier_mandat

CONFORME, CORRIGEABLE, IMPOSSIBLE = "conforme", "corrigeable", "impossible"


def juger(journal, analyse: dict, gabarit: dict, univers, libelle: str, persona: dict | None = None) -> dict:
    """Verdicts du moteur de règles (journalisés) : {trace, regles, violees, manquantes}."""
    return verifier_mandat(journal, analyse["poids"], analyse["mesures"], gabarit, univers, libelle, persona)


def base_conforme(bascule: dict | None) -> bool:
    """Le portefeuille de base supposé respecte-t-il le mandat ? (évalué à part = 0 par le point de bascule)"""
    return bool(bascule) and bascule["base_conforme"]


def calculer_statut(verdicts: dict, bascule: dict | None) -> str:
    """conforme : aucune règle violée. corrigeable : une part plus faible respecte toutes les règles.
    impossible : base déjà non conforme (filet de sécurité), ou aucune part compatible."""
    if not verdicts["violees"]:
        return CONFORME
    if not base_conforme(bascule) or not bascule["part_max"]:
        return IMPOSSIBLE
    return CORRIGEABLE


def consigne(statut: str, symbole: str, verdicts: dict, bascule: dict | None, part_testee: float | None = None) -> str | None:
    """Instruction déterministe pour l'Analyste (None si rien à corriger ou si c'est impossible).
    part_testee = None pour la demande initiale ; sinon, part de l'alternative qui viole encore."""
    if statut != CORRIGEABLE:
        return None
    if part_testee is None:
        return f"Teste {symbole} au point de bascule calculé ({pct(bascule['part_max'])})."
    return (f"L'alternative à {pct(part_testee)} de {symbole} viole encore : "
            + ", ".join(r["regle"] for r in verdicts["violees"]) + ". Propose une part plus prudente.")


# ---------- Parts de correction (inchangées) ----------

def premiere_correction(part_demandee: float, bascule: dict) -> float | None:
    """Correction 1 : le point de bascule calculé par l'outil. None = aucune part compatible."""
    if not bascule["part_max"]:
        return None
    return min(part_demandee, bascule["part_max"])


def correction_suivante(part_actuelle: float) -> float | None:
    """Filet de sécurité si la vérification indépendante échoue : on recule d'un pas de la grille."""
    suivante = round(part_actuelle - CALCUL["pas_bascule"], 6)
    return suivante if suivante > 0 else None


def prochaine_part(part_precedente: float, tentative: int, bascule: dict) -> float | None:
    """Part de repli déterministe pour la tentative `tentative` (2 = première correction).
    Sert aussi quand la part proposée par le modèle est illisible ou non plus prudente. None = aucune part."""
    if tentative <= 2:
        return premiere_correction(part_precedente, bascule)
    return correction_suivante(part_precedente)


# ---------- Tensions avec les préférences du persona ----------

def _sans_accents(texte: str) -> str:
    return unicodedata.normalize("NFKD", texte).encode("ascii", "ignore").decode().lower()


def _preference(textes: list[str], motifs: list[str]) -> str | None:
    """Première préférence (texte d'origine) qui contient l'un des motifs."""
    return next((t for t in textes if any(re.search(m, _sans_accents(t)) for m in motifs)), None)


def _statut_esg(symbole: str) -> str:
    esg = charger_esg()
    if esg is None:
        return "non évalué"
    drapeaux = dict(zip(esg["symbole"].astype(str), esg["controverse"].astype(str).str.lower()))
    return {"oui": "controverse", "non": "sans controverse", "conforme": "sans controverse",
            "non applicable": "non applicable"}.get(drapeaux.get(symbole, "").strip(), "non évalué")


def tensions_profil(persona: dict | None, symbole: str, analyse: dict, verdicts: dict, univers) -> list[str]:
    """Tensions entre la demande et les préférences TEXTUELLES du persona. Elles n'entrent jamais dans le verdict.
    Chaque chiffre cité vient d'une trace (identifiant indiqué)."""
    if not persona:
        return []
    textes = list(persona.get("preferences") or [])
    if persona.get("objectif") and persona["objectif"] != "non précisé":
        textes.append(persona["objectif"])
    classe = dict(zip(univers["symbole"].astype(str), univers["classe"].astype(str))).get(symbole)
    titre = classe in CALCUL["classes_titres"]
    stats = analyse.get("stats")
    violees = {r["regle"] for r in verdicts["violees"]}

    tensions = []
    for t in TENSIONS_PROFIL["tensions"]:
        raison = None
        if t["condition"] == "cryptoactif" and classe == "crypto":
            raison = f"{symbole} est un cryptoactif"
        elif (t["condition"] == "titre_tres_volatil" and titre and classe != "crypto" and stats
              and stats["vol"] > TENSIONS_PROFIL["volatilite_titre_tres_volatil"]):
            raison = (f"{symbole} est un titre individuel très volatil "
                      f"(volatilité de {pct(stats['vol'])} seul, trace {stats['trace']})")
        elif t["condition"] == "esg_incertain":           # tous les actifs, FNB compris (comme le moteur)
            statut = _statut_esg(symbole)
            if statut == "controverse":
                raison = f"{symbole} est marqué « controverse importante » dans les données ESG"
            elif statut == "non évalué":
                raison = f"{symbole} n'a pas encore d'évaluation ESG : information manquante"
        elif t["condition"] == "concentration" and "Part du risque max par titre" in violees:
            part = analyse["mesures"]["parts_risque"].get(symbole, 0.0)
            raison = f"{symbole} porterait {pct(part)} du risque du portefeuille (trace {analyse['mesures']['trace']})"
        if raison:
            pref = _preference(textes, t["motifs"])
            if pref:
                tensions.append(f"Préférence « {pref} » : {raison}.")
    return tensions
