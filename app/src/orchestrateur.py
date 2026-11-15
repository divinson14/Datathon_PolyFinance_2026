"""Orchestrateur DÉTERMINISTE : enchaîne les agents, gère la boucle de correction (max. 3 tentatives)
et publie chaque étape via on_etape (l'interface l'affiche au fur et à mesure)."""
from src import config
from src.agents import analyste, explicabilite, gouvernance, profil
from src.donnees.chargeur import charger
from src.formatage import nombre, pct
from src.traces.journal import Journal
from src.verif import fidelite, guardrails


def executer(persona_id: str | None, message: str, style: str | None = None, on_etape=None,
             profil_saisi: dict | None = None) -> dict:
    """persona_id = persona de référence ; OU profil_saisi = 5 champs (age, tolerance, horizon_ans, objectif, esg[, capital])."""
    prix, univers, source = charger()
    journal = Journal()
    etapes = []
    mandat = profil.construire_mandat(persona_id, profil_saisi, journal)
    persona, gabarit = mandat["profil"], mandat["gabarit"]
    style = style or ("avance" if persona["niveau_experience"] == "avance" else "inter")

    def etape(agent, statut, texte, **details):
        e = {"agent": agent, "statut": statut, "texte": texte, **details}
        etapes.append(e)
        if on_etape:
            on_etape(e)

    def arret():
        return {"arret": True, "etapes": etapes, "journal": journal, "persona": persona, "mandat": mandat}

    # 1. Garde-fous d'ENTRÉE : regex locale (rapide, sans AWS) PUIS Bedrock Guardrails (MODE=bedrock + guardrail configuré).
    #    Guardrails est consulté même si la regex bloque déjà : la trace montre le verdict des deux.
    local = profil.demande_de_transaction(message)
    g = guardrails.controler(journal, message, "INPUT")
    agent_gf = "Bedrock Guardrails" if g["statut"] in ("admis", "bloque") else "Garde-fou local"
    if g["statut"] == "bloque":
        etape(agent_gf, "fail", f"Demande bloquée par Bedrock Guardrails : {' ; '.join(g['politiques'])}. "
              "Aucune transaction réelle ni conseil personnalisé : reformule ta question pour une analyse en simulation.",
              trace=g["trace"], note="Garde-fou local : " + ("a aussi bloqué la demande." if local else "rien détecté."))
        return arret()
    if local:
        etape(agent_gf, "fail", "Demande bloquée : aucune transaction réelle n'est possible. "
              "Reformule ta question pour une analyse en simulation.", trace=g["trace"],
              note=f"Bloquée par le garde-fou local · {guardrails.portee(g)}"
                   + (" (Bedrock Guardrails n'a rien détecté)." if g["statut"] == "admis" else "."))
        return arret()
    etape(agent_gf, "ok" if g["statut"] == "admis" else "warn",
          f"Demande admise · analyse en mode simulation · {guardrails.portee(g)}", trace=g["trace"],
          note=g["detail"] if g["statut"] != "admis" else None)

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
            "verif": verif, "contexte": contexte, "source_donnees": source, "mandat": mandat, "autorise": autorise}


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

    # Garde-fou de SORTIE : Bedrock Guardrails sur le texte réellement affiché (MODE=bedrock + guardrail configuré).
    g = guardrails.controler(journal, guardrails.texte_fiche(fiche), "OUTPUT")
    if g["statut"] == "bloque":
        fiche = guardrails.fiche_remplacement(fiche, g["politiques"])
        etape("Bedrock Guardrails", "fail", "Réponse retenue par Bedrock Guardrails → message de remplacement sûr affiché",
              trace=g["trace"], note="Politiques déclenchées : " + " ; ".join(g["politiques"]) + ".")
    elif g["statut"] == "admis":
        etape("Bedrock Guardrails", "ok", "Réponse vérifiée par Bedrock Guardrails avant affichage", trace=g["trace"])
    elif g["statut"] == "indisponible":
        etape("Garde-fou local", "warn", "Réponse : garde-fou local seulement (Bedrock Guardrails indisponible ; "
              "vérificateur de fidélité appliqué)", trace=g["trace"], note=g["detail"])
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
