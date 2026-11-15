"""Agent Analyste : un agent Strands (SDK AWS, modèle Amazon Bedrock) CHOISIT ses outils de calcul.

- Le modèle ne calcule AUCUN chiffre : chaque outil @tool appelle src/outils/calculs.py, qui écrit une trace.
- Les outils sont créés PAR ANALYSE, en fermeture sur le journal, le persona et l'actif demandé.
- Filet de sécurité : plan fixe si MODE=local ou ANALYSTE=fixe, ou si l'appel Strands/Bedrock échoue
  (trace « Repli sur le plan fixe »).
- Si le modèle oublie un calcul indispensable, l'orchestrateur le complète (mention dans l'agent de la trace).
- Le dictionnaire renvoyé est identique à celui du plan fixe, plus « extras » et « raisonnement ».
"""
import re
import threading

from src import bedrock_client, config
from src.formatage import money, nombre, pct
from src.outils import calculs
from src.verif import fidelite

COMPLETE = " (complété par l'orchestrateur)"
RE_PART = re.compile(r"PART\s*=\s*([-+]?\d+(?:[.,]\d+)?)", re.I)


def _mode_strands() -> bool:
    return config.MODE == "bedrock" and config.ANALYSTE != "fixe"


def _cle(part: float) -> float:
    return round(float(part), 4)


# ---------- Plan fixe (filet de sécurité) ----------

def _plan_fixe_demande(journal, persona, symbole, part, gabarit, univers, agent) -> dict:
    base = persona["portefeuille_suppose"]
    poids = calculs.poids_avec_position(base, symbole, part)
    lib = f"demande {pct(part)} {symbole}"
    mesures = calculs.analyse_portefeuille(journal, poids, lib, agent)
    return {
        "poids": poids, "part": part,
        "stats": calculs.statistiques(journal, symbole, agent),
        "macro": calculs.contexte_macro(journal, agent),
        "mesures_base": calculs.analyse_portefeuille(journal, base, "portefeuille actuel", agent),
        "mesures": mesures,
        "vol": mesures,                                     # alias : {"vol", "trace"}
        "bascule": calculs.point_de_bascule(journal, base, symbole, gabarit, univers, agent, persona),
        "base": calculs.rejeu_2022(journal, base, persona["capital"], "portefeuille actuel", agent),
        "rejeu": calculs.rejeu_2022(journal, poids, persona["capital"], lib, agent),
        "extras": [], "raisonnement": "",
    }


def _plan_fixe_alternative(journal, persona, symbole, part, agent) -> dict:
    poids = calculs.poids_avec_position(persona["portefeuille_suppose"], symbole, part)
    lib = f"alternative {pct(part)} {symbole}"
    mesures = calculs.analyse_portefeuille(journal, poids, lib, agent)
    return {
        "poids": poids, "part": part, "mesures": mesures, "vol": mesures,
        "rejeu": calculs.rejeu_2022(journal, poids, persona["capital"], lib, agent),
        "extras": [], "raisonnement": "",
    }


def _tracer_repli(journal, agent: str, erreur: Exception) -> None:
    journal.log(titre="Repli sur le plan fixe", agent=agent, outil="Agent Strands (Amazon Bedrock)",
                entrees="appel de l'agent Strands", sortie=f"erreur {type(erreur).__name__} : plan fixe utilisé",
                source="orchestrateur", periode="—")


# ---------- Outils Strands, créés par analyse ----------

class _Collecte:
    """Mémorise chaque appel d'outil du modèle (dans l'ordre) pour assembler le dictionnaire final."""

    def __init__(self):
        self.appels: list[tuple[str, float | None, str, dict]] = []     # (type, part, libellé, résultat)
        self.verrou = threading.Lock()                                   # outils exécutés un par un

    def trouver(self, type_: str, part: float | None = None) -> dict | None:
        cle = None if part is None else _cle(part)
        return next((r for t, p, _, r in self.appels if t == type_ and p == cle), None)


def _creer_outils(journal, persona: dict, symbole: str, agent: str, libelle_de, collecte: _Collecte) -> list:
    """Outils @tool en fermeture sur cette analyse. Le modèle lit les docstrings (format Google) pour choisir."""
    from strands import tool

    base = persona["portefeuille_suppose"]
    capital = persona["capital"]
    annee = config.CALCUL["annee_scenario"]

    def poids_de(part_actif: float) -> dict:
        part_actif = float(part_actif)
        if not 0 <= part_actif <= 1:
            raise ValueError("part_actif doit être entre 0 et 1 (0.30 = 30 %).")
        return calculs.poids_avec_position(base, symbole, part_actif) if part_actif > 0 else dict(base)

    def noter(type_, part, lib, res):
        collecte.appels.append((type_, None if part is None else _cle(part), lib, res))

    @tool
    def statistiques_actif() -> dict:
        """Profil de risque de l'actif demandé, seul : volatilité annualisée et pire baisse sur 5 ans, en CAD.

        Returns:
            Identifiant de trace et valeurs formatées.
        """
        with collecte.verrou:
            r = calculs.statistiques(journal, symbole, agent)
            noter("stats", None, symbole, r)
            return {"trace": r["trace"], "actif": symbole, "volatilite": pct(r["vol"]), "pire_baisse": pct(r["pire_baisse"])}

    @tool
    def rejeu_2022(part_actif: float) -> dict:
        """Rejoue l'année 2022 (actions ET obligations en baisse) en achat-conservation, en CAD, sur le capital de l'investisseur.

        Args:
            part_actif: Part de l'actif demandé dans le portefeuille, entre 0 et 1 (0.30 = 30 %).
                Le reste du portefeuille actuel est réduit proportionnellement. 0 = portefeuille actuel.

        Returns:
            Identifiant de trace, rendement, perte et valeur finale formatés.
        """
        with collecte.verrou:
            lib = libelle_de(part_actif)
            r = calculs.rejeu_2022(journal, poids_de(part_actif), capital, lib, agent)
            noter("rejeu", part_actif, lib, r)
            return {"trace": r["trace"], "portefeuille": lib, "annee": annee, "rendement": pct(r["rend"]),
                    "perte": money(r["perte"]), "valeur_finale": money(r["final"])}

    @tool
    def volatilite_portefeuille(part_actif: float) -> dict:
        """Mesures de risque du portefeuille : volatilité annualisée, pire baisse, part du RISQUE portée par
        l'actif demandé (différente de sa part en dollars) et nombre de paris indépendants.

        Args:
            part_actif: Part de l'actif demandé dans le portefeuille, entre 0 et 1 (0.30 = 30 %).
                Le reste du portefeuille actuel est réduit proportionnellement. 0 = portefeuille actuel.

        Returns:
            Identifiant de trace et valeurs formatées.
        """
        with collecte.verrou:
            lib = libelle_de(part_actif)
            r = calculs.analyse_portefeuille(journal, poids_de(part_actif), lib, agent)
            noter("mesures", part_actif, lib, r)
            return {"trace": r["trace"], "portefeuille": lib, "volatilite": pct(r["vol"]),
                    "pire_baisse": pct(r["pire_baisse"]),
                    "part_du_risque_actif": pct(r["parts_risque"].get(symbole, 0.0)),
                    "paris_independants": nombre(r["paris_effectifs"])}

    @tool
    def pire_fenetre_12_mois(part_actif: float) -> dict:
        """Stress-test : pire rendement du portefeuille sur 12 mois consécutifs (252 jours de bourse),
        toutes fenêtres glissantes de l'historique, en achat-conservation.

        Args:
            part_actif: Part de l'actif demandé dans le portefeuille, entre 0 et 1 (0.30 = 30 %).
                Le reste du portefeuille actuel est réduit proportionnellement. 0 = portefeuille actuel.

        Returns:
            Identifiant de trace, pire rendement formaté et période (début → fin).
        """
        with collecte.verrou:
            lib = libelle_de(part_actif)
            r = calculs.pire_fenetre_12_mois(journal, poids_de(part_actif), lib, agent)
            noter("fenetre", part_actif, lib, r)
            if r["rend"] is None:
                return {"trace": r["trace"], "portefeuille": lib, "pire_rendement_12_mois": "historique trop court"}
            return {"trace": r["trace"], "portefeuille": lib, "pire_rendement_12_mois": pct(r["rend"]),
                    "periode": f"{r['debut']} → {r['fin']}"}

    @tool
    def contexte_taux_2022() -> dict:
        """Contexte macroéconomique : évolution du taux directeur de la Banque du Canada pendant 2022
        (série quotidienne, aucune information « du futur »).

        Returns:
            Identifiant de trace et résumé formaté.
        """
        with collecte.verrou:
            r = calculs.contexte_macro(journal, agent)
            noter("macro", None, "taux", r)
            return {"trace": r["trace"], "resume": r["resume"] or "série indisponible"}

    return [statistiques_actif, rejeu_2022, volatilite_portefeuille, pire_fenetre_12_mois, contexte_taux_2022]


def _creer_agent(outils: list):
    """Seul endroit où l'agent Strands est construit (remplacé par un faux agent dans les tests)."""
    from strands import Agent
    return Agent(model=bedrock_client.modele_strands("analyste"), tools=outils,
                 system_prompt=config.prompt("analyste"), callback_handler=None)


def _lancer_agent(journal, persona, symbole, agent, libelle_de, consigne: str) -> tuple[_Collecte, str]:
    collecte = _Collecte()
    outils = _creer_outils(journal, persona, symbole, agent, libelle_de, collecte)
    reponse = _creer_agent(outils)(consigne)
    return collecte, str(reponse).strip()


def _lire_part(texte: str) -> float | None:
    trouve = RE_PART.findall(texte or "")
    if not trouve:
        return None
    try:
        return float(trouve[-1].replace(",", "."))
    except ValueError:
        return None


def _extras(collecte: _Collecte, utilises: set) -> list[tuple[str, str, str]]:
    """Calculs supplémentaires choisis par le modèle : (libellé, valeur, id_trace)."""
    annee = config.CALCUL["annee_scenario"]
    vus, out = set(), []
    for type_, part, lib, r in collecte.appels:
        if r["trace"] in utilises or (type_, part) in vus or type_ in ("stats", "macro"):
            continue
        vus.add((type_, part))
        if type_ == "rejeu":
            out.append((f"Rejeu {annee} · {lib}", pct(r["rend"]), r["trace"]))
        elif type_ == "mesures":
            out.append((f"Volatilité / pire baisse · {lib}", f"{pct(r['vol'])} / {pct(r['pire_baisse'])}", r["trace"]))
        elif type_ == "fenetre":
            out.append((f"Pire fenêtre de 12 mois · {lib}",
                        "historique trop court" if r["rend"] is None else pct(r["rend"]), r["trace"]))
    return out


_LIGNE_PART = re.compile(r"^\s*PART\s*=.*$", re.M)
_ID_TRACE = re.compile(r"\bT-\d+\b")


def _note_verifiee(journal, texte: str, agent: str, consigne: str) -> str:
    """Le commentaire du modèle n'est affiché que s'il passe les MÊMES contrôles que l'Explicabilité :
    ligne technique PART= retirée ; chaque chiffre retrouvé dans les traces (ou la consigne) ; aucun conseil.
    Sinon il est masqué, avec la raison. Les chiffres du tableau viennent toujours des outils."""
    note = _LIGNE_PART.sub("", texte or "").strip()
    if not note:
        return ""
    trouves, rejets = fidelite.chiffres_introuvables(journal, _ID_TRACE.sub(" ", note), consigne)
    conseils = fidelite.formulations_de_conseil(note)
    motifs = ([f"chiffre(s) introuvable(s) dans les traces : {', '.join(rejets)}"] if rejets else []) + \
             ([f"formulation(s) de conseil : {', '.join(conseils)}"] if conseils else [])
    journal.log(titre="Commentaire de l'Analyste · vérification", agent="Vérificateur (code, sans LLM)",
                outil="chiffres_introuvables + formulations_de_conseil",
                entrees=f"{len(trouves)} chiffre(s) dans le commentaire du modèle ({agent})",
                sortie=(" · ".join(motifs) + " → commentaire masqué") if motifs
                       else f"{len(trouves)}/{len(trouves)} chiffres retrouvés dans les traces · 0 formulation de conseil",
                source="journal d'audit · config/garde_fous.yaml", periode="exécution courante")
    if motifs:
        return ("Commentaire du modèle masqué par le vérificateur (" + " ; ".join(motifs) + "). "
                "Les résultats du tableau ci-dessus viennent des outils de calcul et font foi.")
    return note


def _mandat_texte(persona: dict) -> str:
    g = config.GABARITS[persona["risque"]]
    paris = "non vérifié" if g.get("paris_effectifs_min") is None else nombre(g["paris_effectifs_min"])
    return (f"Investisseur : {persona['nom']}, profil de risque « {g['label']} », horizon {persona['horizon']}, "
            f"capital {money(persona['capital'])}.\n"
            f"Portefeuille actuel (hypothèse) : {persona['portefeuille_suppose_libelle']}.\n"
            f"Limites du mandat (config/gabarits_risque.yaml) : poids max/titre {pct(g['poids_max_par_titre'])} · "
            f"part du risque max/titre {pct(g['part_risque_max_par_titre'])} · volatilité max {pct(g['volatilite_max'])} · "
            f"pire baisse max {pct(g['pire_baisse_max'])} · obligations min {pct(g['obligations_min'])} · "
            f"crypto max {pct(g['crypto_max'])} · paris indépendants min {paris}.")


# ---------- Fonctions publiques (appelées par l'orchestrateur) ----------

def analyser_demande(journal, persona: dict, symbole: str, part: float, gabarit: dict, univers,
                     tentative: int = 1) -> dict:
    agent = f"Agent Analyste · tentative {tentative}"
    if not _mode_strands():
        return _plan_fixe_demande(journal, persona, symbole, part, gabarit, univers, agent)

    cle_demande = _cle(part)

    def libelle_de(x):
        x = _cle(x)
        if x == 0:
            return "portefeuille actuel"
        return f"{'demande' if x == cle_demande else 'variante'} {pct(x)} {symbole}"

    consigne = (f"{_mandat_texte(persona)}\n"
                f"Demande : ajouter {pct(part)} de {symbole} (part_actif = {cle_demande}).\n"
                f"Calculs minimum : statistiques_actif(), contexte_taux_2022(), rejeu_2022(0), volatilite_portefeuille(0), "
                f"rejeu_2022({cle_demande}), volatilite_portefeuille({cle_demande}).\n"
                f"Termine par la ligne PART={cle_demande}.")
    try:
        collecte, texte = _lancer_agent(journal, persona, symbole, agent, libelle_de, consigne)
    except Exception as e:                       # Bedrock indisponible, quota, SDK absent… → filet de sécurité
        _tracer_repli(journal, agent, e)
        d = _plan_fixe_demande(journal, persona, symbole, part, gabarit, univers, agent)
        d["raisonnement"] = f"Repli sur le plan fixe ({type(e).__name__})."
        return d

    base = persona["portefeuille_suppose"]
    poids = calculs.poids_avec_position(base, symbole, part)
    lib, ac = libelle_de(part), agent + COMPLETE
    mesures = collecte.trouver("mesures", part) or calculs.analyse_portefeuille(journal, poids, lib, ac)
    d = {
        "poids": poids, "part": part,
        "stats": collecte.trouver("stats") or calculs.statistiques(journal, symbole, ac),
        "macro": collecte.trouver("macro") or calculs.contexte_macro(journal, ac),
        "mesures_base": collecte.trouver("mesures", 0) or calculs.analyse_portefeuille(journal, base, "portefeuille actuel", ac),
        "mesures": mesures,
        "vol": mesures,
        # Le point de bascule n'est pas un outil du modèle : l'orchestrateur le calcule toujours pour la Gouvernance.
        "bascule": calculs.point_de_bascule(journal, base, symbole, gabarit, univers, ac, persona),
        "base": collecte.trouver("rejeu", 0) or calculs.rejeu_2022(journal, base, persona["capital"], "portefeuille actuel", ac),
        "rejeu": collecte.trouver("rejeu", part) or calculs.rejeu_2022(journal, poids, persona["capital"], lib, ac),
    }
    utilises = {v["trace"] for v in d.values() if isinstance(v, dict) and "trace" in v}
    d["extras"] = _extras(collecte, utilises)
    d["raisonnement"] = _note_verifiee(journal, texte, agent, consigne)
    return d


def analyser_alternative(journal, persona: dict, symbole: str, part: float, tentative: int,
                         consigne: str | None = None, part_precedente: float | None = None) -> dict:
    """`part` = part de repli déterministe (gouvernance.prochaine_part). En mode Strands, le modèle propose
    sa propre part, qui doit être strictement inférieure à `part_precedente` ; sinon on garde `part`."""
    agent = f"Agent Analyste · tentative {tentative}"
    if not _mode_strands():
        return _plan_fixe_alternative(journal, persona, symbole, part, agent)

    plafond = part_precedente if part_precedente is not None else part

    def libelle_de(x):
        x = _cle(x)
        return "portefeuille actuel" if x == 0 else f"alternative {pct(x)} {symbole}"

    texte_consigne = (f"{_mandat_texte(persona)}\n"
                      f"CORRECTION demandée par l'Agent Gouvernance : {consigne or 'propose une part plus prudente.'}\n"
                      f"Part précédente de {symbole} : {pct(plafond)} (part_actif = {_cle(plafond)}). "
                      f"Ta nouvelle part doit être strictement inférieure. Repère calculé : {_cle(part)}.\n"
                      f"Calculs minimum pour la part choisie : rejeu_2022(part) et volatilite_portefeuille(part).\n"
                      f"Termine par la ligne PART=<nombre entre 0 et 1>.")
    try:
        collecte, texte = _lancer_agent(journal, persona, symbole, agent, libelle_de, texte_consigne)
    except Exception as e:
        _tracer_repli(journal, agent, e)
        a = _plan_fixe_alternative(journal, persona, symbole, part, agent)
        a["raisonnement"] = f"Repli sur le plan fixe ({type(e).__name__})."
        return a

    proposee = _lire_part(texte)
    choisie = part
    if proposee is not None and 0 < proposee < plafond - 1e-9 and proposee <= 1:
        choisie = _cle(proposee)
    else:
        journal.log(titre="Part proposée par le modèle écartée", agent=agent + COMPLETE, outil="lecture de PART=",
                    entrees=f"PART lu : {'illisible' if proposee is None else proposee} · part précédente {pct(plafond)}",
                    sortie=f"part de repli retenue : {pct(part)} (gouvernance.prochaine_part)",
                    source="orchestrateur", periode="—")

    poids = calculs.poids_avec_position(persona["portefeuille_suppose"], symbole, choisie)
    lib, ac = libelle_de(choisie), agent + COMPLETE
    mesures = collecte.trouver("mesures", choisie) or calculs.analyse_portefeuille(journal, poids, lib, ac)
    a = {
        "poids": poids, "part": choisie, "mesures": mesures, "vol": mesures,
        "rejeu": collecte.trouver("rejeu", choisie) or calculs.rejeu_2022(journal, poids, persona["capital"], lib, ac),
    }
    utilises = {a["mesures"]["trace"], a["rejeu"]["trace"]}
    a["extras"] = _extras(collecte, utilises)
    a["raisonnement"] = _note_verifiee(journal, texte, agent, texte_consigne)
    return a
