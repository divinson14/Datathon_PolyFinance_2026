"""Interface AlphaForge : 1) choix du profil, 2) écran coupé en deux (chat | agents en direct).
Lancer depuis app/ :  streamlit run ui/streamlit_app.py
Maquette de référence : docs/prototype/index.html"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))   # rend « src » importable

import altair as alt
import pandas as pd
import streamlit as st

from src import config
from src.agents import explicabilite, profil
from src.donnees.chargeur import LIBELLE_DEMO, donnees_fictives
from src.formatage import money, pct
from src.orchestrateur import executer, reformuler

st.set_page_config(page_title="AlphaForge AI", layout="wide")
st.markdown("""<style>
.tag{display:inline-block;font-size:11px;font-weight:700;text-transform:uppercase;padding:2px 7px;border-radius:6px;margin-right:6px}
.fait{background:#E6EEFC;color:#1A3E9E}.hyp{background:#FFF4D6;color:#6B4200}.scen{background:#EEE8FB;color:#4B2C9E}
.tr{font-family:monospace;font-size:12px;color:#1F4FD1;border:1px solid #C9D3E6;border-radius:5px;padding:1px 5px;margin-left:3px}
</style>""", unsafe_allow_html=True)

ICONES = {"ok": "✅", "warn": "⚠️", "fail": "❌"}
CLASSES = {"Fait": "fait", "Hypothèse": "hyp", "Scénario fictif": "scen"}
etat = st.session_state
etat.setdefault("persona", None)
etat.setdefault("profil_saisi", None)
etat.setdefault("messages", [])
etat.setdefault("etapes", [])
etat.setdefault("memoire", None)          # dernier actif / dernière part, pour les relances courtes

st.warning("**Simulation uniquement** — aucune transaction réelle, aucun conseil financier personnalisé.", icon="⚠️")
if donnees_fictives():          # repli silencieux du chargeur : on le rend impossible à manquer
    st.error(f"**{LIBELLE_DEMO}.** Les chiffres affichés sont simulés et ne reflètent pas les marchés réels. "
             "Pour les vraies données : `python data/scripts/01_nettoyer_prix.py` puis redémarrer.", icon="🚨")


# ---------- Écran 1 : choix du profil ----------
def ecran_profil():
    st.title("Choisis ton profil d'investisseur")
    st.caption("Profils fictifs. Le même système répond différemment selon le risque, l'horizon et les préférences.")
    cols = st.columns(len(config.PERSONAS))
    for col, (pid, p) in zip(cols, config.PERSONAS.items()):
        with col.container(border=True):
            st.subheader(f"{p['nom']}, {p['age']} ans")
            st.caption(p["metier"])
            st.markdown(f"**Risque :** {config.GABARITS[p['risque']]['label']}  \n**Horizon :** {p['horizon']}")
            st.markdown(f"**Objectif :** {p['objectif']}")
            st.markdown("\n".join(f"- {x}" for x in p["preferences"]))
            a_faire = p.get("a_faire")
            if st.button(f"Continuer avec {p['nom']}", key=pid, width="stretch", type="primary", disabled=bool(a_faire)):
                etat.persona, etat.messages, etat.etapes, etat.memoire = pid, [], [], None
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
                etat.messages, etat.etapes, etat.memoire = [], [], None
                st.rerun()


# ---------- Panneau droit : une carte par étape ----------
def afficher_etape(e, conteneur):
    with conteneur.container(border=True):
        st.markdown(f"{ICONES.get(e['statut'], '•')} **{e['agent']}** — {e['texte']}")
        if "mandat" in e:
            st.dataframe(pd.DataFrame(e["mandat"], columns=["", "Valeur"]), hide_index=True, width="stretch")
        if "calculs" in e:
            st.dataframe(pd.DataFrame(e["calculs"], columns=["Calcul", "Résultat", "Trace"]), hide_index=True, width="stretch")
        if "regles" in e:
            st.dataframe(pd.DataFrame([{"Règle": r["regle"], "Limite": r["limite"], "Valeur": r["valeur"],
                                        "Statut": ("⚠️ Information manquante" if r.get("manquant") else
                                                   "➖ Non applicable" if r.get("neutre") else
                                                   "✅ Respecté" if r["ok"] else "❌ Violé")} for r in e["regles"]]),
                         hide_index=True, width="stretch")
        if e.get("resume"):
            st.markdown(e["resume"])
            if e.get("redaction"):
                st.caption("Formulé par le LLM, chiffres vérifiés" if e["redaction"] == "llm"
                           else f"Formulé par le code ({e['redaction']})")
        if e.get("consigne"):
            st.caption(f"Correction envoyée à l'Analyste : « {e['consigne']} »")
        for tension in e.get("tensions") or []:
            st.caption(f"⚖️ Tension avec le profil : {tension}")
        if e.get("note"):
            st.caption(e["note"])
        if e.get("trace"):
            st.caption(f"Trace : {e['trace']}")


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
    df = df.assign(respecte=df["conforme"].map({True: "oui", False: "non"}))

    axe_x = alt.X("part:Q", title=f"Part de {s} dans le portefeuille",
                  axis=alt.Axis(format="%", tickCount=6, gridOpacity=0.35), scale=alt.Scale(domain=[0, xmax], nice=False))
    axe_y = alt.Y("part_risque:Q", title=f"Part du risque portée par {s}",
                  axis=alt.Axis(format="%", tickCount=5, gridOpacity=0.35), scale=alt.Scale(domain=[0, 1]))
    couches = []
    if seuil is not None:                                   # zone hors profil, discrète
        couches.append(alt.Chart(pd.DataFrame({"x": [seuil], "x2": [xmax]})).mark_rect(opacity=0.07, color=encre)
                       .encode(x="x:Q", x2="x2:Q"))
    couches.append(alt.Chart(df).mark_line(strokeWidth=2).encode(
        x=axe_x, y=axe_y,
        tooltip=[alt.Tooltip("part:Q", title=f"Part de {s}", format=".1%"),
                 alt.Tooltip("part_risque:Q", title="Part du risque", format=".1%"),
                 alt.Tooltip("vol:Q", title="Volatilité du portefeuille", format=".1%"),
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
def afficher_reponse(res, index):
    if res["arret"]:
        st.markdown(res["etapes"][-1]["texte"])
        return
    f, d, alt_ = res["fiche"], res["demande"], res["alternative"]
    auteur = f.get("auteur", "gabarit")
    st.caption("Rédigé par le LLM (Amazon Bedrock), chiffres contrôlés par le code" if auteur == "llm"
               else f"Rédigé par un gabarit de texte ({auteur}), chiffres contrôlés par le code")
    st.markdown(f"**{f['intro']}**")
    st.caption("💱 Montants et rendements en dollars canadiens (CAD) — actifs en USD convertis au taux de la Banque du Canada.")
    for l in f["lignes"]:
        traces = "".join(f"<span class='tr'>{t}</span>" for t in l.get("traces", []))
        st.markdown(f"<span class='tag {CLASSES.get(l['tag'], 'fait')}'>{l['tag']}</span>{l['texte']} {traces}", unsafe_allow_html=True)
    courbe_bascule(res)
    m = d["mesures"]
    with st.expander("Détail par ligne : part des dollars et part du risque"):
        st.bar_chart(pd.DataFrame({"Part des dollars": pd.Series(m["poids"]), "Part du risque": pd.Series(m["parts_risque"])}),
                     stack=False, horizontal=True, alt="Part des dollars et part du risque de chaque ligne du portefeuille demandé")
    valeurs = {"Portefeuille actuel": d["base"]["valeurs"], f"Demande {pct(d['part'])}": d["rejeu"]["valeurs"]}
    if alt_:
        valeurs[f"Au point de bascule ({pct(alt_['part'])})"] = alt_["rejeu"]["valeurs"]
    st.caption(f"Ce que 2022 aurait fait à {money(res['persona']['capital'])} (valeur en fin de mois, en CAD)")
    st.line_chart(pd.DataFrame(valeurs, index=["début"] + [f"{m:02d}" for m in range(1, len(d['base']['valeurs']))]),
                  alt=f"Valeur simulée du portefeuille pendant 2022, avec et sans la demande")
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


# ---------- Écran 2 : chat | coulisses ----------
def ecran_analyse():
    saisie = etat.profil_saisi if etat.persona == "personnalise" else None
    mandat = profil.construire_mandat(None if saisie else etat.persona, saisie)
    p = mandat["profil"]
    tete_g, tete_d = st.columns([4, 1])
    risque = mandat["gabarit"]["label"] if mandat["gabarit"] else "tolérance non précisée"
    age = f", {p['age']} ans" if p.get("age") else ""
    tete_g.markdown(f"### {p['nom']}{age} · {risque} · {p['horizon']}")
    for t in mandat["tensions"]:
        tete_g.warning(f"Tension dans le profil : {t}.", icon="⚠️")
    if tete_d.button("Changer de profil"):
        etat.persona, etat.memoire = None, None
        st.rerun()

    gauche, droite = st.columns([1.15, 1], gap="large")
    with droite:
        st.markdown("#### Dans les coulisses")
        import os
        from src import bedrock_client
        if bedrock_client.actif():
            st.caption(f"🟢 Mode **Bedrock** · région {os.getenv('AWS_REGION', '?')} · "
                       f"Profil : {os.getenv('BEDROCK_MODELE_RAPIDE', '?')} · Explicabilité : {os.getenv('BEDROCK_MODELE_REDACTION', '?')}")
        else:
            st.caption("⚪ Mode **local** (aucun appel AWS). Pour Bedrock : MODE=bedrock dans app/.env, puis redémarrer Streamlit.")
        zone_agents = st.container()
        for e in etat.etapes:
            afficher_etape(e, zone_agents)

    with gauche:
        st.markdown("#### Conversation")
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
        question = st.chat_input("Écris ta question…")

    if question:
        etat.messages.append({"role": "user", "texte": question})
        etat.etapes = []
        with fil:
            with st.chat_message("user"):
                st.markdown(question)
            attente = st.empty()
            attente.info("Les agents analysent ta demande… suis leur travail à droite.")

        def en_direct(e):                       # chaque agent apparaît au fur et à mesure
            etat.etapes.append(e)
            afficher_etape(e, zone_agents)

        res = executer(None if saisie else etat.persona, question, on_etape=en_direct, profil_saisi=saisie,
                       memoire=etat.memoire)
        dem = res.get("demande_extraite")
        if dem is not None:                     # la mémoire suit la DERNIÈRE demande comprise (jamais devinée)
            avant = (etat.memoire or {}).get("derniere_lecture")
            lecture = dem["lecture"] if dem["part"] is not None else None
            etat.memoire = {"symbole": dem["symbole"], "lecture": lecture, "derniere_lecture": lecture or avant}
        attente.empty()
        etat.messages.append({"role": "assistant", "res": res})
        st.rerun()


if etat.persona is None:
    ecran_profil()
else:
    ecran_analyse()
