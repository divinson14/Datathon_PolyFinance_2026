"""Style AlphaForge : la feuille ui/style.css est injectée UNE fois, en un seul bloc <style>.
Le CSS est compact (aucune ligne vide, aucun commentaire) : une ligne vide dans un bloc HTML passé à st.markdown
coupe le bloc, et le reste s'affichait en texte brut. Aucun logo ni couleur d'une vraie banque."""
from pathlib import Path

import streamlit as st

COULEURS = {"fond": "#F7F7F5", "carte": "#FFFFFF", "texte": "#111111", "accent": "#1F6FEB",
            "vert": "#12805C", "orange": "#B7791F", "rouge": "#C53030", "gris": "#6B7280", "bord": "#E7E7E3"}

FEUILLE = Path(__file__).with_name("style.css")


def css_compact() -> str:
    """Contenu de style.css sans lignes vides (garde-fou si quelqu'un en ajoute une)."""
    return "\n".join(l.strip() for l in FEUILLE.read_text(encoding="utf-8").splitlines() if l.strip())


def injecter_style() -> None:
    """À appeler une fois en haut de l'application."""
    st.markdown(f"<style>{css_compact()}</style>", unsafe_allow_html=True)
