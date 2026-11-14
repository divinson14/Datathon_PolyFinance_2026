"""Orchestrateur DÉTERMINISTE : enchaîne les agents, gère la boucle de correction (max. 3 tentatives)
et publie chaque étape via on_etape (l'interface l'affiche au fur et à mesure)."""
from src import config
from src.agents import analyste, explicabilite, gouvernance, profil
from src.donnees.chargeur import charger
from src.formatage import pct
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
    etape("Agent Profil", "warn", "Demande comprise · 1 information manquante remplacée par une hypothèse affichée",
          mandat=[("Actif demandé", symbole), ("Part demandée", pct(part, 0)), ("Gabarit appliqué", f"« {gabarit['label']} » (config/)"),
                  ("Seuils", f"poids max {pct(gabarit['poids_max_par_titre'])} · vol. max {pct(gabarit['volatilite_max'])} · perte max {pct(gabarit['perte_max_toleree'])}"),
                  ("Hypothèse", f"portefeuille actuel {persona['portefeuille_suppose_libelle']}")])

    # 3. Agent Analyste, tentative 1
    d = analyste.analyser_demande(journal, persona, symbole, part)
    etape("Agent Analyste · tentative 1", "ok", "5 appels d'outils de calcul", calculs=[
        (f"Volatilité de {symbole}", pct(d["stats"]["vol"]), d["stats"]["trace"]),
        ("Contexte des taux 2022", "1re hausse le 2 mars", d["macro"]["trace"]),
        ("Rejeu 2022 · portefeuille actuel", pct(d["base"]["rend"]), d["base"]["trace"]),
        (f"Rejeu 2022 · demande {pct(part, 0)}", pct(d["rejeu"]["rend"]), d["rejeu"]["trace"]),
        (f"Volatilité · demande {pct(part, 0)}", pct(d["vol"]["vol"]), d["vol"]["trace"])])

    # 4. Agent Gouvernance + boucle de correction
    verd = gouvernance.verifier(journal, d, symbole, gabarit, univers, f"demande {pct(part, 0)} {symbole}")
    alt = None
    if verd["violees"]:
        etape("Agent Gouvernance", "fail", f"{len(verd['violees'])} règle(s) violée(s) → correction demandée à l'Analyste",
              regles=verd["regles"], trace=verd["trace"], consigne=verd["consigne"])
        candidat = gouvernance.prochaine_part(part, gabarit, premiere_correction=True)
        for t in range(2, config.MAX_TENTATIVES + 1):
            a = analyste.analyser_alternative(journal, persona, symbole, candidat, t)
            etape(f"Agent Analyste · tentative {t}", "ok", f"Alternative testée : {pct(candidat, 0)} en {symbole}", calculs=[
                (f"Rejeu 2022 · {pct(candidat, 0)} {symbole}", pct(a["rejeu"]["rend"]), a["rejeu"]["trace"]),
                (f"Volatilité · {pct(candidat, 0)} {symbole}", pct(a["vol"]["vol"]), a["vol"]["trace"])])
            v2 = gouvernance.verifier(journal, a, symbole, gabarit, univers, f"alternative {pct(candidat, 0)} {symbole}")
            if not v2["violees"]:
                a["verdicts"] = v2
                alt = a
                etape("Agent Gouvernance", "ok", f"{len(v2['regles'])} règles sur {len(v2['regles'])} respectées", regles=v2["regles"], trace=v2["trace"])
                break
            etape("Agent Gouvernance", "fail", f"Toujours {len(v2['violees'])} règle(s) violée(s) → nouvelle correction", regles=v2["regles"], trace=v2["trace"])
            candidat = gouvernance.prochaine_part(candidat, gabarit, premiere_correction=False)
        if alt is None:
            etape("Orchestrateur", "warn", f"Aucune alternative conforme trouvée en {config.MAX_TENTATIVES} tentatives : le système le dit honnêtement.")
    else:
        etape("Agent Gouvernance", "ok", "La demande respecte toutes les règles du mandat", regles=verd["regles"], trace=verd["trace"])

    # 5. Agent Explicabilité + vérificateur de fidélité
    nom_actif = str(univers.loc[univers["symbole"] == symbole, "nom"].iloc[0])
    contexte = {"persona": persona, "gabarit": gabarit, "symbole": symbole, "nom_actif": nom_actif,
                "demande": d, "alternative": alt, "verdicts": verd}
    autorise = (f"{persona['capital']} {persona['horizon']} {persona['portefeuille_suppose_libelle']} 2022 "
                f"{pct(gabarit['poids_max_par_titre'])} {pct(gabarit['volatilite_max'])} {pct(gabarit['perte_max_toleree'])} "
                f"{len(verd['regles'])}")
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
