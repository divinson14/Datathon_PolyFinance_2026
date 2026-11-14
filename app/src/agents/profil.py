"""Agent Profil : transforme la phrase libre en demande structurée {symbole, part}.

Il ne fixe AUCUN seuil (ils viennent de config/) et ne détermine pas le profil (c'est une entrée).
Règle « aucun chiffre ne vient du LLM » :
- le LLM (MODE=bedrock) choisit seulement l'actif et RECOPIE l'extrait du message qui donne la part
  (« 30 % », « 50 000 $ ») ;
- le code vérifie que l'extrait existe tel quel dans le message, puis le convertit en part
  (montant / capital pour un montant en dollars) ;
- chaque extraction laisse une trace dans le journal.
"""
import json
import re
import unicodedata

import yaml

from src import bedrock_client
from src.config import APP, GABARITS, PERSONAS, PROFIL, prompt
from src.formatage import money, nombre, pct

MOTS_TRANSACTION = re.compile(r"\b(ach[eè]te[- ]?(le|la|les)?|passe (l'|un )?ordre|ex[ée]cute|vends)\b", re.I)

_POURCENTAGE = re.compile(r"(\d{1,3}(?:[.,]\d+)?)\s*(?:%|pour\s?cent|pourcent)", re.I)
_MONTANT = re.compile(r"(\d{1,3}(?:[   ]\d{3})+|\d+)(?:[.,](\d+))?\s*(k)?\s*(?:\$|dollars?\b|CAD\b)", re.I)

with open(APP / "config" / "alias_actifs.yaml", encoding="utf-8") as _f:
    ALIAS: dict[str, list[str]] = yaml.safe_load(_f)


def demande_de_transaction(message: str) -> bool:
    """Garde-fou local, doublé par Bedrock Guardrails en mode bedrock."""
    if MOTS_TRANSACTION.search(message):
        return True
    return bedrock_client.actif() and bedrock_client.guardrail_bloque(message)


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


def actifs_mentionnes(message: str, univers) -> list[str]:
    """Symboles de l'univers cités dans le message, dans leur ordre d'apparition (sans doublon)."""
    norm = _normaliser(message)
    positions: dict[str, int] = {}
    for symbole in univers["symbole"].astype(str):
        courts = {symbole, re.sub(r"(\.TO|-USD)$", "", symbole)}
        trouves = [_chercher(t, message) for t in courts]                         # tickers : majuscules seulement
        trouves += [_chercher(_normaliser(a), norm) for a in ALIAS.get(symbole, [])]
        trouves = [p for p in trouves if p is not None]
        if trouves:
            positions[symbole] = min(trouves)
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


# ---------- Extraction ----------

def _extraction_locale(message: str, univers, persona: dict) -> dict:
    mentionnes = actifs_mentionnes(message, univers)
    return {"symboles_mentionnes": mentionnes,
            "symbole": mentionnes[0] if len(mentionnes) == 1 else None,
            "lecture": lire_part(message, persona["capital"]),
            "methode": "règles locales (alias + expressions régulières)"}


def _extraction_llm(message: str, univers, persona: dict) -> dict | None:
    """Le LLM choisit l'actif et recopie l'extrait ; le code contrôle et convertit. None si inutilisable."""
    texte = (prompt("profil") + "\n\nMessage : " + message
             + "\nSymboles de l'univers : " + ", ".join(univers["symbole"].astype(str)))
    try:
        rep = bedrock_client.appeler_json(texte, modele="rapide")
    except Exception as e:                    # accès refusé, modèle non activé, réseau… : repli sur les règles locales
        return {"erreur": f"{type(e).__name__} : {str(e)[:300]}"}
    if not rep:
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


def extraire(message: str, persona: dict, univers, journal=None) -> dict:
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
    manquants, question = [], None
    if len(mentionnes) > 1:
        manquants.append("actif à analyser")
        question = (f"Ton message cite plusieurs actifs ({', '.join(mentionnes)}). J'analyse une demande à la fois : "
                    "lequel veux-tu ajouter à ton portefeuille, et pour quelle part ?")
    elif symbole is None:
        manquants.append("actif")
        question = ("Je ne reconnais pas l'actif visé dans l'univers étudié. Actifs couverts : "
                    + ", ".join(univers["symbole"].astype(str)) + ".")
    if part is None:
        manquants.append("part du portefeuille")
        question = question or ("Quelle part de ton portefeuille veux-tu y mettre (en % ou en $) ? "
                                "Je ne la devine pas à ta place.")
    elif not 0 < part <= 1:
        manquants.append("part valide")
        question = question or f"La part demandée ({lecture['extrait']}) doit être comprise entre 0 et 100 % du portefeuille."
        part = None

    res_final = {"symbole": symbole,
                 "part": part, "lecture": lecture, "symboles_mentionnes": mentionnes,
                 "informations_manquantes": manquants, "question": question, "methode": res["methode"], "trace": None}
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
    if r["informations_manquantes"]:
        morceaux.append("manquant : " + ", ".join(r["informations_manquantes"]))
    extrait_msg = message if len(message) <= 240 else message[:237] + "…"
    return journal.log(titre="Extraction de la demande", agent="Agent Profil", outil="extraire_demande(message)",
                       entrees=f"message : « {extrait_msg} » · profil : {persona['nom']} (entrée, non déduit)",
                       sortie=" · ".join(morceaux), source=f"message de l'utilisateur · {r['methode']}",
                       periode="exécution courante")
