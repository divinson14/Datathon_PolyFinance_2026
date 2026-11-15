"""Style AlphaForge : CSS injecté UNE fois (police Inter, cartes arrondies, couleurs sobres).
Les couleurs reprennent .streamlit/config.toml. Aucun logo ni couleur d'une vraie banque."""
import streamlit as st

COULEURS = {"fond": "#F7F7F5", "carte": "#FFFFFF", "texte": "#111111", "accent": "#1F6FEB",
            "vert": "#12805C", "orange": "#B7791F", "rouge": "#C53030", "gris": "#6B7280", "bord": "#E7E7E3"}

_CSS = """
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@300;400;500;600&display=swap" rel="stylesheet">
<style>
html, body, [class*="st-"], .stMarkdown, button, input, textarea { font-family: 'Inter', sans-serif !important; }
#MainMenu, footer, [data-testid="stDecoration"], [data-testid="stStatusWidget"] { visibility: hidden; height: 0; }
header[data-testid="stHeader"] { background: transparent; }
.block-container { padding-top: 2.2rem; padding-bottom: 4rem; max-width: 1280px; }
h1, h2, h3 { font-weight: 300 !important; letter-spacing: -0.02em; color: %(texte)s; }
h1 { font-size: 2.6rem !important; }
[data-testid="stVerticalBlockBorderWrapper"] { background: %(carte)s; border-radius: 16px !important;
  border: 1px solid %(bord)s !important; box-shadow: 0 1px 2px rgba(17,17,17,.04); }
.stButton > button, [data-testid="stBaseButton-primary"], [data-testid="stBaseButton-secondary"] {
  border-radius: 999px !important; font-weight: 500; padding: .45rem 1.1rem; }
[data-testid="stChatInput"] textarea { border-radius: 14px; }

/* Marque et bandeaux */
.af-marque { font-size: 1.35rem; font-weight: 600; letter-spacing: -0.03em; color: %(texte)s; }
.af-marque span { color: %(accent)s; }
.af-pastille { display:inline-flex; align-items:center; gap:6px; font-size:.78rem; color:%(gris)s;
  background:%(carte)s; border:1px solid %(bord)s; border-radius:999px; padding:3px 10px; }
.af-point { width:7px; height:7px; border-radius:50%%; display:inline-block; }
.af-bandeau { font-size:.82rem; color:%(gris)s; background:%(carte)s; border:1px solid %(bord)s;
  border-radius:12px; padding:8px 14px; margin: 4px 0 18px 0; }
.af-sous-titre { color:%(gris)s; font-size:1rem; margin-top:-8px; margin-bottom:28px; }

/* Cartes KPI */
.af-kpi { background:%(carte)s; border:1px solid %(bord)s; border-radius:16px; padding:18px 20px;
  box-shadow:0 1px 2px rgba(17,17,17,.04); height:100%%; }
.af-kpi .titre { color:%(gris)s; font-size:.8rem; text-transform:uppercase; letter-spacing:.06em; }
.af-kpi .valeur { font-size:1.75rem; font-weight:300; color:%(texte)s; margin-top:6px; letter-spacing:-0.02em; }
.af-kpi .detail { color:%(gris)s; font-size:.82rem; margin-top:4px; }

/* Persona */
.af-avatar { width:56px; height:56px; border-radius:50%%; background:#EAF1FE; color:%(accent)s;
  display:flex; align-items:center; justify-content:center; font-weight:600; font-size:1.2rem; margin-bottom:10px; }
.af-persona-nom { font-size:1.35rem; font-weight:400; }
.af-persona-meta { color:%(gris)s; font-size:.88rem; margin:2px 0 10px 0; }
.af-persona-phrase { font-size:.95rem; color:%(texte)s; min-height:3.2em; }

/* Verdict */
.af-verdict { border-radius:16px; padding:18px 20px; margin-bottom:14px; border:1px solid; }
.af-verdict .statut { font-size:.78rem; font-weight:600; text-transform:uppercase; letter-spacing:.07em; }
.af-verdict .titre { font-size:1.15rem; font-weight:400; margin-top:4px; color:%(texte)s; }
.af-chiffres { display:flex; gap:24px; margin-top:14px; flex-wrap:wrap; }
.af-chiffre .v { font-size:1.4rem; font-weight:300; color:%(texte)s; }
.af-chiffre .l { font-size:.76rem; color:%(gris)s; }
.af-alternative { margin-top:12px; font-size:.9rem; color:%(texte)s; }

/* Étiquettes et traces */
.af-badge { display:inline-block; font-size:.68rem; font-weight:600; text-transform:uppercase; letter-spacing:.05em;
  padding:2px 8px; border-radius:999px; margin-right:8px; vertical-align:1px; }
.af-trace { font-family: ui-monospace, monospace; font-size:.72rem; color:%(accent)s; border:1px solid #D6E2FB;
  border-radius:6px; padding:0 5px; margin-left:4px; }

/* Ligne de temps des agents */
.af-etape { display:flex; gap:12px; position:relative; padding-bottom:6px; }
.af-etape .rail { display:flex; flex-direction:column; align-items:center; }
.af-etape .icone { width:30px; height:30px; border-radius:50%%; display:flex; align-items:center; justify-content:center;
  font-size:.95rem; border:2px solid; background:%(carte)s; }
.af-etape .ligne { width:2px; flex:1; background:%(bord)s; min-height:14px; }
.af-etape .corps { flex:1; padding-bottom:10px; }
.af-etape .agent { font-weight:500; font-size:.92rem; }
.af-etape .meta { color:%(gris)s; font-size:.75rem; }
.af-etape .phrase { font-size:.88rem; margin-top:2px; }
</style>
"""


def injecter_style() -> None:
    """À appeler une fois en haut de l'application."""
    st.markdown(_CSS % COULEURS, unsafe_allow_html=True)
