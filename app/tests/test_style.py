"""Feuille de style de l'interface : un bloc <style> avec une ligne vide ou un commentaire était coupé par le parseur
Markdown de Streamlit, et le CSS s'affichait en texte brut. La police Inter ne doit jamais s'appliquer aux icônes."""
from pathlib import Path

CSS = (Path(__file__).resolve().parents[1] / "ui" / "style.css").read_text(encoding="utf-8")


def test_css_compact_sans_ligne_vide_ni_commentaire():
    assert all(l.strip() for l in CSS.splitlines()), "ligne vide dans ui/style.css"
    assert "/*" not in CSS and "*/" not in CSS, "commentaire dans ui/style.css"


def test_classes_attendues_presentes():
    for classe in (".af-kpi", ".af-avatar", ".af-verdict", ".af-etape", ".af-badge"):
        assert classe in CSS, classe


def test_icones_material_jamais_en_inter():
    assert '[data-testid="stIconMaterial"]' in CSS and '"Material Symbols Rounded" !important' in CSS
    assert '[class*="st-"]' not in CSS                       # ce sélecteur appliquait Inter aux icônes


def test_ancres_des_titres_masquees():
    assert '[data-testid="stHeaderActionElements"]' in CSS
