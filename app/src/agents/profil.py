"""Agent Profil : transforme la phrase libre en demande structurée {symbole, part}.

Il ne fixe AUCUN seuil (ils viennent de config/) et ne détermine pas le profil (c'est une entrée).
Règle « aucun chiffre ne vient du LLM » :
- le LLM (MODE=bedrock) choisit seulement l'actif et RECOPIE l'extrait du message qui donne la part
  (« 30 % », « 50 000 $ ») ;
- le code vérifie que l'extrait existe tel quel dans le message, puis le convertit en part
  (montant / capital pour un montant en dollars) ;
- chaque extraction laisse une trace dans le journal.
"""
import difflib
import json
import re
import unicodedata

import yaml

from src import bedrock_client
from src.config import APP, GABARITS, PERSONAS, PROFIL, prompt
from src.formatage import money, nombre, pct

# ORDRE RÉEL = l'utilisateur demande à l'assistant d'AGIR (pas une simulation « si j'achète… », « je pense mettre… »).
# Tolère les fautes courantes (« achte », « achete »). C'est le blocage d'entrée des ordres réels : Bedrock Guardrails
# ne fait que DÉTECTER ce sujet en entrée (il bloquait des simulations légitimes, voir docs/decisions.md).
_ACHAT_VENTE = (r"(?:ach[eèé]?t(?:e|es|ez|er)?|vend(?:s|ez|re)?|plac(?:e|es|ez|er)|investi(?:s|ssez|r)"
                r"|met[sz]?|mettez|prends|prenez)")                  # formes VERBALES seulement (pas « placement »)
MOTS_TRANSACTION = re.compile("|".join([
    r"\bach\w*",                                                                     # tout mot qui commence par « ach » (choix de l'équipe)
    rf"\b{_ACHAT_VENTE}[\s-]+(?:pour\s+)?moi\b",                                     # « achète-moi », « achte moi », « mets-moi »
    r"\bach[eèé]?te-(?:le|la|les)\b",                                                # « achète-le pour moi »
    r"(?:^|[.!?;:]\s*)(?:ach[eèé]?te[sz]?|vend[sz]?|vendez|ex[ée]cute[sz]?)\b",       # impératif en début de phrase
    rf"\b(?:(?:tu|vous)\s+(?:peux|pourrais|pouvez|pourriez)|(?:peux|pourrais|pouvez|pourriez)-(?:tu|vous))"
    rf"\s+(?:m'|me\s+)?(?:{_ACHAT_VENTE}|passer)",                                    # « tu peux m'acheter… »
    r"\bpass(?:e|er|ez)\s+(?:l'|un\s+|une\s+|des\s+|mon\s+|mes\s+)?ordres?\b",        # « passe l'ordre », « passer un ordre »
    r"\bex[ée]cut\w*\s+(?:la|l'|une|cette|mon|ma|mes)\s*(?:transaction|ordre|achat|vente)",
]), re.I)

_POURCENTAGE = re.compile(r"(\d{1,3}(?:[.,]\d+)?)\s*(?:%|pour\s?cent|pourcent)", re.I)
_MONTANT = re.compile(r"(\d{1,3}(?:[   ]\d{3})+|\d+)(?:[.,](\d+))?\s*(k)?\s*(?:\$|dollars?\b|CAD\b)", re.I)

with open(APP / "config" / "alias_actifs.yaml", encoding="utf-8") as _f:
    ALIAS: dict[str, list[str]] = yaml.safe_load(_f)


def demande_de_transaction(message: str) -> bool:
    """Garde-fou LOCAL (regex, rapide, sans AWS). Bedrock Guardrails est appelé ensuite par l'orchestrateur
    (src/verif/guardrails.py), en MODE=bedrock si un guardrail est configuré."""
    return bool(MOTS_TRANSACTION.search(message))


# ---------- Mandat : profil (entrée) + gabarit (config) ----------

def horizon_en_annees(horizon) -> tuple[float | None, float | None]:
    """« 3 à 5 ans » → (3, 5) · « 15 ans et plus » → (15, None) · 10 → (10, 10). Code pur."""
    if horizon is None or horizon == "":
        return None, None
    if isinstance(horizon, (int, float)):
        return float(horizon), float(horizon)
    nombres = [float(n.replace(",", ".")) for n in re.findall(r"\d+(?:[.,]\d+)?", str(horizon))]
    if not nombres:
        return None, None
    if re.search(r"plus|\+", str(horizon)):
        return nombres[0], None
    return nombres[0], nombres[-1]


def _profil_saisi(saisie: dict) -> tuple[dict, list[str], list[str]]:
    """Profil personnalisé (5 champs) → dict au format persona. Renvoie (profil, manquants, hypothèses)."""
    manquants, hypotheses = [], []
    tolerance = saisie.get("tolerance")
    if tolerance not in PROFIL["tolerances"]:
        tolerance = None
        manquants.append("tolérance au risque")
    horizon = saisie.get("horizon_ans")
    if horizon in (None, ""):
        manquants.append("horizon de placement")
    for champ, libelle in (("age", "âge"), ("objectif", "objectif")):
        if saisie.get(champ) in (None, ""):
            manquants.append(libelle)
    capital = saisie.get("capital")
    if not capital:
        capital = PROFIL["capital_par_defaut"]
        hypotheses.append(f"capital fictif de {money(capital)} (non saisi)")
    type_pf = PROFIL["portefeuilles_types"].get(tolerance) if tolerance else None
    if type_pf:
        hypotheses.append(f"portefeuille actuel supposé selon la tolérance : {type_pf['libelle']}")
    hypotheses.append(f"niveau d'explication « {PROFIL['experience_par_defaut']} » par défaut")
    profil = {
        "id": "personnalise", "nom": saisie.get("nom") or "Profil personnalisé", "age": saisie.get("age"),
        "metier": "—", "risque": tolerance, "horizon": f"{horizon} ans" if horizon not in (None, "") else "non précisé",
        "capital": capital, "niveau_experience": PROFIL["experience_par_defaut"],
        "objectif": saisie.get("objectif") or "non précisé",
        "preferences": ["Critères ESG importants"] if saisie.get("esg") else [],
        "exclusions_esg": bool(saisie.get("esg")),
        "portefeuille_suppose": dict(type_pf["poids"]) if type_pf else {},
        "portefeuille_suppose_libelle": type_pf["libelle"] if type_pf else "inconnu",
        "message_exemple": "Je pense mettre 10 % dans Tesla.",
    }
    return profil, manquants, hypotheses


def _tensions(profil: dict) -> list[str]:
    """Incohérences ENTRE les champs du profil : signalées, jamais corrigées à la place de l'utilisateur."""
    tensions = []
    h_min, _ = horizon_en_annees(profil.get("horizon"))
    seuil = PROFIL["horizon_min_coherent"].get(profil.get("risque"))
    if h_min is not None and seuil and h_min < seuil:
        label = GABARITS[profil["risque"]]["label"].lower()
        tensions.append(f"tolérance « {label} » avec un horizon de {nombre(h_min, 0)} ans "
                        f"(horizon jugé cohérent : {seuil} ans ou plus) : une forte baisse laisserait peu de temps pour récupérer")
    return tensions


def construire_mandat(persona_id: str | None = None, saisie: dict | None = None, journal=None) -> dict:
    """Mandat JSON = profil (persona choisi OU 5 champs saisis) + gabarit de config/ + contraintes.

    Le profil est une ENTRÉE : l'agent ne déduit jamais la tolérance au risque. Il signale les
    informations manquantes et les tensions entre champs au lieu de les inventer ou de les corriger.
    `bloquant` = True si la tolérance manque (aucun gabarit applicable) ; `question` dit quoi préciser.
    """
    if saisie is not None:
        profil, manquants, hypotheses = _profil_saisi(saisie)
        source = "profil saisi (5 champs)"
    else:
        profil = dict(PERSONAS[persona_id])
        profil.setdefault("exclusions_esg", False)
        manquants = []
        hypotheses = [f"portefeuille actuel supposé : {profil['portefeuille_suppose_libelle']}"]
        source = f"persona de référence « {profil['nom']} » (config/personas)"
    gabarit = {"id": profil["risque"], **GABARITS[profil["risque"]]} if profil["risque"] else None
    bloquant = gabarit is None
    mandat = {
        "source": source, "profil": profil, "gabarit": gabarit,
        "contraintes": None if bloquant else {
            "poids_max_par_titre": gabarit["poids_max_par_titre"],
            "part_risque_max_par_titre": gabarit["part_risque_max_par_titre"],
            "volatilite_max": gabarit["volatilite_max"], "pire_baisse_max": gabarit["pire_baisse_max"],
            "obligations_min": gabarit["obligations_min"], "crypto_max": gabarit["crypto_max"],
            "paris_effectifs_min": gabarit.get("paris_effectifs_min"),
            "exclusions_esg": profil["exclusions_esg"]},
        "horizon_ans": dict(zip(("min", "max"), horizon_en_annees(profil.get("horizon")))),
        "informations_manquantes": manquants, "tensions": [] if bloquant else _tensions(profil),
        "hypotheses": hypotheses, "bloquant": bloquant,
        "question": ("Quelle est ta tolérance au risque : faible à modérée, modérée ou élevée ? "
                     "Je ne la déduis pas à ta place.") if bloquant else None,
        "demande": None, "trace": None,
    }
    if journal is not None:
        mandat["trace"] = _tracer_mandat(journal, mandat)
    return mandat


def _tracer_mandat(journal, m: dict) -> str:
    p, g = m["profil"], m["gabarit"]
    morceaux = [f"tolérance : {g['label'] if g else 'MANQUANTE'}", f"horizon : {p['horizon']}",
                f"ESG : {'exclusions demandées' if p['exclusions_esg'] else 'non demandé'}"]
    if g:
        morceaux.append(f"gabarit « {g['label']} » : poids max/titre {pct(g['poids_max_par_titre'])}, "
                        f"part du risque max/titre {pct(g['part_risque_max_par_titre'])}, vol. max {pct(g['volatilite_max'])}, "
                        f"pire baisse max {pct(g['pire_baisse_max'])}, obligations min {pct(g['obligations_min'])}, "
                        f"crypto max {pct(g['crypto_max'])}")
    if p.get("portefeuille_suppose"):
        morceaux.append(f"positions (donnée du compte, fictif) : {p['portefeuille_suppose_libelle']}")
    if m["informations_manquantes"]:
        morceaux.append("manquant : " + ", ".join(m["informations_manquantes"]))
    if m["tensions"]:
        morceaux.append("tension : " + " ; ".join(m["tensions"]))
    return journal.log(titre="Construction du mandat", agent="Agent Profil", outil="construire_mandat(profil)",
                       entrees=f"{m['source']} · capital {money(p['capital'])}",
                       sortie=" · ".join(morceaux), source="config/gabarits_risque.yaml · config/profil.yaml",
                       periode="exécution courante")


# ---------- Reconnaissance des actifs ----------

def _normaliser(texte: str) -> str:
    sans_accents = unicodedata.normalize("NFKD", texte).encode("ascii", "ignore").decode()
    return sans_accents.replace("’", "'").lower()


def _chercher(motif: str, texte: str, flags=0) -> int | None:
    m = re.search(rf"(?<![\w&]){re.escape(motif)}(?![\w&])", texte, flags)
    return m.start() if m else None


def actifs_mentionnes(message: str, univers, approximations: list | None = None) -> list[str]:
    """Symboles de l'univers cités dans le message, dans leur ordre d'apparition (sans doublon).

    - tickers de 3 lettres ou plus : majuscules ou minuscules (« NVDA », « nvda ») ; tickers de 2 lettres (TD, PG, RY) :
      majuscules seulement, pour ne pas confondre avec des mots ordinaires ;
    - noms et alias (config/alias_actifs.yaml), sans accents ni majuscules ;
    - fautes de frappe (« nvdia ») : approximation stricte (seuil dans config/profil.yaml), notée dans `approximations`
      pour être affichée et tracée — jamais silencieuse.
    """
    norm = _normaliser(message)
    positions: dict[str, int] = {}
    cibles: dict[str, str] = {}                       # mot de référence (ticker ou alias en un mot) → symbole
    for symbole in univers["symbole"].astype(str):
        court = re.sub(r"(\.TO|-USD)$", "", symbole)
        trouves = [_chercher(t, message) for t in {symbole, court}]               # majuscules
        if len(court) >= 3:
            trouves.append(_chercher(court.lower(), norm))                         # minuscules (« nvda »)
            cibles[court.lower()] = symbole
        for a in ALIAS.get(symbole, []):
            trouves.append(_chercher(_normaliser(a), norm))
            if " " not in a and len(a) >= 4:
                cibles[_normaliser(a)] = symbole
        trouves = [p for p in trouves if p is not None]
        if trouves:
            positions[symbole] = min(trouves)
    if not positions:                                 # rien d'exact : on tente les fautes de frappe, mot par mot
        for m in re.finditer(r"[a-z]{4,}", norm):
            mot = m.group(0)
            if mot in set(PROFIL["mots_de_relance_exclus_approx"]):
                continue
            proche = difflib.get_close_matches(mot, list(cibles), n=1, cutoff=PROFIL["seuil_approximation_actif"])
            if proche and cibles[proche[0]] not in positions:
                positions[cibles[proche[0]]] = m.start()
                if approximations is not None:
                    approximations.append(f"{mot} → {cibles[proche[0]]}")
    return sorted(positions, key=positions.get)


# ---------- Lecture de la part (code pur) ----------

def _nombre(entier: str, decimales: str | None) -> float:
    valeur = float(re.sub(r"[   ]", "", entier))
    return valeur + (float(f"0.{decimales}") if decimales else 0.0)


def lire_part(texte: str, capital: float) -> dict | None:
    """Lit la part demandée dans un texte. Pourcentage prioritaire ; sinon montant ÷ capital.

    Un montant supérieur ou égal au capital décrit en général le capital lui-même
    (« j'ai 200 000 $ de côté ») : il n'est pas interprété comme une part.
    """
    m = _POURCENTAGE.search(texte)
    if m:
        return {"part": float(m.group(1).replace(",", ".")) / 100, "extrait": m.group(0).strip(), "type": "pourcentage"}
    for m in _MONTANT.finditer(texte):
        montant = _nombre(m.group(1), m.group(2)) * (1000 if m.group(3) else 1)
        if 0 < montant < capital:
            return {"part": montant / capital, "extrait": m.group(0).strip(), "type": "montant", "montant": montant}
    return None


# ---------- Mémoire de conversation (code pur) ----------

_GROUPES = [("actions canadiennes", lambda c, d: c == "equity" and d == "CAD"),
            ("actions américaines", lambda c, d: c == "equity" and d != "CAD"),
            ("FNB d'actions", lambda c, d: c == "etf_equity"), ("FNB obligataires", lambda c, d: c == "etf_bond"),
            ("or", lambda c, d: c == "etf_commodity"), ("cryptoactifs", lambda c, d: c == "crypto")]


def univers_lisible(univers) -> str:
    """« actions canadiennes (RY, TD, …) · actions américaines (AAPL, …) · … » pour les messages à l'utilisateur."""
    morceaux = []
    for nom, test in _GROUPES:
        sel = univers[[test(str(c), str(d)) for c, d in zip(univers["classe"], univers["devise"])]]
        if len(sel):
            courts = [re.sub(r"(\.TO|-USD)$", "", str(s)) for s in sel["symbole"]]
            morceaux.append(f"{nom} ({', '.join(courts)})")
    return " · ".join(morceaux)


_NOMBRE_NU = re.compile(r"(?<![\w.,])\d+(?:[.,]\d+)?(?![\w.,%$])")
_CIBLE = re.compile(r"\b(dans|sur|chez|pour)\s+[a-z]", re.I)


def _sans_ponctuation(texte: str) -> str:
    """Minuscules, sans accents, tirets ni apostrophes : « qu'en est-il », « qu en est til » → comparables."""
    return " " + re.sub(r"\s+", " ", re.sub(r"[^a-z0-9]+", " ", _normaliser(texte))).strip() + " "


def _contient(message: str, marqueurs: list[str]) -> bool:
    norm = _sans_ponctuation(message)
    return any(_sans_ponctuation(m) in norm for m in marqueurs)


def est_comparaison(message: str) -> bool:
    """« et NVIDIA ? », « qu'en est-il pour NVIDIA ? » (tolère « qu'en est til ») : comparaison avec la demande précédente."""
    return _sans_ponctuation(message).startswith(" et ") or _contient(message, PROFIL["marqueurs_de_comparaison"])


def renvoie_a_une_part_donnee(message: str) -> bool:
    """« ce que je t'ai demandé au début », « comme avant » : l'utilisateur renvoie à une part déjà indiquée."""
    return _contient(message, PROFIL["marqueurs_de_reprise_part"])


def nouvelle_cible(message: str) -> bool:
    """« … dans Bombardier » : le message vise un AUTRE actif (même inconnu) → ne jamais reprendre l'actif précédent."""
    return bool(_CIBLE.search(_normaliser(message)))


# ---------- Extraction ----------

def _extraction_locale(message: str, univers, persona: dict) -> dict:
    approximations: list[str] = []
    mentionnes = actifs_mentionnes(message, univers, approximations)
    methode = "règles locales (alias + expressions régulières)"
    if approximations:
        methode += " · reconnu par approximation : " + ", ".join(approximations)
    return {"symboles_mentionnes": mentionnes,
            "symbole": mentionnes[0] if len(mentionnes) == 1 else None,
            "lecture": lire_part(message, persona["capital"]),
            "methode": methode}


def _extraction_llm(message: str, univers, persona: dict) -> dict | None:
    """Le LLM choisit l'actif et recopie l'extrait ; le code contrôle et convertit. None si inutilisable."""
    texte = (prompt("profil") + "\n\nMessage : " + message
             + "\nSymboles de l'univers : " + ", ".join(univers["symbole"].astype(str)))
    try:
        rep = bedrock_client.appeler_json(texte, modele="rapide")
    except Exception as e:                    # accès refusé, modèle non activé, réseau… : repli sur les règles locales
        return {"erreur": f"{type(e).__name__} : {str(e)[:300]}"}
    if not isinstance(rep, dict):
        return {"erreur": "réponse JSON illisible"}
    symboles = set(univers["symbole"].astype(str))
    mentionnes = [s for s in rep.get("symboles_mentionnes") or [] if s in symboles]
    symbole = rep.get("symbole") if rep.get("symbole") in symboles else None
    if symbole and symbole not in mentionnes:
        mentionnes.insert(0, symbole)
    extrait = rep.get("extrait_part")
    lecture = None
    controle = "aucun extrait de part fourni"
    if extrait:
        if extrait in message:                                    # contrôle d'ancrage : recopié, pas inventé
            lecture = lire_part(extrait, persona["capital"])
            controle = "extrait retrouvé dans le message" if lecture else "extrait illisible"
        else:
            controle = f"extrait « {extrait} » ABSENT du message → rejeté"
    return {"symboles_mentionnes": mentionnes, "symbole": symbole if len(mentionnes) <= 1 else None,
            "lecture": lecture, "methode": f"LLM Bedrock (actif) + contrôle par le code ({controle})"}


RELANCE_ACTIF = "Quel actif ? Par exemple Tesla, Nvidia ou un FNB comme XIU."


def _ancree(lecture: dict | None, message_origine: str | None) -> bool:
    """Contrôle d'ancrage d'une part REPRISE : son extrait doit figurer dans le message où elle a été trouvée."""
    return bool(lecture and message_origine and lecture["extrait"] in message_origine)


def maj_demande_en_attente(en_attente: dict | None, res: dict, message: str) -> dict | None:
    """Demande en attente après un tour de conversation (code pur, partagé par l'interface et les tests).

    - analyse lancée (demande complète) → None (vidée) ;
    - arrêt AVANT la lecture de la demande (garde-fou, tolérance manquante) → inchangée ;
    - demande incomplète → on garde les champs trouvés ; un champ présent dans ce message remplace l'ancien.
      Chaque champ garde le message où il a été trouvé (contrôle d'ancrage au moment de la reprise).
    """
    if not res.get("arret"):
        return None
    dem = res.get("demande_extraite")
    if dem is None:
        return en_attente
    p = dict(en_attente or {})
    origines = dem.get("origines") or {}
    if origines.get("symbole") == message and dem["symbole"] and len(dem["symboles_mentionnes"]) == 1:
        p.update(symbole=dem["symbole"], message_symbole=message)
    if origines.get("part") == message:                  # ce message donnait une part : elle remplace l'ancienne
        valide = dem["part"] is not None                 # (une part invalide, ex. 150 %, efface l'ancienne)
        p.update(lecture=dem["lecture"] if valide else None, message_part=message if valide else None)
    return p if (p.get("symbole") or p.get("lecture")) else None


def extraire(message: str, persona: dict, univers, journal=None, memoire: dict | None = None,
             en_attente: dict | None = None) -> dict:
    """Retourne {symbole, part, symboles_mentionnes, informations_manquantes, question, methode, trace, …}.

    `question` est le message à poser à l'utilisateur quand la demande est incomplète ou ambiguë :
    l'agent ne devine jamais à sa place.
    """
    locale = _extraction_locale(message, univers, persona)
    res = locale
    if bedrock_client.actif():
        llm = _extraction_llm(message, univers, persona)
        if "erreur" in llm:
            res = {**locale, "methode": f"repli sur les règles locales (LLM Bedrock indisponible : {llm['erreur']})"}
        else:
            # L'actif peut venir du LLM (périphrases) ; la part vient toujours du code.
            res = {**llm, "lecture": llm["lecture"] or locale["lecture"]}
            if not res["symboles_mentionnes"]:
                res.update(symboles_mentionnes=locale["symboles_mentionnes"], symbole=locale["symbole"])

    lecture = res["lecture"]
    part = lecture["part"] if lecture else None
    mentionnes = res["symboles_mentionnes"]
    symbole = res["symbole"]

    # Mémoire minimale : elle COMPLÈTE une demande à moitié donnée, rien de plus. On raisonne sur le CONTENU
    # du message (actif ? part ?), jamais sur sa longueur. Toute reprise est affichée et tracée.
    #  1. actif + part      → nouvelle demande, mémoire ignorée ;
    #  2. part seule        → actif de l'échange précédent (sauf si le message vise un autre actif : « … dans X ») ;
    #  3. actif seul        → part précédente SEULEMENT si comparaison explicite (« et pour… », « qu'en est-il… »)
    #                         ou renvoi à une part déjà donnée (« comme avant ») ;
    #  4. ni actif ni part  → jamais d'analyse : actif inconnu (« … dans Bombardier »), demande en attente
    #                         (reprise si « comme avant », sinon on redemande la part), ou message d'aide.
    # DEMANDE EN ATTENTE (multi-tours) : un message incomplet garde ses champs (actif OU part) ; le message suivant
    # les complète. Un message complet (actif + part) remplace la demande en attente. Prioritaire sur la mémoire.
    origines = {"symbole": message if mentionnes else None, "part": message if lecture is not None else None}
    completes, actif_tente = [], False
    att = en_attente or {}
    if att and not (mentionnes and lecture is not None):
        if mentionnes and lecture is None and _ancree(att.get("lecture"), att.get("message_part")):
            lecture = att["lecture"]                                                   # « 10 % » puis « tesla »
            origines["part"] = att["message_part"]
            completes.append(f"part = {pct(lecture['part'])}")
        elif not mentionnes and att.get("symbole") and not nouvelle_cible(message):
            symbole, mentionnes = att["symbole"], [att["symbole"]]                     # « tesla » puis « 10 % »
            origines["symbole"] = att.get("message_symbole")
            completes.append(f"actif = {symbole}")
        elif not mentionnes and lecture is None and att.get("lecture"):
            actif_tente = True                       # la part attend un actif : ce message en nomme un hors univers

    reprises, aide = [], None
    memoire = memoire or {}
    en_attente = bool(memoire.get("symbole")) and memoire.get("lecture") is None
    precedente = memoire.get("lecture") or memoire.get("derniere_lecture")
    if completes or actif_tente:
        pass                                                                          # demande en attente appliquée
    elif not mentionnes and lecture is not None:                                      # règle 2
        if memoire.get("symbole") and not nouvelle_cible(message):                    # « 10 % dans Bombardier » : non
            symbole, mentionnes = memoire["symbole"], [memoire["symbole"]]
            reprises.append(f"actif {symbole}")
    elif mentionnes and lecture is None:                                              # règle 3
        if precedente and len(mentionnes) == 1 and (est_comparaison(message) or renvoie_a_une_part_donnee(message)):
            lecture = precedente
            reprises.append(f"part {pct(lecture['part'])} (dernière part indiquée : « {lecture['extrait']} »)")
    elif not mentionnes and lecture is None and not nouvelle_cible(message):          # règle 4
        if en_attente:
            symbole, mentionnes = memoire["symbole"], [memoire["symbole"]]
            reprises.append(f"actif {symbole} (demande en attente)")
            if precedente and renvoie_a_une_part_donnee(message):
                lecture = precedente
                reprises.append(f"part {pct(lecture['part'])} (dernière part indiquée : « {lecture['extrait']} »)")
        elif not _NOMBRE_NU.search(message):
            aide = ("Je suis un outil de simulation : j'analyse une part d'un actif dans ton portefeuille, selon ton profil. "
                    "Par exemple : « Je pense mettre 10 % dans Tesla » ou « Et 5 000 $ en NVIDIA ? ».")
    part = lecture["part"] if lecture else None

    manquants, question = [], None
    if aide:
        manquants.append("demande")
        question = aide
    elif len(mentionnes) > 1:
        manquants.append("actif à analyser")
        question = (f"Ton message cite plusieurs actifs ({', '.join(mentionnes)}). J'analyse une demande à la fois : "
                    "lequel veux-tu ajouter à ton portefeuille, et pour quelle part ?")
    elif symbole is None:
        manquants.append("actif")
        # La liste complète seulement si un actif a VRAIMENT été nommé hors de l'univers (« … dans Ford », « Ford »).
        question = (f"Je ne reconnais pas d'actif de l'univers étudié dans ta demande. Il couvre {len(univers)} actifs : "
                    + univers_lisible(univers) + "." if actif_tente or nouvelle_cible(message) else RELANCE_ACTIF)
    if aide:
        pass
    elif part is None:
        manquants.append("part du portefeuille")
        cible = f"mettre en {symbole}" if symbole else "y mettre"
        nombre_nu = _NOMBRE_NU.search(_MONTANT.sub(" ", _POURCENTAGE.sub(" ", message)))
        precision = (f" Tu as écrit « {nombre_nu.group(0)} » : est-ce {nombre_nu.group(0)} % ou {nombre_nu.group(0)} $ ?"
                     if nombre_nu else "")
        question = question or (f"Quelle part de ton portefeuille veux-tu {cible} (en % ou en $) ?{precision} "
                                "Je ne la devine pas à ta place.")
    elif not 0 < part <= 1:
        manquants.append("part valide")
        question = question or f"La part demandée ({lecture['extrait']}) doit être comprise entre 0 et 100 % du portefeuille."
        part = None

    res_final = {"symbole": symbole,
                 "part": part, "lecture": lecture, "symboles_mentionnes": mentionnes,
                 "informations_manquantes": manquants, "question": question, "methode": res["methode"],
                 "reprises": reprises, "completes": completes, "origines": origines, "trace": None}
    if journal is not None:
        res_final["trace"] = _tracer(journal, message, persona, res_final)
    return res_final


def _tracer(journal, message: str, persona: dict, r: dict) -> str:
    morceaux = [f"actifs cités : {', '.join(r['symboles_mentionnes']) or 'aucun'}",
                f"actif retenu : {r['symbole'] or 'aucun'}"]
    lec = r["lecture"]
    if r["part"] is not None and lec["type"] == "montant":
        morceaux.append(f"part : {pct(r['part'])} = {money(lec['montant'])} / capital {money(persona['capital'])} (extrait « {lec['extrait']} »)")
    elif r["part"] is not None:
        morceaux.append(f"part : {pct(r['part'])} (extrait « {lec['extrait']} »)")
    if r.get("completes"):
        morceaux.append("complété à partir du message précédent : " + ", ".join(r["completes"]))
    if r.get("reprises"):
        morceaux.append("repris de l'échange précédent : " + ", ".join(r["reprises"]))
    if r["informations_manquantes"]:
        morceaux.append("manquant : " + ", ".join(r["informations_manquantes"]))
    extrait_msg = message if len(message) <= 240 else message[:237] + "…"
    return journal.log(titre="Extraction de la demande", agent="Agent Profil", outil="extraire_demande(message)",
                       entrees=f"message : « {extrait_msg} » · profil : {persona['nom']} (entrée, non déduit)",
                       sortie=" · ".join(morceaux), source=f"message de l'utilisateur · {r['methode']}",
                       periode="exécution courante")
