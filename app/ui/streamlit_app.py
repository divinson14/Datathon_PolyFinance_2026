"""Interface AlphaForge : 1) choix du profil, 2) « Mon compte » (KPI, positions, historique),
3) analyse (chat + coulisses en ligne de temps). Présentation seulement : la logique est dans src/.
Lancer depuis app/ :  streamlit run ui/streamlit_app.py"""
import os
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))   # rend « src » et « ui » importables

import altair as alt
import pandas as pd
import plotly.graph_objects as go
import streamlit as st

from src import bedrock_client, config
from src.agents import explicabilite, gouvernance, profil
from src.donnees.chargeur import LIBELLE_DEMO, charger, donnees_fictives
from src.formatage import money, pct
from src.orchestrateur import executer, reformuler
from src.outils import calculs
from src.regles.moteur import evaluer_regles
from ui.composants import badge_etiquette, badge_trace, carte_kpi, carte_verdict, etape_timeline
from ui.style import COULEURS, injecter_style

st.set_page_config(page_title="AlphaForge", layout="wide")
injecter_style()

ORDRE_PERSONAS = ["robert", "amira", "mateo"]
PALETTE_ANNEAU = ["#1F6FEB", "#5B8DEF", "#93B4F5", "#C9D7F5", "#12805C", "#7FB8A3",
                  "#B7791F", "#D9B98A", "#6B7280", "#A1A6AE", "#D1D5DB", "#E7E7E3"]   # sobre : bleus, verts, ocres, gris


def mise_en_page(fig, hauteur: int):
    """Mise en page plotly commune : nombres à la française (« 50 000 $ », « 16,2 % »), fond transparent."""
    fig.update_layout(height=hauteur, separators=", ", margin=dict(t=10, b=10, l=10, r=10),
                      paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)",
                      font=dict(family="Inter, sans-serif", color=COULEURS["gris"]))
    return fig


etat = st.session_state
etat.setdefault("persona", None)
etat.setdefault("profil_saisi", None)
etat.setdefault("messages", [])
etat.setdefault("etapes", [])
etat.setdefault("memoire", None)          # dernier actif / dernière part, pour les relances courtes
etat.setdefault("demande_en_attente", None)   # demande incomplète (actif OU part) complétée au message suivant
etat.setdefault("question_en_cours", None)    # question en cours d'analyse : reprise si un clic interrompt l'exécution
etat.setdefault("voir_coulisses", True)       # état de l'interrupteur « Voir comment j'ai décidé »
etat.setdefault("_voir_affiche", True)        # valeur utilisée par le dernier affichage complet

def entete():
    """Marque + indicateur discret du mode (Bedrock ou démonstration hors ligne)."""
    g, d = st.columns([3, 2])
    g.markdown("<div class='af-marque'>Alpha<span>Forge</span></div>", unsafe_allow_html=True)
    if bedrock_client.actif():
        point, texte = COULEURS["vert"], f"Bedrock · {os.getenv('AWS_REGION', 'us-east-1')}"
    else:
        point, texte = COULEURS["gris"], "Mode démonstration hors ligne"
    d.markdown(f"<div style='text-align:right'><span class='af-pastille'><span class='af-point' "
               f"style='background:{point}'></span>{texte}</span></div>", unsafe_allow_html=True)


entete()
if donnees_fictives():          # repli silencieux du chargeur : on le rend impossible à manquer
    st.error(f"**{LIBELLE_DEMO}.** Les chiffres affichés sont simulés et ne reflètent pas les marchés réels. "
             "Pour les vraies données : `python data/scripts/01_nettoyer_prix.py` puis redémarrer.", icon="🚨")


# ---------- Écran 1 : choix du profil ----------
def ecran_profil():
    st.title("Choisis ton profil d'investisseur", anchor=False)
    st.markdown("<div class='af-sous-titre'>Simulation éducative · personas fictifs · aucun conseil personnalisé</div>",
                unsafe_allow_html=True)
    cols = st.columns(len(config.PERSONAS), gap="large")
    ordre = sorted(config.PERSONAS.items(),
                   key=lambda kv: ORDRE_PERSONAS.index(kv[0]) if kv[0] in ORDRE_PERSONAS else len(ORDRE_PERSONAS))
    for col, (pid, p) in zip(cols, ordre):
        with col.container(border=True):
            st.markdown(f"<div class='af-avatar'>{p['nom'][:1].upper()}</div>"
                        f"<div class='af-persona-nom'>{p['nom']}</div>"
                        f"<div class='af-persona-meta'>{p['age']} ans · risque {config.GABARITS[p['risque']]['label'].lower()}"
                        f" · horizon {p['horizon']}</div>"
                        f"<div class='af-persona-phrase'>{p['metier']}. {p['objectif']}.</div>", unsafe_allow_html=True)
            a_faire = p.get("a_faire")
            if st.button(f"Choisir {p['nom']}", key=pid, width="stretch", type="primary", disabled=bool(a_faire)):
                etat.persona, etat.messages, etat.etapes, etat.memoire, etat.demande_en_attente = pid, [], [], None, None
                st.rerun()
            if a_faire:
                st.caption("Bientôt : " + a_faire)
    with st.expander("…ou décris ton propre profil (5 champs, fictif)"):
        with st.form("formulaire_profil"):
            c1, c2 = st.columns(2)
            age = c1.number_input("Âge", min_value=18, max_value=100, value=None, placeholder="non précisé")
            horizon = c2.number_input("Horizon de placement (années)", min_value=1, max_value=50, value=None, placeholder="non précisé")
            libelles = {t: config.GABARITS[t]["label"] for t in config.PROFIL["tolerances"]}
            tolerance = c1.selectbox("Tolérance au risque", list(libelles), format_func=libelles.get, index=None,
                                     placeholder="à choisir (jamais déduite)")
            capital = c2.number_input("Capital fictif ($)", min_value=1000, step=1000, value=None,
                                      placeholder=f"{config.PROFIL['capital_par_defaut']:,} par défaut".replace(",", " "))
            objectif = st.text_input("Objectif", placeholder="ex. faire croître mon capital à long terme")
            esg = st.checkbox("J'exclus les entreprises liées à des controverses ESG importantes")
            if st.form_submit_button("Continuer avec ce profil", type="primary"):
                etat.persona = "personnalise"
                etat.profil_saisi = {"age": age, "tolerance": tolerance, "horizon_ans": horizon, "objectif": objectif,
                                     "esg": esg, "capital": capital}
                etat.messages, etat.etapes, etat.memoire, etat.demande_en_attente = [], [], None, None
                st.rerun()


# ---------- Courbe de bascule : la thèse en une image ----------
def courbe_bascule(res):
    """Part du risque portée par l'actif demandé, selon son poids. Tous les points viennent de l'outil
    point_de_bascule (trace citée) : l'image montre la LIMITE du profil, elle ne recommande rien."""
    d, g, s = res["demande"], res["gabarit"], res["symbole"]
    b = d["bascule"]
    df = pd.DataFrame(b["courbe"])
    part_max = b["part_max"]
    xmax = min(1.0, max(0.2, d["part"] * 1.4, (part_max or 0) * 3))
    df = df[df["part"] <= xmax + 1e-9]
    limite = g["part_risque_max_par_titre"]
    seuil = b["premiere_violation"].get(b["limitantes"][0]) if b["limitantes"] else None

    # Encre lisible sur fond clair ET sombre (st.context.theme peut être inconnu au 1er chargement → gris moyen).
    try:
        sombre = st.context.theme.type == "dark"
        encre, fond = ("#E6E6E6", "#0E1117") if sombre else ("#31333F", "#FFFFFF")
    except Exception:                                       # noqa: BLE001
        encre, fond = "#8A8F98", "#FFFFFF"
    df = df.assign(respecte=df["conforme"].map({True: "oui", False: "non"}), part_txt=df["part"].map(pct),
                   risque_txt=df["part_risque"].map(pct), vol_txt=df["vol"].map(pct))

    axe_x = alt.X("part:Q", title=f"Part de {s} dans le portefeuille",
                  axis=alt.Axis(labelExpr=POURCENT_FR, tickCount=6, gridOpacity=0.35), scale=alt.Scale(domain=[0, xmax], nice=False))
    axe_y = alt.Y("part_risque:Q", title=f"Part du risque portée par {s}",
                  axis=alt.Axis(labelExpr=POURCENT_FR, tickCount=5, gridOpacity=0.35), scale=alt.Scale(domain=[0, 1]))
    couches = []
    if seuil is not None:                                   # zone hors profil, discrète
        couches.append(alt.Chart(pd.DataFrame({"x": [seuil], "x2": [xmax]})).mark_rect(opacity=0.07, color=encre)
                       .encode(x="x:Q", x2="x2:Q"))
    couches.append(alt.Chart(df).mark_line(strokeWidth=2).encode(
        x=axe_x, y=axe_y,
        tooltip=[alt.Tooltip("part_txt:N", title=f"Part de {s}"),
                 alt.Tooltip("risque_txt:N", title="Part du risque"),
                 alt.Tooltip("vol_txt:N", title="Volatilité du portefeuille"),
                 alt.Tooltip("respecte:N", title="Respecte le profil")]))
    regle = pd.DataFrame({"y": [limite], "x": [xmax], "texte": [f"limite par titre : {pct(limite)}"]})
    couches.append(alt.Chart(regle).mark_rule(strokeDash=[4, 4], color=encre, opacity=0.6).encode(y="y:Q"))
    couches.append(alt.Chart(regle).mark_text(align="right", dy=-8, color=encre, opacity=0.8).encode(x="x:Q", y="y:Q", text="texte:N"))

    # Repères : étiquette de la demande au-dessus à gauche, du point de bascule en dessous à droite
    # (la courbe monte : ces deux zones sont vides, aucune étiquette ne la traverse).
    reperes = [{"x": d["part"], "y": d["mesures"]["parts_risque"].get(s, 0.0), "texte": f"demande : {pct(d['part'])}",
                "align": "right" if d["part"] > 0.25 * xmax else "left", "dx": -10 if d["part"] > 0.25 * xmax else 10, "dy": -14}]
    if part_max is not None and abs(part_max - d["part"]) > 1e-9:
        y_b = next((p["part_risque"] for p in b["courbe"] if abs(p["part"] - part_max) < 1e-9), 0.0)
        reperes.append({"x": part_max, "y": y_b, "texte": f"point de bascule : {pct(part_max)}",
                        "align": "left", "dx": 10, "dy": 16})
    for r in reperes:
        point = pd.DataFrame([r])
        couches.append(alt.Chart(point).mark_point(size=110, filled=True, color=encre, stroke=fond, strokeWidth=2)
                       .encode(x="x:Q", y="y:Q"))
        couches.append(alt.Chart(point).mark_text(align=r["align"], dx=r["dx"], dy=r["dy"], color=encre, fontWeight="bold")
                       .encode(x="x:Q", y="y:Q", text="texte:N"))
    st.markdown("**Courbe de bascule**")
    st.altair_chart(alt.layer(*couches).properties(height=280),
                    alt=f"Part du risque portée par {s} selon son poids ; limite du profil atteinte à {pct(part_max or 0)}")
    regle_txt = (f"Première règle franchie à {pct(seuil)} : {', '.join(b['limitantes']).lower()}." if seuil is not None
                 else "Aucune règle franchie sur toute la plage.")
    st.caption(f"{regle_txt} Zone grisée : hors des limites du profil. Calcul : trace {b['trace']}.")


# ---------- Réponse dans le chat ----------
GARDE_FOUS = ("Bedrock Guardrails", "Garde-fou local")
POURCENT_FR = "replace(replace(format(datum.value, '.0%'), '%', ' %'), '.', ',')"   # axes Altair : « 20 % »


def _verdict(res) -> tuple[str, str, list, str | None]:
    """(statut, titre, 3 chiffres clés, alternative) lus dans le résultat du CODE (verdicts, mesures, point de bascule)."""
    if res["arret"]:
        e = res["etapes"][-1]
        return ("bloque" if e["agent"] in GARDE_FOUS else "manquant"), e["texte"], [], None
    d, g, s, verd, alt_ = res["demande"], res["gabarit"], res["symbole"], res["verdicts"], res["alternative"]
    w, n = pct(d["part"]), len(verd["violees"])
    b = d["bascule"]
    chiffres = [(pct(d["mesures"]["parts_risque"].get(s, 0.0)), f"du risque porté par {s} (limite {pct(g['part_risque_max_par_titre'])})"),
                (pct(d["mesures"]["vol"]), f"volatilité du portefeuille (limite {pct(g['volatilite_max'])})"),
                (pct(b["part_max"]) if b["base_conforme"] and b["part_max"] is not None else "—", "point de bascule")]
    manquantes = ", ".join(r["regle"] for r in verd.get("manquantes") or [])
    if verd["statut"] == gouvernance.CONFORME and not manquantes:
        statut, titre = "respecte", f"{w} en {s} respecte les limites de ton profil."
    elif verd["statut"] == gouvernance.CONFORME:
        statut, titre = "manquant", f"{w} en {s} ne viole aucune règle, mais une information manque : {manquantes}."
    elif verd["statut"] == gouvernance.CORRIGEABLE:
        statut, titre = "a_revoir", f"{w} en {s} dépasse {n} limite(s) de ton profil."
    else:
        statut, titre = "bloque", (f"Aucune part de {s} n'est compatible avec ton profil." if b["base_conforme"]
                                   else "Le portefeuille actuel dépasse déjà une limite du profil.")
    alternative = (f"Alternative vérifiée : {pct(alt_['part'])} en {s}, aucune règle violée." if alt_ else None)
    return statut, titre, chiffres, alternative


def afficher_reponse(res, index):
    statut, titre, chiffres, alternative = _verdict(res)
    carte_verdict(statut, titre, chiffres, alternative)
    if res["arret"]:
        return
    f, d, alt_ = res["fiche"], res["demande"], res["alternative"]
    auteur = f.get("auteur", "gabarit")
    if auteur.startswith("Bedrock Guardrails"):          # sortie retenue par le guardrail (src/verif/guardrails.py)
        st.warning("Réponse retenue par Bedrock Guardrails : un message sûr la remplace (voir la trace à droite).",
                   icon="🛡️")
    else:
        st.caption("Rédigé par le LLM (Amazon Bedrock), chiffres contrôlés par le code" if auteur == "llm"
                   else f"Rédigé par un gabarit de texte ({auteur}), chiffres contrôlés par le code")
    st.markdown(f"**{f['intro']}**")
    st.caption("💱 Montants et rendements en dollars canadiens (CAD) — actifs en USD convertis au taux de la Banque du Canada.")
    for l in f["lignes"]:
        traces = "".join(badge_trace(t) for t in l.get("traces", []))
        st.markdown(f"{badge_etiquette(l['tag'])}{l['texte']} {traces}", unsafe_allow_html=True)
    courbe_bascule(res)
    m = d["mesures"]
    with st.expander("Détail par ligne : part des dollars et part du risque"):
        lignes_p = sorted(m["poids"], key=lambda k: -m["parts_risque"].get(k, 0.0))
        barres = go.Figure()
        for nom, serie, couleur in (("Part des dollars", m["poids"], "#C9D7F5"),
                                    ("Part du risque", m["parts_risque"], COULEURS["accent"])):
            vals = [serie.get(k, 0.0) for k in lignes_p]
            barres.add_bar(name=nom, y=lignes_p, x=[100 * x for x in vals], orientation="h", marker_color=couleur,
                           customdata=[pct(x) for x in vals],
                           hovertemplate="%{y} · " + nom.lower() + " %{customdata}<extra></extra>")
        mise_en_page(barres, 60 + 28 * len(lignes_p)).update_layout(
            barmode="group", xaxis=dict(tickformat=",.0f", ticksuffix=" %", gridcolor="#EEEEEA"),
            yaxis=dict(autorange="reversed"), legend=dict(orientation="h", y=1.08))
        st.plotly_chart(barres, width="stretch", config={"displayModeBar": False})
    valeurs = {"Portefeuille actuel": d["base"]["valeurs"], f"Demande {pct(d['part'])}": d["rejeu"]["valeurs"]}
    if alt_:
        valeurs[f"Au point de bascule ({pct(alt_['part'])})"] = alt_["rejeu"]["valeurs"]
    st.caption(f"Ce que 2022 aurait fait à {money(res['persona']['capital'])} (valeur en fin de mois, en CAD)")
    mois = ["début"] + [f"{i:02d}/2022" for i in range(1, len(d["base"]["valeurs"]))]
    rejeu = go.Figure()
    for nom, serie in valeurs.items():
        rejeu.add_scatter(x=mois, y=serie, mode="lines", name=nom,
                          hovertemplate="%{x} · %{y:,.0f} $<extra>" + nom + "</extra>")
    mise_en_page(rejeu, 300).update_layout(yaxis=dict(tickformat=",.0f", ticksuffix=" $", gridcolor="#EEEEEA"),
                                           xaxis=dict(showgrid=False), legend=dict(orientation="h", y=1.12))
    st.plotly_chart(rejeu, width="stretch", config={"displayModeBar": False})
    st.info(f"**Limites.** {f['limites']}")
    rejets = [e for e in res["etapes"] if e["agent"] == "Vérificateur de fidélité" and e["statut"] == "fail"]
    if rejets:
        st.warning(" ".join(e.get("note", "") for e in rejets)
                   + " Elle a été régénérée : la version affichée ne contient que des chiffres présents dans les traces, "
                   "sans formulation de conseil.", title="Le vérificateur a bloqué une version précédente de cette réponse",
                   icon=":material/shield:")
    st.success(f"Chiffres vérifiés : chacun provient d'une trace de calcul ({res['verif']['trace']}).")
    autre = "inter" if f["style"] == "avance" else "avance"
    if st.button("Explique-moi plus simplement" if autre == "inter" else "Version plus technique", key=f"style{index}"):
        with st.spinner("L'Agent Explicabilité reformule, puis le vérificateur contrôle chaque chiffre…"):
            reformuler(res, autre, on_etape=etat.etapes.append)
        st.rerun()
    with st.expander(f"Voir les {len(res['journal'].traces)} traces (journal d'audit)"):
        for t in res["journal"].traces:
            st.markdown(f"**{t['id']} · {t['titre']}** — _{t['agent']}_  \n`{t['outil']}`  \nEntrées : {t['entrees']}  \n"
                        f"Sortie : **{t['sortie']}**  \nSource : {t['source']} · Période : {t['periode']}")
    with st.expander("Voir le mandat JSON (produit par l'Agent Profil)"):
        st.json(res["mandat"], expanded=False)
    st.caption(f"Données : {res['source_donnees']} · montants et rendements en dollars canadiens (CAD)")


# ---------- Écran 2 : « Mon compte » (compte de démonstration du persona) ----------
def _conformite_esg(p: dict, g: dict, univers, m: dict) -> tuple[str, str]:
    """KPI ESG : évaluée par le moteur de règles existant sur le portefeuille actuel (aucun LLM)."""
    if not p.get("exclusions_esg"):
        return "Non applicable", "aucune exclusion ESG dans le profil"
    regle = next(r for r in evaluer_regles(p["portefeuille_suppose"], m, g, univers, p) if r["regle"] == "Exclusions ESG")
    if not regle["ok"]:
        return "Controverse", regle["valeur"]
    if regle.get("manquant"):
        return "Information manquante", regle["valeur"]
    return "Conforme", regle["valeur"]


def section_compte(mandat: dict) -> None:
    p, g = mandat["profil"], mandat["gabarit"]
    poids = p.get("portefeuille_suppose") or {}
    st.markdown("<div class='af-bandeau'>Compte de démonstration · données fictives · simulation, "
                "aucune transaction réelle</div>", unsafe_allow_html=True)
    if not poids or not g:
        st.info("Le compte de démonstration s'affichera dès que la tolérance au risque sera précisée.")
        return
    _, univers, _ = charger()
    m = calculs.mesures(poids)                                   # outils existants : aucun chiffre du LLM
    esg, esg_detail = _conformite_esg(p, g, univers, m)
    k = st.columns(4, gap="medium")
    carte_kpi("Valeur du compte", money(p["capital"]), "CAD · compte de démonstration", k[0])
    carte_kpi("Profil de risque", g["label"], f"horizon {p['horizon']}", k[1])
    carte_kpi("Volatilité annualisée", pct(m["vol"]), f"portefeuille actuel · limite du profil {pct(g['volatilite_max'])}", k[2])
    carte_kpi("Conformité ESG", esg, esg_detail, k[3])

    gauche, droite = st.columns([1.1, 1], gap="large")
    noms = dict(zip(univers["symbole"].astype(str), univers["nom"].astype(str)))
    tri = sorted(poids.items(), key=lambda kv: -kv[1])
    lignes = pd.DataFrame([{"Actif": s, "Nom": noms.get(s, s), "Poids": pct(w), "Valeur": money(w * p["capital"])}
                           for s, w in tri])
    with gauche:
        st.markdown("<div class='af-section'>Positions</div>", unsafe_allow_html=True)
        st.dataframe(lignes, hide_index=True, width="stretch",
                     column_config={"Actif": st.column_config.TextColumn(width="small"),
                                    "Nom": st.column_config.TextColumn(width="medium"),
                                    "Poids": st.column_config.TextColumn(width="small"),
                                    "Valeur": st.column_config.TextColumn("Valeur (CAD)", width="small")})
        anneau = go.Figure(go.Pie(labels=[s for s, _ in tri], values=[w for _, w in tri], hole=0.62, sort=False,
                                  customdata=[pct(w) for _, w in tri], texttemplate="%{label}<br>%{customdata}",
                                  hovertemplate="%{label} · %{customdata}<extra></extra>", textposition="outside",
                                  marker=dict(colors=PALETTE_ANNEAU[:len(tri)], line=dict(color="#FFFFFF", width=2))))
        mise_en_page(anneau, 290).update_layout(showlegend=False)
        st.plotly_chart(anneau, width="stretch", config={"displayModeBar": False})
    with droite:
        st.markdown("<div class='af-section'>Valeur simulée du portefeuille</div>", unsafe_allow_html=True)
        duree = st.segmented_control("Période", ["1A", "3A", "5A"], default="5A", key="periode_compte",
                                     label_visibility="collapsed") or "5A"
        v = calculs.valeur_historique(poids, p["capital"], int(duree[0]))
        courbe = go.Figure(go.Scatter(x=v.index, y=v.values, mode="lines", line=dict(color=COULEURS["accent"], width=2),
                                      fill="tozeroy", fillcolor="rgba(31,111,235,0.06)",
                                      hovertemplate="%{x|%d/%m/%Y}<br>%{y:,.0f} $<extra></extra>"))
        mise_en_page(courbe, 360).update_layout(
            yaxis=dict(range=[v.min() * 0.97, v.max() * 1.02], gridcolor="#EEEEEA", tickformat=",.0f", ticksuffix=" $"),
            xaxis=dict(showgrid=False, tickformat="%m/%Y"))
        st.plotly_chart(courbe, width="stretch", config={"displayModeBar": False})
        st.caption(f"Positions actuelles conservées sur {duree[0]} an(s), rééquilibrées chaque semaine · prix en CAD · "
                   "simulation à partir de l'historique, pas une performance réelle.")
    st.markdown("<a class='af-cta' href='#analyse'>Ce placement me convient-il ?</a>", unsafe_allow_html=True)


# ---------- Écran 3 : analyse (chat | coulisses) ----------
@st.fragment
def interrupteur_coulisses():
    """Dans un fragment : cliqué PENDANT une analyse, il attend qu'elle se termine au lieu de l'interrompre
    (un widget du script principal relancerait tout et couperait l'analyse en cours)."""
    st.toggle("Voir comment j'ai décidé", key="voir_coulisses")
    if etat.voir_coulisses != etat._voir_affiche:     # changement fait à l'arrêt : on redessine toute la page
        etat._voir_affiche = etat.voir_coulisses
        st.rerun()


def ecran_analyse():
    saisie = etat.profil_saisi if etat.persona == "personnalise" else None
    mandat = profil.construire_mandat(None if saisie else etat.persona, saisie)
    p = mandat["profil"]
    tete_g, tete_d = st.columns([4, 1])
    risque = mandat["gabarit"]["label"] if mandat["gabarit"] else "tolérance non précisée"
    age = f", {p['age']} ans" if p.get("age") else ""
    tete_g.header(f"Mon compte · {p['nom']}{age}", anchor=False)
    tete_g.caption(f"{risque} · horizon {p['horizon']} · {p['objectif']}")
    for t in mandat["tensions"]:
        tete_g.warning(f"Tension dans le profil : {t}.", icon="⚠️")
    if tete_d.button("Changer de profil"):
        etat.persona, etat.memoire, etat.demande_en_attente, etat.question_en_cours = None, None, None, None
        st.rerun()
    section_compte(mandat)
    st.markdown("<div id='analyse'></div><div class='af-section'>Analyse d'un placement</div>", unsafe_allow_html=True)

    gauche, droite = st.columns([1.15, 1], gap="large")
    with droite:
        interrupteur_coulisses()
        voir = etat._voir_affiche = etat.voir_coulisses
        if bedrock_client.actif():
            st.caption(f"Agents sur Amazon Bedrock · Profil : {os.getenv('BEDROCK_MODELE_RAPIDE', '?')} · "
                       f"Explicabilité : {os.getenv('BEDROCK_MODELE_REDACTION', '?')}")
        else:
            st.caption("Mode démonstration hors ligne : agents simulés, aucun appel AWS.")
        zone_agents = st.container()
        if voir:
            for i, e in enumerate(etat.etapes):
                etape_timeline(e, derniere=(i == len(etat.etapes) - 1), conteneur=zone_agents)
            if not etat.etapes:
                zone_agents.caption("Les agents apparaîtront ici, un par un : Guardrails → Profil → Analyste → "
                                    "Gouvernance → Explicabilité → Vérificateur de fidélité.")

    with gauche:
        fil = st.container(height=620)
        with fil:
            if not etat.messages:
                with st.chat_message("assistant"):
                    st.markdown(f"Bonjour {p['nom']} ! Pose ta question d'investissement : je l'analyse en simulation, "
                                "je vérifie qu'elle respecte ton profil et je t'explique chaque chiffre.")
            for i, m in enumerate(etat.messages):
                with st.chat_message(m["role"]):
                    if m["role"] == "user":
                        st.markdown(m["texte"])
                    else:
                        afficher_reponse(m["res"], i)
        st.caption(f"Exemple : {p['message_exemple']}")
        # submit_mode="disable" : pas de nouveau message tant que l'analyse en cours n'est pas terminée
        question = st.chat_input("Écris ta question…", submit_mode="disable")

    if question:                                # nouvelle question : mémorisée AVANT l'analyse
        etat.messages.append({"role": "user", "texte": question})
        etat.question_en_cours = question
        etat.etapes = []
        with fil:
            with st.chat_message("user"):
                st.markdown(question)
    elif etat.question_en_cours:                # analyse interrompue par un clic : elle reprend automatiquement
        question = etat.question_en_cours
        etat.etapes = []

    if question:
        with fil:
            attente = st.empty()
            attente.info("Les agents analysent ta demande… suis leur travail à droite.")

        chrono = {"t": time.perf_counter()}

        def en_direct(e):                       # chaque agent apparaît au fur et à mesure, avec sa durée
            maintenant = time.perf_counter()
            e["duree"], chrono["t"] = maintenant - chrono["t"], maintenant
            etat.etapes.append(e)
            if voir:
                etape_timeline(e, conteneur=zone_agents)

        res = executer(None if saisie else etat.persona, question, on_etape=en_direct, profil_saisi=saisie,
                       memoire=etat.memoire, en_attente=etat.demande_en_attente)
        # Demande en attente : gardée si incomplète, complétée au message suivant, vidée quand l'analyse est lancée.
        etat.demande_en_attente = profil.maj_demande_en_attente(etat.demande_en_attente, res, question)
        dem = res.get("demande_extraite")
        if dem is not None:                     # la mémoire suit la DERNIÈRE demande comprise (jamais devinée)
            avant = (etat.memoire or {}).get("derniere_lecture")
            lecture = dem["lecture"] if dem["part"] is not None else None
            etat.memoire = {"symbole": dem["symbole"], "lecture": lecture, "derniere_lecture": lecture or avant}
        attente.empty()
        etat.messages.append({"role": "assistant", "res": res})
        etat.question_en_cours = None           # analyse terminée : plus rien à reprendre
        st.rerun()


if etat.persona is None:
    ecran_profil()
else:
    ecran_analyse()
