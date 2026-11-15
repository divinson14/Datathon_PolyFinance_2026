"""Orchestrateur DÉTERMINISTE : enchaîne les agents, gère la boucle de correction (max. 3 tentatives)
et publie chaque étape via on_etape (l'interface l'affiche au fur et à mesure)."""
from src import config
from src.agents import analyste, explicabilite, gouvernance, profil
from src.donnees.chargeur import charger
from src.formatage import nombre, pct
from src.traces.journal import Journal
from src.verif import fidelite


def executer(persona_id: str | None, message: str, style: str | None = None, on_etape=None,
             profil_saisi: dict | None = None, tolerance: str | None = None) -> dict:
    """persona_id = persona de référence ; OU profil_saisi = 5 champs (age, tolerance, horizon_ans, objectif, esg[, capital]).
    tolerance = scénario fictif : la tolérance d'une COPIE du profil est remplacée (voir plus_de_risque)."""
    prix, univers, source = charger()
    journal = Journal()
    etapes = []
    mandat = profil.construire_mandat(persona_id, profil_saisi, journal, tolerance=tolerance)
    entree = {"persona_id": persona_id, "profil_saisi": profil_saisi, "message": message}   # pour relancer (Et si)
    persona, gabarit = mandat["profil"], mandat["gabarit"]
    style = style or ("avance" if persona["niveau_experience"] == "avance" else "inter")

    def etape(agent, statut, texte, **details):
        e = {"agent": agent, "statut": statut, "texte": texte, **details}
        etapes.append(e)
        if on_etape:
            on_etape(e)

    def arret():
        return {"arret": True, "etapes": etapes, "journal": journal, "persona": persona, "mandat": mandat, "entree": entree}

    # 1. Garde-fou
    if profil.demande_de_transaction(message):
        etape("Bedrock Guardrails", "fail", "Demande bloquée : aucune transaction réelle n'est possible. Reformule ta question pour une analyse en simulation.")
        return arret()
    etape("Bedrock Guardrails", "ok", "Demande admise · analyse en mode simulation")

    # 2. Agent Profil : mandat (profil + gabarit) puis demande
    if mandat["bloquant"]:
        etape("Agent Profil", "warn", mandat["question"], trace=mandat["trace"],
              note="Information manquante : " + ", ".join(mandat["informations_manquantes"]) + ". Le système ne la devine pas.")
        return arret()
    dem = profil.extraire(message, persona, univers, journal)
    mandat["demande"] = {k: dem[k] for k in ("symbole", "part", "symboles_mentionnes", "informations_manquantes", "methode", "trace")}
    if dem["informations_manquantes"]:
        etape("Agent Profil", "warn", dem["question"], trace=dem["trace"],
              note="Information manquante : " + ", ".join(dem["informations_manquantes"]) + ". Le système ne la devine pas.")
        return arret()
    symbole, part = dem["symbole"], float(dem["part"])
    g = gabarit
    seuils = (f"poids max/titre {pct(g['poids_max_par_titre'])} · part du risque max/titre {pct(g['part_risque_max_par_titre'])} · "
              f"vol. max {pct(g['volatilite_max'])} · pire baisse max {pct(g['pire_baisse_max'])} · "
              f"obligations min {pct(g['obligations_min'])} · crypto max {pct(g['crypto_max'])}")
    remarques = ([f"Tension : {t}." for t in mandat["tensions"]]
                 + [f"Information manquante : {', '.join(mandat['informations_manquantes'])}."] * bool(mandat["informations_manquantes"]))
    etape("Agent Profil", "warn", "Mandat construit et demande comprise · les hypothèses sont affichées"
          + (f" · {len(mandat['tensions'])} tension(s) dans le profil" if mandat["tensions"] else ""),
          trace=mandat["trace"], note=" ".join(remarques) or None,
          mandat=[("Actif demandé", symbole), ("Part demandée", pct(part) + (f" (= {dem['lecture']['extrait']})" if dem["lecture"]["type"] == "montant" else "")),
                  ("Lecture de la demande", dem["methode"]),
                  ("Gabarit appliqué", f"« {g['label']} » (config/)"),
                  ("Seuils (hypothèses de l'équipe)", seuils),
                  ("Profil", f"{mandat['source']} · horizon {persona['horizon']}"),
                  *[("Hypothèse", h) for h in mandat["hypotheses"]],
                  ("Traces", f"{mandat['trace']} (mandat) · {dem['trace']} (demande)")])

    # 3. Agent Analyste, tentative 1
    d = analyste.analyser_demande(journal, persona, symbole, part, gabarit, univers)
    part_risque = d["mesures"]["parts_risque"].get(symbole, 0.0)
    bascule = d["bascule"]
    calculs_1 = [
        (f"Volatilité de {symbole} seul", pct(d["stats"]["vol"]), d["stats"]["trace"]),
        ("Portefeuille actuel · volatilité", pct(d["mesures_base"]["vol"]), d["mesures_base"]["trace"]),
        (f"Demande · part du risque portée par {symbole}", pct(part_risque), d["mesures"]["trace"]),
        ("Demande · volatilité / pire baisse", f"{pct(d['mesures']['vol'])} / {pct(d['mesures']['pire_baisse'])}", d["mesures"]["trace"]),
        (f"Point de bascule · {symbole}", pct(bascule["part_max"]) if bascule["base_conforme"] else "base non conforme", bascule["trace"]),
        ("Contexte des taux", d["macro"]["resume"] or "indisponible", d["macro"]["trace"]),
        (f"Rejeu 2022 · actuel / demande", f"{pct(d['base']['rend'])} / {pct(d['rejeu']['rend'])}", d["rejeu"]["trace"]),
        *d["extras"]]                                   # calculs supplémentaires choisis par le modèle
    etape("Agent Analyste · tentative 1", "ok", f"{len(calculs_1)} appels d'outils de calcul", calculs=calculs_1,
          **({"note": d["raisonnement"]} if d["raisonnement"] else {}))

    # 4. Agent Gouvernance (jugement par le code, formulation par le LLM) + boucle de correction
    #    La boucle ne tourne QUE si le statut calculé est « corrigeable » (jamais si la base viole déjà le mandat).
    verd = gouvernance.verifier(journal, d, symbole, gabarit, univers, f"demande {pct(part)} {symbole}", persona)
    alt = None
    formulation = dict(regles=verd["regles"], trace=verd["trace"], consigne=verd["consigne"],
                       resume=verd["resume"], tensions=verd["tensions_profil"], redaction=verd.get("redaction"))
    if verd["statut"] == gouvernance.CORRIGEABLE:
        etape("Agent Gouvernance", "fail", f"{len(verd['violees'])} règle(s) violée(s) → correction demandée à l'Analyste",
              **formulation)
        consigne, part_prec = verd["consigne"], part
        for t in range(2, config.MAX_TENTATIVES + 1):
            candidat = gouvernance.prochaine_part(part_prec, t, bascule)   # repli déterministe si le modèle échoue
            if candidat is None:
                break
            a = analyste.analyser_alternative(journal, persona, symbole, candidat, t,
                                              consigne=consigne, part_precedente=part_prec)
            choisie = a["part"]                                           # part réellement retenue (≤ part précédente)
            etape(f"Agent Analyste · tentative {t}", "ok", f"Alternative testée : {pct(choisie)} en {symbole}", calculs=[
                (f"Part du risque · {symbole}", pct(a["mesures"]["parts_risque"].get(symbole, 0.0)), a["mesures"]["trace"]),
                ("Volatilité / pire baisse", f"{pct(a['mesures']['vol'])} / {pct(a['mesures']['pire_baisse'])}", a["mesures"]["trace"]),
                (f"Rejeu 2022 · {pct(choisie)} {symbole}", pct(a["rejeu"]["rend"]), a["rejeu"]["trace"]),
                *a["extras"]], **({"note": a["raisonnement"]} if a["raisonnement"] else {}))
            v2 = gouvernance.verifier(journal, a, symbole, gabarit, univers, f"alternative {pct(choisie)} {symbole}", persona,
                                      bascule=bascule, formuler=False)
            if not v2["violees"]:
                a["verdicts"] = v2
                alt = a
                etape("Agent Gouvernance", "ok", f"{len(v2['regles'])} règles sur {len(v2['regles'])} respectées",
                      regles=v2["regles"], trace=v2["trace"], resume=v2["resume"])
                break
            etape("Agent Gouvernance", "fail", f"Toujours {len(v2['violees'])} règle(s) violée(s) → nouvelle correction",
                  regles=v2["regles"], trace=v2["trace"], resume=v2["resume"])
            consigne, part_prec = v2["consigne"], choisie
        if alt is None:
            etape("Orchestrateur", "warn", f"Pas d'alternative proposée : aucune alternative conforme trouvée en "
                                           f"{config.MAX_TENTATIVES} tentatives. Le système le dit honnêtement.")
    elif verd["statut"] == gouvernance.IMPOSSIBLE:
        etape("Agent Gouvernance", "fail", f"{len(verd['violees'])} règle(s) violée(s) → aucune correction possible", **formulation)
        etape("Orchestrateur", "warn", f"Pas d'alternative proposée : aucune part de {symbole} n'est compatible avec le mandat. "
                                       "Le système le dit honnêtement.")
    else:
        etape("Agent Gouvernance", "ok", "La demande respecte toutes les règles du mandat", **formulation)

    # 5. Agent Explicabilité + vérificateur de fidélité
    nom_actif = str(univers.loc[univers["symbole"] == symbole, "nom"].iloc[0])
    contexte = {"persona": persona, "gabarit": gabarit, "symbole": symbole, "nom_actif": nom_actif, "mandat": mandat,
                "demande": d, "alternative": alt, "verdicts": verd}
    autorise = " ".join([str(persona["capital"]), persona["horizon"], persona["portefeuille_suppose_libelle"],
                         str(config.CALCUL["annee_scenario"]), str(len(verd["regles"])), seuils,
                         nombre(g["paris_effectifs_min"]) if g.get("paris_effectifs_min") is not None else ""])
    fiche, verif = rediger_verifie(contexte, journal, style, autorise, etape)

    return {"arret": False, "etapes": etapes, "journal": journal, "persona": persona, "gabarit": gabarit,
            "symbole": symbole, "demande": d, "alternative": alt, "verdicts": verd, "fiche": fiche,
            "verif": verif, "contexte": contexte, "source_donnees": source, "mandat": mandat, "autorise": autorise,
            "entree": entree}


def rediger_verifie(contexte: dict, journal, style: str, autorise: str, etape):
    """Rédaction + vérificateur de fidélité, avec régénération stricte puis gabarit sûr en dernier recours.
    AUCUN texte n'est affiché sans être passé par ici."""
    niveau = "avancé" if style == "avance" else "intermédiaire"
    fiche = explicabilite.rediger(contexte, journal, style)
    etape("Agent Explicabilité", "ok", f"Réponse rédigée au niveau « {niveau} »"
          + (" par le LLM" if fiche.get("auteur") == "llm" else f" ({fiche.get('auteur', 'gabarit')})"),
          note=f"{len(fiche['lignes'])} affirmations étiquetées (Fait / Hypothèse / Scénario fictif), reliées à leurs traces.")
    version = len([t for t in journal.traces if t["titre"].startswith("Vérification de fidélité")]) + 1
    verif = fidelite.verifier(journal, fiche, autorise, version)
    if not verif["ok"]:
        etape("Vérificateur de fidélité", "fail", "Réponse rejetée → régénération en mode strict",
              note=verif["motif"] + ".", trace=verif["trace"])
        fiche = explicabilite.rediger(contexte, journal, style, strict=True)
        verif = fidelite.verifier(journal, fiche, autorise, version + 1)
        if not verif["ok"]:                     # dernier recours : gabarit sûr
            fiche = explicabilite._gabarit_texte(contexte, style)
            verif = fidelite.verifier(journal, fiche, autorise, version + 2)
    etape("Vérificateur de fidélité", "ok" if verif["ok"] else "fail", "Réponse validée" if verif["ok"] else "Réponse non validée",
          note=f"{verif['total']}/{verif['total']} chiffres retrouvés dans les traces." if verif["ok"] else "", trace=verif["trace"])
    return fiche, verif


def reformuler(res: dict, style: str, on_etape=None) -> dict:
    """Bouton « plus simple / plus technique » : nouvelle rédaction, VÉRIFIÉE comme la première."""
    nouvelles = []

    def etape(agent, statut, texte, **details):
        e = {"agent": agent, "statut": statut, "texte": texte, **details}
        nouvelles.append(e)
        if on_etape:
            on_etape(e)

    res["fiche"], res["verif"] = rediger_verifie(res["contexte"], res["journal"], style, res["autorise"], etape)
    res["etapes"] = res["etapes"] + nouvelles
    return res


# ---------- « Et si j'acceptais plus de risque ? » (scénario fictif) ----------

def tolerance_suivante(res: dict) -> str | None:
    """Niveau de tolérance suivant (ordre de config/profil.yaml), ou None si le bouton serait sans effet :
    analyse arrêtée, déjà un scénario fictif, ou tolérance déjà au niveau le plus élevé."""
    if res.get("arret") or res.get("scenario_fictif"):
        return None
    ordre = config.PROFIL["tolerances"]
    actuelle = res["gabarit"]["id"]
    i = ordre.index(actuelle)
    return ordre[i + 1] if i + 1 < len(ordre) else None


def _part_acceptable(res: dict) -> str:
    """Point de bascule (part maximale compatible avec le mandat), tel que calculé par l'outil point_de_bascule."""
    b = res["demande"]["bascule"]
    return pct(b["part_max"]) if b["base_conforme"] and b["part_max"] is not None else "aucune"


def plus_de_risque(res: dict, on_etape=None) -> dict:
    """Relance executer() avec une COPIE du profil dont la tolérance passe au niveau suivant, MÊME message.
    L'analyse d'origine n'est jamais modifiée. Le bandeau est écrit par le code à partir des deux résultats."""
    suivante = tolerance_suivante(res)
    if suivante is None:
        raise ValueError("Aucun niveau de tolérance plus élevé à simuler pour cette analyse.")
    e = res["entree"]
    nouveau = executer(e["persona_id"], e["message"], on_etape=on_etape, profil_saisi=e["profil_saisi"],
                       tolerance=suivante)
    avant, apres = res["gabarit"]["label"], config.GABARITS[suivante]["label"]
    bandeau = f"Scénario fictif — tolérance « {apres} » au lieu de « {avant} »"
    if not nouveau["arret"]:
        bandeau += f" : part acceptable {_part_acceptable(res)} → {_part_acceptable(nouveau)}"
    nouveau["scenario_fictif"] = bandeau
    return nouveau
