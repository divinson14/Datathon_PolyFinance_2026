"""Agent Explicabilité : rédige la réponse UNIQUEMENT à partir des traces.
MODE=bedrock : le LLM rédige (prompts/explicabilite.md), puis le vérificateur contrôle.
MODE=local ou réponse illisible : gabarits de texte ci-dessous."""
import json

from src import bedrock_client
from src.config import STYLES, prompt
from src.formatage import money, pct


def _hypothese(persona: dict, style: str, perte: str) -> str:
    prudent = persona["risque"] in ("faible_a_modere",)
    if style == "avance":
        return (f"Les seuils viennent du gabarit fixé par l'équipe. Avec un horizon de {persona['horizon']}, "
                f"une perte de {perte} laisse peu de temps pour récupérer." if prudent else
                f"Les seuils viennent du gabarit fixé par l'équipe. Un horizon de {persona['horizon']} tolère la volatilité, "
                "mais concentrer une grande part sur un seul titre réduit la diversification.")
    return ("Ton horizon est court : après une grosse baisse, tu aurais peu de temps pour te refaire. "
            "Les limites de ton profil sont un choix documenté de l'équipe." if prudent else
            "Avec un long horizon, tu peux encaisser des hauts et des bas. Mais miser une grosse part sur une seule "
            "entreprise, c'est mettre beaucoup d'œufs dans le même panier : « risque élevé » ne veut pas dire « tout est acceptable ».")


def _gabarit_texte(c: dict, style: str, halluciner: bool = False) -> dict:
    p, g, s = c["persona"], c["gabarit"], c["symbole"]
    nom = c["nom_actif"]
    d, alt, verd = c["demande"], c["alternative"], c["verdicts"]
    n = len(verd["violees"])
    rend = d["rejeu"]["rend"] - (0.031 if halluciner else 0)        # erreur volontaire pour la démo
    w = pct(d["part"], 0)
    lignes = []
    if style == "avance":
        intro = (f"Demande analysée : {w} en {s}. Elle respecte les {len(verd['regles'])} règles de votre mandat." if n == 0 else
                 f"Demande analysée : {w} en {s}. {n} règle(s) de votre mandat ne sont pas respectées ; voici le détail"
                 + (" et une alternative conforme." if alt else ", et aucune alternative conforme n'a été trouvée."))
        lignes.append({"tag": "Fait", "texte": f"Rejeu 2022 : {pct(rend)} ({money(d['rejeu']['perte'])}) avec {w} de {s}, contre "
                       f"{pct(d['base']['rend'])} ({money(d['base']['perte'])}) pour le portefeuille actuel.",
                       "traces": [d["rejeu"]["trace"], d["base"]["trace"]]})
        lignes.append({"tag": "Fait", "texte": f"Volatilité annualisée du portefeuille demandé : {pct(d['vol']['vol'])}, "
                       f"pour une limite de {pct(g['volatilite_max'])} dans le gabarit « {g['label']} ».", "traces": [d["vol"]["trace"]]})
        if n:
            lignes.append({"tag": "Fait", "texte": "Règles non respectées : " + " ; ".join(
                f"{r['regle'].lower()} ({r['valeur']} pour une limite de {r['limite'].replace('≤ ', '').replace('≥ ', '')})"
                for r in verd["violees"]) + ".", "traces": [verd["trace"]]})
        lignes.append({"tag": "Fait", "texte": "Contexte : la Banque du Canada relève son taux directeur à partir du 2 mars 2022 (0,25 % → 0,50 %).",
                       "traces": [d["macro"]["trace"]]})
        lignes.append({"tag": "Hypothèse", "texte": _hypothese(p, style, pct(d["rejeu"]["rend"])), "traces": []})
        if alt:
            lignes.append({"tag": "Scénario fictif", "texte": f"Alternative conforme : une poche satellite de {pct(alt['part'], 0)} en {s} "
                           f"donne {pct(alt['rejeu']['rend'])} ({money(alt['rejeu']['perte'])}) en 2022 et une volatilité de {pct(alt['vol']['vol'])}.",
                           "traces": [alt["rejeu"]["trace"], alt["vol"]["trace"], alt["verdicts"]["trace"]]})
        limites = ("Un seul scénario historique (2022) : les performances passées ne prédisent pas les résultats futurs. "
                   "La volatilité n'est qu'un indicateur de risque parmi d'autres. "
                   f"Portefeuille actuel supposé ({p['portefeuille_suppose_libelle']}), faute d'information.")
    else:
        intro = (f"Bonne nouvelle : {w} en {nom}, ça reste dans les limites de ton profil." if n == 0 else
                 f"En bref : {w} en {nom}, c'est plus de risque que ton profil ne le permet. "
                 + ("Je t'explique pourquoi, et je te propose une option plus équilibrée." if alt else "Et je n'ai pas trouvé d'option conforme."))
        lignes.append({"tag": "Fait", "texte": f"Si tu avais mis {w} en {nom} début 2022, tes {money(p['capital'])} seraient devenus environ "
                       f"{money(d['rejeu']['final'])} en fin d'année ({pct(rend)}). Sans {nom}, ils seraient à {money(d['base']['final'])}.",
                       "traces": [d["rejeu"]["trace"], d["base"]["trace"]]})
        v = d["vol"]["vol"]
        lignes.append({"tag": "Fait", "texte": (f"La volatilité (l'ampleur des hausses et des baisses) serait de {pct(v)} : ça reste sous le maximum de {pct(g['volatilite_max'])} de ton profil."
                       if v <= g["volatilite_max"] else
                       f"Ton portefeuille ferait de plus grosses montagnes russes que prévu : sa volatilité (l'ampleur des hausses et des baisses) serait de {pct(v)}, alors que ton profil fixe un maximum de {pct(g['volatilite_max'])}."),
                       "traces": [d["vol"]["trace"]]})
        if n:
            lignes.append({"tag": "Fait", "texte": "Ce qui coince : " + ", ".join(r["regle"].lower() for r in verd["violees"]) + ".", "traces": [verd["trace"]]})
        lignes.append({"tag": "Hypothèse", "texte": _hypothese(p, style, ""), "traces": []})
        if alt:
            lignes.append({"tag": "Scénario fictif", "texte": f"Une option plus équilibrée : une part de {pct(alt['part'], 0)} en {nom}. En 2022, ton portefeuille "
                           f"serait passé à environ {money(alt['rejeu']['final'])}, et ça respecte ton profil.",
                           "traces": [alt["rejeu"]["trace"], alt["vol"]["trace"], alt["verdicts"]["trace"]]})
        limites = ("2022 n'est qu'un exemple du passé : ça ne dit pas ce qui arrivera demain. "
                   f"On a aussi supposé que ton portefeuille actuel est {p['portefeuille_suppose_libelle']}.")
    return {"intro": intro, "lignes": lignes, "limites": limites, "style": style, "auteur": "gabarit"}


def rediger(contexte: dict, journal, style: str, halluciner: bool = False, strict: bool = False) -> dict:
    if not bedrock_client.actif():
        return _gabarit_texte(contexte, style, halluciner)
    cle_style = {"avance": "avance", "inter": "intermediaire"}.get(style, style)
    traces = "\n".join(f"{t['id']} | {t['titre']} | entrées : {t['entrees']} | sortie : {t['sortie']}" for t in journal.traces)
    ctx = {"persona": {k: contexte["persona"][k] for k in ("nom", "horizon", "capital", "portefeuille_suppose_libelle")},
           "gabarit": contexte["gabarit"], "symbole": contexte["symbole"],
           "regles_violees": [r["regle"] for r in contexte["verdicts"]["violees"]],
           "alternative_trouvee": contexte["alternative"] is not None}
    texte = (prompt("explicabilite").replace("{style}", STYLES[cle_style])
             .replace("{traces}", traces).replace("{contexte}", json.dumps(ctx, ensure_ascii=False)))
    if strict:
        texte += "\n\nATTENTION : une version précédente contenait un chiffre absent des traces. Recopie les chiffres EXACTEMENT."
    rep = bedrock_client.appeler_json(texte, modele="redaction")
    if not rep or not {"intro", "lignes", "limites"} <= set(rep):
        return _gabarit_texte(contexte, style)
    rep.update(style=style, auteur="llm")
    return rep
