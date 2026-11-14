"""Orchestrateur DÉTERMINISTE : enchaîne les agents, gère la boucle de correction (max. 3 tentatives)
et publie chaque étape via on_etape (l'interface l'affiche au fur et à mesure)."""
from src import config
from src.agents import analyste, explicabilite, gouvernance, profil
from src.donnees.chargeur import charger
from src.formatage import nombre, pct
from src.traces.journal import Journal
from src.verif import fidelite


def executer(persona_id: str, message: str, style: str | None = None, halluciner: bool = False, on_etape=None) -> dict:
    persona = config.PERSONAS[persona_id]
    gabarit = config.GABARITS[persona["risque"]]
    style = style or ("avance" if persona["niveau_experience"] == "avance" else "inter")
    prix, univers, source = charger()
    journal = Journal()
    etapes = []

    def etape(agent, statut, texte, **details):
        e = {"agent": agent, "statut": statut, "texte": texte, **details}
        etapes.append(e)
        if on_etape:
            on_etape(e)

    def arret():
        return {"arret": True, "etapes": etapes, "journal": journal, "persona": persona}

    # 1. Garde-fou
    if profil.demande_de_transaction(message):
        etape("Bedrock Guardrails", "fail", "Demande bloquée : aucune transaction réelle n'est possible. Reformule ta question pour une analyse en simulation.")
        return arret()
    etape("Bedrock Guardrails", "ok", "Demande admise · analyse en mode simulation")

    # 2. Agent Profil
    dem = profil.extraire(message, persona, univers)
    if dem.get("symbole") is None:
        etape("Agent Profil", "warn", f"Actif non reconnu. L'univers couvre : {', '.join(univers['symbole'].astype(str))}. Précise l'actif visé.")
        return arret()
    if dem.get("part") is None:
        etape("Agent Profil", "warn", "Information manquante : quelle part du portefeuille souhaites-tu y mettre ? Je ne la devine pas à ta place.")
        return arret()
    symbole, part = dem["symbole"], float(dem["part"])
    g = gabarit
    seuils = (f"poids max/titre {pct(g['poids_max_par_titre'])} · part du risque max/titre {pct(g['part_risque_max_par_titre'])} · "
              f"vol. max {pct(g['volatilite_max'])} · pire baisse max {pct(g['pire_baisse_max'])} · "
              f"obligations min {pct(g['obligations_min'])} · crypto max {pct(g['crypto_max'])}")
    etape("Agent Profil", "warn", "Demande comprise · le portefeuille actuel est une hypothèse affichée",
          mandat=[("Actif demandé", symbole), ("Part demandée", pct(part)), ("Gabarit appliqué", f"« {g['label']} » (config/)"),
                  ("Seuils (hypothèses de l'équipe)", seuils),
                  ("Hypothèse", f"portefeuille actuel : {persona['portefeuille_suppose_libelle']}")])

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

    # 4. Agent Gouvernance + boucle de correction (vérification indépendante de chaque alternative)
    verd = gouvernance.verifier(journal, d, symbole, gabarit, univers, f"demande {pct(part)} {symbole}", persona)
    alt = None
    if verd["violees"]:
        etape("Agent Gouvernance", "fail", f"{len(verd['violees'])} règle(s) violée(s) → correction demandée à l'Analyste",
              regles=verd["regles"], trace=verd["trace"], consigne=verd["consigne"])
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
            v2 = gouvernance.verifier(journal, a, symbole, gabarit, univers, f"alternative {pct(choisie)} {symbole}", persona)
            if not v2["violees"]:
                a["verdicts"] = v2
                alt = a
                etape("Agent Gouvernance", "ok", f"{len(v2['regles'])} règles sur {len(v2['regles'])} respectées", regles=v2["regles"], trace=v2["trace"])
                break
            etape("Agent Gouvernance", "fail", f"Toujours {len(v2['violees'])} règle(s) violée(s) → nouvelle correction", regles=v2["regles"], trace=v2["trace"])
            consigne = (f"L'alternative à {pct(choisie)} de {symbole} viole encore : "
                        + ", ".join(r["regle"] for r in v2["violees"]) + ". Propose une part plus prudente.")
            part_prec = choisie
        if alt is None:
            raison = (verd["consigne"] if candidat is None else
                      f"aucune alternative conforme trouvée en {config.MAX_TENTATIVES} tentatives")
            etape("Orchestrateur", "warn", f"Pas d'alternative proposée : {raison} Le système le dit honnêtement.")
    else:
        etape("Agent Gouvernance", "ok", "La demande respecte toutes les règles du mandat", regles=verd["regles"], trace=verd["trace"])

    # 5. Agent Explicabilité + vérificateur de fidélité
    nom_actif = str(univers.loc[univers["symbole"] == symbole, "nom"].iloc[0])
    contexte = {"persona": persona, "gabarit": gabarit, "symbole": symbole, "nom_actif": nom_actif,
                "demande": d, "alternative": alt, "verdicts": verd}
    autorise = " ".join([str(persona["capital"]), persona["horizon"], persona["portefeuille_suppose_libelle"],
                         str(config.CALCUL["annee_scenario"]), str(len(verd["regles"])), seuils,
                         nombre(g["paris_effectifs_min"]) if g.get("paris_effectifs_min") is not None else ""])
    fiche = explicabilite.rediger(contexte, journal, style, halluciner=halluciner)
    etape("Agent Explicabilité", "ok", f"Réponse rédigée au niveau « {'avancé' if style == 'avance' else 'intermédiaire'} »",
          note=f"{len(fiche['lignes'])} affirmations étiquetées (Fait / Hypothèse / Scénario fictif), reliées à leurs traces.")
    verif = fidelite.verifier(journal, fiche, autorise, 1)
    if not verif["ok"]:
        etape("Vérificateur de fidélité", "fail", "Réponse rejetée → régénération en mode strict",
              note=f"Chiffre(s) introuvable(s) dans les traces : {', '.join(verif['rejets'])}", trace=verif["trace"])
        fiche = explicabilite.rediger(contexte, journal, style, strict=True)
        verif = fidelite.verifier(journal, fiche, autorise, 2)
        if not verif["ok"]:                     # dernier recours : gabarit sûr
            fiche = explicabilite._gabarit_texte(contexte, style)
            verif = fidelite.verifier(journal, fiche, autorise, 3)
    etape("Vérificateur de fidélité", "ok" if verif["ok"] else "fail", "Réponse validée" if verif["ok"] else "Réponse non validée",
          note=f"{verif['total']}/{verif['total']} chiffres retrouvés dans les traces." if verif["ok"] else "", trace=verif["trace"])

    return {"arret": False, "etapes": etapes, "journal": journal, "persona": persona, "gabarit": gabarit,
            "symbole": symbole, "demande": d, "alternative": alt, "verdicts": verd, "fiche": fiche,
            "verif": verif, "contexte": contexte, "source_donnees": source}
