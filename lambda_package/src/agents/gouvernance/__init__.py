"""Agent Gouvernance : JUGE avec le moteur de règles (code pur) et FORMULE avec le LLM.

    regles.py     verdicts, statut (conforme / corrigeable / impossible), consigne, tensions de profil : sans LLM
    redaction.py  formulation par le LLM (MODE=bedrock), chiffres vérifiés contre les traces
    repli.py      textes déterministes (MODE=local, ou si le LLM échoue)

API publique inchangée : verifier, premiere_correction, correction_suivante, prochaine_part.
"""
from . import redaction, regles, repli
from .regles import (CONFORME, CORRIGEABLE, IMPOSSIBLE, calculer_statut, correction_suivante,
                     premiere_correction, prochaine_part, tensions_profil)


def verifier(journal, analyse: dict, symbole: str, gabarit: dict, univers, libelle: str,
             persona: dict | None = None, bascule: dict | None = None, formuler: bool = True) -> dict:
    """Verdicts du moteur de règles + statut, résumé, consigne et tensions.

    Renvoie {trace, regles, violees, manquantes, statut, resume, consigne, tensions_profil, redaction}.
    bascule : point de bascule de la demande initiale (pris dans `analyse` s'il y est ; à fournir pour une alternative).
    formuler : False = textes déterministes sans appel au LLM (vérification rapide d'une alternative).
    """
    alternative = "bascule" not in analyse
    bascule = bascule or analyse.get("bascule")
    v = regles.juger(journal, analyse, gabarit, univers, libelle, persona)
    statut = regles.calculer_statut(v, bascule)
    jugement = {
        "statut": statut, "symbole": symbole, "libelle": libelle, "verdicts": v, "bascule": bascule,
        "alternative": alternative,
        "consigne": regles.consigne(statut, symbole, v, bascule, analyse.get("part") if alternative else None),
        "tensions": [] if alternative else regles.tensions_profil(persona, symbole, analyse, v, univers),
    }
    f = (redaction.formuler(journal, jugement, persona) if formuler
         else {**repli.formuler(jugement), "auteur": "code"})
    v.update(statut=statut, resume=f["resume"], consigne=f["consigne"], tensions_profil=f["tensions_profil"],
             redaction=f["auteur"])
    return v


__all__ = ["CONFORME", "CORRIGEABLE", "IMPOSSIBLE", "verifier", "calculer_statut", "tensions_profil",
           "premiere_correction", "correction_suivante", "prochaine_part"]
