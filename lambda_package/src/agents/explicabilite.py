"""Agent Explicabilité : rédige la réponse UNIQUEMENT à partir des traces.
MODE=bedrock : le LLM rédige (prompts/explicabilite.md), puis le vérificateur contrôle.
MODE=local ou réponse illisible : gabarits de texte ci-dessous."""
import json
import re

from src import bedrock_client
from src.config import CALCUL, STYLES, prompt
from src.donnees.chargeur import donnees_fictives
from src.formatage import money, pct

# Mentions ajoutées par le CODE à chaque réponse (LLM ou gabarit), sans aucun chiffre :
# le vérificateur de fidélité n'a donc rien à y contrôler.
MENTION_CAD = ("Montants et rendements en dollars canadiens (CAD) : les actifs cotés en dollars américains "
               "sont convertis au taux quotidien de la Banque du Canada.")
MENTION_FICTIVES = ("Attention : DONNÉES FICTIVES de démonstration (data/processed/ absent) ; "
                    "les chiffres ne reflètent pas les marchés réels.")


def _mentions_obligatoires(fiche: dict) -> dict:
    """Ajoute aux limites la mention CAD et, le cas échéant, l'avertissement « données fictives »."""
    mentions = ([MENTION_FICTIVES] if donnees_fictives() else []) + [MENTION_CAD]
    limites = str(fiche.get("limites") or "").strip()
    fiche["limites"] = " ".join(m for m in mentions if m not in limites) + (" " + limites if limites else "")
    return fiche


_HYPOTHESES = {
    "faible_a_modere": {
        "avance": "Avec un horizon de {horizon}, une forte baisse laisse peu de temps pour récupérer.",
        "inter": "Ton horizon est court : après une grosse baisse, tu aurais peu de temps pour te refaire."},
    "modere": {
        "avance": "Un profil modéré cherche l'équilibre entre croissance et stabilité : un seul titre ne devrait pas dominer le risque.",
        "inter": "Ton profil cherche l'équilibre : un seul titre ne devrait pas décider à lui seul des hauts et des bas de ton portefeuille."},
    "eleve": {
        "avance": "Un horizon de {horizon} tolère la volatilité, mais un profil élevé n'autorise pas qu'un seul titre porte l'essentiel du risque.",
        "inter": "Avec un long horizon, tu peux encaisser des hauts et des bas. Mais « risque élevé » ne veut pas dire « tout est acceptable » : "
                 "si un seul titre fait bouger tout ton portefeuille, tu n'es plus vraiment diversifiée."},
}


def _hypothese(persona: dict, style: str) -> str:
    cle = "avance" if style == "avance" else "inter"
    texte = _HYPOTHESES.get(persona["risque"], _HYPOTHESES["modere"])[cle].format(horizon=persona["horizon"])
    prefixe = ("Les seuils viennent du gabarit fixé par l'équipe ; ce sont des hypothèses, pas des normes. " if cle == "avance"
               else "Les limites de ton profil sont un choix documenté de l'équipe, pas une vérité absolue. ")
    return prefixe + texte


def _ligne_tension(c: dict) -> dict | None:
    """Tension entre champs du profil (ex. tolérance élevée + horizon court), relevée par l'Agent Profil."""
    mandat = c.get("mandat") or {}
    if not mandat.get("tensions"):
        return None
    return {"tag": "Hypothèse", "texte": "Point d'attention sur ton profil : " + " ; ".join(mandat["tensions"])
            + ". Les limites appliquées restent celles de la tolérance indiquée.", "traces": [mandat["trace"]]}


def _ligne_manquante(c: dict) -> dict | None:
    """Information manquante (ex. ESG non évalué) : dite explicitement, jamais présentée comme conforme."""
    manquantes = c["verdicts"].get("manquantes") or []
    if not manquantes:
        return None
    detail = " ; ".join(f"{r['regle']} : {r['valeur']}" for r in manquantes)
    return {"tag": "Hypothèse", "texte": f"Information manquante ({detail}). Le système ne peut pas confirmer ce critère : "
            "à vérifier avant toute décision.", "traces": [c["verdicts"]["trace"]]}


def _ligne_bascule(c: dict, style: str) -> dict | None:
    b, s, nom = c["demande"]["bascule"], c["symbole"], c["nom_actif"]
    if not b["base_conforme"]:
        return {"tag": "Fait", "texte": "Le portefeuille supposé ne respecte déjà pas toutes les limites du profil : "
                + ", ".join(b["limitantes"]).lower() + ".", "traces": [b["trace"]]}
    if not b["limitantes"]:
        return None
    seuil = b["premiere_violation"][b["limitantes"][0]]
    regle = b["limitantes"][0].lower()
    if b["part_max"] == 0:
        texte = (f"Point de bascule : dès {pct(seuil)} de {s}, la règle « {regle} » est franchie ; aucune part n'est compatible avec le profil."
                 if style == "avance" else
                 f"Même une petite part de {nom} ({pct(seuil)}) dépasse déjà une limite de ton profil : {regle}.")
    else:
        texte = (f"Point de bascule : jusqu'à {pct(b['part_max'])} de {s}, toutes les règles sont respectées ; "
                 f"à {pct(seuil)}, la première règle franchie est « {regle} »." if style == "avance" else
                 f"Le point où ça bascule : jusqu'à {pct(b['part_max'])} en {nom}, ton portefeuille reste cohérent avec ton profil. "
                 f"À {pct(seuil)}, il ne l'est plus ({regle}).")
    return {"tag": "Fait", "texte": texte, "traces": [b["trace"]]}


def _gabarit_texte(c: dict, style: str) -> dict:
    p, g, s = c["persona"], c["gabarit"], c["symbole"]
    nom = c["nom_actif"]
    d, alt, verd = c["demande"], c["alternative"], c["verdicts"]
    m = d["mesures"]
    n = len(verd["violees"])
    rend = d["rejeu"]["rend"]
    w = pct(d["part"])
    risque = pct(m["parts_risque"].get(s, 0.0))
    lim_risque = pct(g["part_risque_max_par_titre"])
    annee = str(CALCUL["annee_scenario"])
    lignes = []
    if style == "avance":
        intro = (f"Demande analysée : {w} en {s}. Elle respecte les {len(verd['regles'])} règles de votre mandat." if n == 0 else
                 f"Demande analysée : {w} en {s}. {n} règle(s) de votre mandat ne sont pas respectées ; voici le détail"
                 + (" et la limite de votre mandat." if alt else " ; aucune part n'est compatible avec le mandat."))
        lignes.append({"tag": "Fait", "texte": f"Part des dollars ≠ part du risque : {s} représenterait {w} du capital mais "
                       f"{risque} du risque du portefeuille (limite par titre : {lim_risque}).", "traces": [m["trace"]]})
        lignes.append({"tag": "Fait", "texte": f"Volatilité annualisée : {pct(m['vol'])} (limite {pct(g['volatilite_max'])}) ; "
                       f"pire baisse sur la fenêtre : {pct(m['pire_baisse'])} (limite {pct(g['pire_baisse_max'])}).",
                       "traces": [m["trace"]]})
        if n:
            lignes.append({"tag": "Fait", "texte": "Règles non respectées : " + " ; ".join(
                f"{r['regle'].lower()} ({r['valeur']} pour une limite de {r['limite'].replace('≤ ', '').replace('≥ ', '')})"
                for r in verd["violees"]) + ".", "traces": [verd["trace"]]})
        lb = _ligne_bascule(c, style)
        if lb:
            lignes.append(lb)
        lignes.append({"tag": "Fait", "texte": f"Rejeu {annee} : {pct(rend)} ({money(d['rejeu']['perte'])}) avec {w} de {s}, contre "
                       f"{pct(d['base']['rend'])} ({money(d['base']['perte'])}) pour le portefeuille actuel.",
                       "traces": [d["rejeu"]["trace"], d["base"]["trace"]]})
        if d["macro"].get("resume"):
            lignes.append({"tag": "Fait", "texte": f"Contexte : taux directeur de la Banque du Canada en {annee}, {d['macro']['resume']}.",
                           "traces": [d["macro"]["trace"]]})
        for lm in (_ligne_tension(c), _ligne_manquante(c)):
            if lm:
                lignes.append(lm)
        lignes.append({"tag": "Hypothèse", "texte": _hypothese(p, style), "traces": []})
        if alt:
            am = alt["mesures"]
            lignes.append({"tag": "Scénario fictif", "texte": f"Vérification au point de bascule : à {pct(alt['part'])} de {s}, toutes les règles "
                           f"du mandat sont respectées ({s} porterait {pct(am['parts_risque'].get(s, 0.0))} du risque ; volatilité {pct(am['vol'])} ; "
                           f"rejeu {annee} {pct(alt['rejeu']['rend'])}).",
                           "traces": [am["trace"], alt["rejeu"]["trace"], alt["verdicts"]["trace"]]})
        limites = ("Fenêtre de 5 ans (un seul cycle de taux) et biais du survivant : les performances passées ne prédisent pas "
                   "les résultats futurs. La volatilité et la pire baisse ne sont que deux indicateurs de risque. "
                   f"Portefeuille actuel supposé ({p['portefeuille_suppose_libelle']}), poids constants.")
    else:
        intro = (f"Bonne nouvelle : {w} en {nom}, ça reste dans les limites de ton profil." if n == 0 else
                 f"En bref : {w} en {nom}, c'est plus de risque que ton profil ne le permet. "
                 + ("Je t'explique pourquoi, et je te montre où se situe la limite de ton profil." if alt
                    else "Aucune part n'est compatible avec les limites de ton profil."))
        lignes.append({"tag": "Fait", "texte": f"En dollars, {nom} ferait {w} de ton portefeuille. En risque, il en porterait {risque} : "
                       f"c'est la part des hauts et des bas qui viendrait de lui. Ton profil fixe un maximum de {lim_risque} par titre.",
                       "traces": [m["trace"]]})
        v = m["vol"]
        lignes.append({"tag": "Fait", "texte": (f"La volatilité (l'ampleur des hausses et des baisses) serait de {pct(v)} : ça reste sous le maximum de {pct(g['volatilite_max'])} de ton profil."
                       if v <= g["volatilite_max"] else
                       f"Ton portefeuille ferait de plus grosses montagnes russes que prévu : sa volatilité (l'ampleur des hausses et des baisses) serait de {pct(v)}, alors que ton profil fixe un maximum de {pct(g['volatilite_max'])}."),
                       "traces": [m["trace"]]})
        if n:
            lignes.append({"tag": "Fait", "texte": "Ce qui coince : " + ", ".join(r["regle"].lower() for r in verd["violees"]) + ".", "traces": [verd["trace"]]})
        lb = _ligne_bascule(c, style)
        if lb:
            lignes.append(lb)
        lignes.append({"tag": "Fait", "texte": f"Si tu avais mis {w} en {nom} début {annee}, tes {money(p['capital'])} seraient devenus environ "
                       f"{money(d['rejeu']['final'])} en fin d'année ({pct(rend)}). Sans {nom}, ils seraient à {money(d['base']['final'])}.",
                       "traces": [d["rejeu"]["trace"], d["base"]["trace"]]})
        for lm in (_ligne_tension(c), _ligne_manquante(c)):
            if lm:
                lignes.append(lm)
        lignes.append({"tag": "Hypothèse", "texte": _hypothese(p, style), "traces": []})
        if alt:
            lignes.append({"tag": "Scénario fictif", "texte": f"À la limite de ton profil ({pct(alt['part'])} en {nom}), toutes les règles sont respectées. "
                           f"Simulé sur {annee}, ton portefeuille serait passé à environ {money(alt['rejeu']['final'])}.",
                           "traces": [alt["mesures"]["trace"], alt["rejeu"]["trace"], alt["verdicts"]["trace"]]})
        limites = (f"{annee} et les 5 dernières années ne sont que des exemples du passé : ça ne dit pas ce qui arrivera demain. "
                   f"On a aussi supposé ton portefeuille actuel : {p['portefeuille_suppose_libelle']}.")
    return _mentions_obligatoires({"intro": intro, "lignes": lignes, "limites": limites, "style": style,
                                   "auteur": "gabarit"})


def rediger(contexte: dict, journal, style: str, strict: bool = False) -> dict:
    if not bedrock_client.actif():
        return _gabarit_texte(contexte, style)
    cle_style = {"avance": "avance", "inter": "intermediaire"}.get(style, style)
    traces = "\n".join(f"{t['id']} | {t['titre']} | entrées : {t['entrees']} | sortie : {t['sortie']}" for t in journal.traces)
    ctx = {"persona": {k: contexte["persona"][k] for k in ("nom", "horizon", "capital", "portefeuille_suppose_libelle")},
           "gabarit": contexte["gabarit"], "symbole": contexte["symbole"],
           "regles_violees": [r["regle"] for r in contexte["verdicts"]["violees"]],
           "alternative_trouvee": contexte["alternative"] is not None,
           "point_de_bascule_trace": contexte["demande"]["bascule"]["trace"]}
    texte = (prompt("explicabilite").replace("{style}", STYLES[cle_style])
             .replace("{traces}", traces).replace("{contexte}", json.dumps(ctx, ensure_ascii=False)))
    if strict:
        texte += ("\n\nATTENTION : une version précédente a été rejetée (chiffre absent des traces ou formulation de conseil). "
                  "Recopie les chiffres EXACTEMENT et décris uniquement des limites, sans jamais dire quoi faire.")
    try:
        rep = bedrock_client.appeler_json(texte, modele="redaction", max_tokens=4000)
    except Exception as e:                    # identifiants expirés, réseau, réponse tronquée ou illisible : la démo continue
        fiche = _gabarit_texte(contexte, style)
        fiche["auteur"] = f"gabarit (repli : {type(e).__name__} — {str(e)[:160]})"
        return fiche
    manquantes = {"intro", "lignes", "limites"} - set(rep)
    if manquantes or not isinstance(rep.get("lignes"), list):
        fiche = _gabarit_texte(contexte, style)
        fiche["auteur"] = f"gabarit (repli : format inattendu, clés manquantes {sorted(manquantes)})"
        return fiche
    rep.update(style=style, auteur="llm")
    return _mentions_obligatoires(rep)
