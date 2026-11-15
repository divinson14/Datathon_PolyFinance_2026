"""Composants visuels réutilisables (présentation SEULEMENT : aucun calcul, aucune décision).
carte_kpi · carte_verdict · etape_timeline · badge_etiquette."""
from html import escape

import pandas as pd
import streamlit as st

from ui.style import COULEURS as C

# Étiquettes des affirmations de l'Explicabilité → (fond, texte)
ETIQUETTES = {"Fait": ("#E8F0FE", "#1F4FB0"), "Donnée du compte (fictif)": ("#E6F4EE", "#12805C"),
              "Hypothèse": ("#FDF3E1", "#8A5A12"), "Scénario fictif": ("#EFEAFB", "#5B3BA8")}

# Statut du verdict → (libellé, couleur)
VERDICTS = {"respecte": ("Respecté", C["vert"]), "a_revoir": ("À revoir", C["orange"]),
            "manquant": ("Information manquante", C["orange"]), "bloque": ("Bloqué", C["rouge"])}

STATUTS_ETAPE = {"ok": C["vert"], "warn": C["orange"], "fail": C["rouge"]}
ICONES_AGENT = {"Bedrock Guardrails": "🛡", "Garde-fou local": "🛡", "Agent Profil": "👤", "Agent Analyste": "📊",
                "Agent Gouvernance": "⚖", "Orchestrateur": "↻", "Agent Explicabilité": "✎",
                "Vérificateur de fidélité": "✓"}


def badge_etiquette(tag: str) -> str:
    """HTML d'un badge coloré : Fait, Donnée du compte (fictif), Hypothèse, Scénario fictif."""
    fond, texte = ETIQUETTES.get(tag, ("#F1F1EF", C["gris"]))
    return f"<span class='af-badge' style='background:{fond};color:{texte}'>{escape(tag)}</span>"


def badge_trace(tid: str) -> str:
    return f"<span class='af-trace'>{escape(str(tid))}</span>"


def carte_kpi(titre: str, valeur: str, detail: str | None = None, conteneur=st) -> None:
    conteneur.markdown(f"<div class='af-kpi'><div class='titre'>{escape(titre)}</div>"
                       f"<div class='valeur'>{escape(valeur)}</div>"
                       + (f"<div class='detail'>{escape(detail)}</div>" if detail else "") + "</div>",
                       unsafe_allow_html=True)


def carte_verdict(statut: str, titre: str, chiffres: list[tuple[str, str]] | None = None,
                  alternative: str | None = None) -> None:
    """statut ∈ respecte | a_revoir | manquant | bloque ; chiffres = [(valeur, libellé)] (au plus 3)."""
    libelle, couleur = VERDICTS[statut]
    blocs = "".join(f"<div class='af-chiffre'><div class='v'>{escape(v)}</div><div class='l'>{escape(l)}</div></div>"
                    for v, l in (chiffres or [])[:3])
    st.markdown(f"<div class='af-verdict' style='border-color:{couleur}33;background:{couleur}0D'>"
                f"<div class='statut' style='color:{couleur}'>● {libelle}</div>"
                f"<div class='titre'>{escape(titre)}</div>"
                + (f"<div class='af-chiffres'>{blocs}</div>" if blocs else "")
                + (f"<div class='af-alternative'>{escape(alternative)}</div>" if alternative else "")
                + "</div>", unsafe_allow_html=True)


def _statut_regle(r: dict) -> str:
    return ("⚠️ Information manquante" if r.get("manquant") else "➖ Non applicable" if r.get("neutre")
            else "✅ Respecté" if r["ok"] else "❌ Violé")


def etape_timeline(e: dict, derniere: bool = False, conteneur=st) -> None:
    """Une étape de la ligne de temps verticale : icône, statut coloré, une phrase, durée, trace ; détail repliable."""
    couleur = STATUTS_ETAPE.get(e.get("statut"), C["gris"])
    icone = ICONES_AGENT.get(e["agent"].split(" · ")[0], "•")
    meta = " · ".join(x for x in [f"{e['duree']:.1f} s" if e.get("duree") is not None else None,
                                  f"trace {e['trace']}" if e.get("trace") else None] if x)
    conteneur.markdown(
        f"<div class='af-etape'><div class='rail'><div class='icone' style='border-color:{couleur};color:{couleur}'>"
        f"{icone}</div>{'' if derniere else '<div class=ligne></div>'}</div>"
        f"<div class='corps'><div class='agent'>{escape(e['agent'])}</div>"
        f"<div class='phrase'>{escape(e['texte'])}</div>"
        + (f"<div class='meta'>{escape(meta)}</div>" if meta else "") + "</div></div>", unsafe_allow_html=True)
    details = any(k in e for k in ("mandat", "calculs", "regles")) or any(
        e.get(k) for k in ("resume", "consigne", "tensions", "note"))
    if not details:
        return
    with conteneur.expander("Détail", expanded=False):
        if "mandat" in e:
            st.dataframe(pd.DataFrame(e["mandat"], columns=["", "Valeur"]), hide_index=True, width="stretch")
        if "calculs" in e:
            st.dataframe(pd.DataFrame(e["calculs"], columns=["Outil / calcul", "Résultat", "Trace"]),
                         hide_index=True, width="stretch")
        if "regles" in e:
            st.dataframe(pd.DataFrame([{"Règle": r["regle"], "Limite": r["limite"], "Valeur": r["valeur"],
                                        "Statut": _statut_regle(r)} for r in e["regles"]]),
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
