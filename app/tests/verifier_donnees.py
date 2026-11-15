"""Vérifie que l'application tourne sur les VRAIES données, et qu'elles sont plausibles.

Depuis app/ :
    python tests/verifier_donnees.py              # vérifications des données
    python tests/verifier_donnees.py --pipeline   # + un passage complet Robert / Tesla en mode local

Sortie : une ligne ✅ / ⚠️ / ❌ par vérification, puis un verdict. Code de sortie 1 s'il y a au moins un ❌.
Les repères de 2022 sont des ORDRES DE GRANDEUR publics (tolérance large), pas des valeurs exactes.
"""
import os
import sys
from pathlib import Path

import pandas as pd

APP = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(APP))
DATA = APP.parent / "data"
if hasattr(sys.stdout, "reconfigure"):          # console Windows (cp1252) : sinon les émojis font planter print
    sys.stdout.reconfigure(encoding="utf-8")

resultats = []


def ok(msg):
    resultats.append("ok"); print(f"✅ {msg}")


def attention(msg):
    resultats.append("warn"); print(f"⚠️  {msg}")


def echec(msg):
    resultats.append("ko"); print(f"❌ {msg}")


def titre(t):
    print(f"\n── {t} " + "─" * max(0, 60 - len(t)))


# ------------------------------------------------------------------ 1. Source utilisée par l'app
titre("1. Source des données lue par l'application")
from src.donnees.chargeur import charger  # noqa: E402

prix, univers, source = charger()
if "FICTIVE" in source.upper() or "DÉMO" in source.upper() or "DEMO" in source.upper():
    echec(f"L'application lit des données FICTIVES : « {source} »")
    print("   → Lancer data/scripts/01_nettoyer_prix.py ou faire git pull pour récupérer data/processed/.")
else:
    ok(f"Source : {source}")

# ------------------------------------------------------------------ 2. Fichiers et dimensions
titre("2. Fichiers et dimensions")
for f in ["prix_cad_alignes.csv", "univers_enrichi.csv", "esg_drapeaux.csv"]:
    (ok if (DATA / "processed" / f).exists() else echec)(f"data/processed/{f} " +
                                                        ("présent" if (DATA / "processed" / f).exists() else "ABSENT"))
print(f"   Prix : {prix.shape[0]} jours × {prix.shape[1]} actifs, du {prix.index.min().date()} au {prix.index.max().date()}")
(ok if prix.shape[1] >= 25 else attention)(f"{prix.shape[1]} actifs dans les prix (attendu : environ 31)")
(ok if prix.index.min().year <= 2021 and prix.index.max().year >= 2026 else attention)("Période couvrant 2021 → 2026")
sym_univers = set(univers["symbole"].astype(str)) if "symbole" in univers.columns else set()
manquants = sorted(sym_univers - set(prix.columns))
(ok if not manquants else echec)("Tous les actifs de l'univers ont des prix" if not manquants
                                 else f"Actifs de l'univers sans prix : {manquants}")
nan = int(prix.isna().sum().sum())
(ok if nan == 0 else attention)(f"{nan} valeur(s) manquante(s) dans les prix nettoyés")

# ------------------------------------------------------------------ 3. Taux de change
titre("3. Taux de change USD/CAD")
fx_path = DATA / "raw" / "starter" / "fx_usdcad_daily.csv"
fx = None
if fx_path.exists():
    brut = pd.read_csv(fx_path)
    col_date = next(c for c in brut.columns if c.lower() == "date")
    col_val = next(c for c in brut.columns if c != col_date and pd.api.types.is_numeric_dtype(brut[c]))
    fx = brut.set_index(pd.to_datetime(brut[col_date]))[col_val].sort_index()
    lo, hi = fx.min(), fx.max()
    (ok if 1.15 < lo and hi < 1.55 else echec)(f"Colonne « {col_val} » entre {lo:.3f} et {hi:.3f} (attendu : CAD pour 1 USD, ≈ 1,2 à 1,5)")
else:
    attention("fx_usdcad_daily.csv introuvable dans data/raw/starter/")

# ------------------------------------------------------------------ 4. Vraisemblance 2022 (devise d'origine)
titre("4. Rendements 2022 en devise d'origine (repères publics, tolérance ±6 points)")
REPERES = {"TSLA": -0.65, "NVDA": -0.50, "SPY": -0.18, "BTC-USD": -0.64}
raw_path = DATA / "raw" / "starter" / "prices_daily.csv"
raw = None
if raw_path.exists():
    raw = pd.read_csv(raw_path, parse_dates=["date"])
    col_sym = "ticker" if "ticker" in raw.columns else ("symbol" if "symbol" in raw.columns else "symbole")
    for sym, attendu in REPERES.items():
        s = raw[(raw[col_sym] == sym) & (raw["date"].dt.year == 2022)].sort_values("date")["adj_close"]
        if s.empty:
            attention(f"{sym} absent des prix bruts")
            continue
        r = s.iloc[-1] / s.iloc[0] - 1
        (ok if abs(r - attendu) <= 0.06 else echec)(f"{sym} 2022 : {r:+.1%} (repère ≈ {attendu:+.0%})")
else:
    attention("prices_daily.csv introuvable dans data/raw/starter/")

# ------------------------------------------------------------------ 5. Conversion en CAD cohérente
titre("5. Conversion en CAD (prix propres vs bruts × taux)")
if raw is not None and fx is not None:
    for sym in ["TSLA", "SPY"]:
        if sym not in prix.columns:
            continue
        s_usd = raw[(raw[col_sym] == sym) & (raw["date"].dt.year == 2022)].sort_values("date")
        s_cad = prix.loc["2022", sym].dropna()
        r_usd = s_usd["adj_close"].iloc[-1] / s_usd["adj_close"].iloc[0] - 1
        f0, f1 = fx.asof(s_usd["date"].iloc[0]), fx.asof(s_usd["date"].iloc[-1])
        attendu_cad = (1 + r_usd) * (f1 / f0) - 1
        r_cad = s_cad.iloc[-1] / s_cad.iloc[0] - 1
        (ok if abs(r_cad - attendu_cad) <= 0.01 else echec)(
            f"{sym} 2022 en CAD : {r_cad:+.1%} (attendu d'après USD × taux : {attendu_cad:+.1%})")

# ------------------------------------------------------------------ 6. Fractionnements d'actions
titre("6. Fractionnements : aucune chute artificielle")
SPLITS = {"TSLA": "2022-08-25", "SHOP.TO": "2022-06-29", "NVDA": "2024-06-10"}
for sym, jour in SPLITS.items():
    if sym not in prix.columns:
        attention(f"{sym} absent des prix")
        continue
    fen = prix[sym].loc[pd.Timestamp(jour) - pd.Timedelta(days=7): pd.Timestamp(jour) + pd.Timedelta(days=7)]
    pire = fen.pct_change().min()
    (ok if pire > -0.35 else echec)(f"{sym} autour du {jour} : pire variation sur un jour {pire:+.1%}")

# ------------------------------------------------------------------ 7. ESG
titre("7. Données ESG")
esg_path = DATA / "processed" / "esg_drapeaux.csv"
if esg_path.exists():
    esg = pd.read_csv(esg_path)
    print(f"   Colonnes : {list(esg.columns)}")
    col_c = next((c for c in esg.columns if "controverse" in c.lower() or "statut" in c.lower()), None)
    if col_c:
        print("   Répartition : " + ", ".join(f"{k} = {v}" for k, v in esg[col_c].astype(str).value_counts().items()))
    a_motif = any("motif" in c.lower() for c in esg.columns)
    (ok if a_motif else attention)("Colonne « motif » présente" if a_motif else "Colonne « motif » ABSENTE (raison de l'exclusion)")
    for sym in ["ENB.TO", "XOM", "JNJ", "ESGV", "XBB.TO"]:
        ligne = esg[esg["symbole"].astype(str) == sym]
        if ligne.empty:
            attention(f"{sym} absent du fichier ESG")
        else:
            print(f"   {sym:8} → " + " · ".join(f"{c}={ligne.iloc[0][c]}" for c in esg.columns if c != "symbole"))
else:
    echec("data/processed/esg_drapeaux.csv absent (lancer data/scripts/02_construire_esg.py)")

# ------------------------------------------------------------------ 8. Portefeuilles supposés des personas
titre("8. Portefeuilles supposés des personas")
from src import config  # noqa: E402
for pid, p in config.PERSONAS.items():
    base = p.get("portefeuille_suppose") or {}
    absents = [s for s in base if s not in prix.columns]
    somme = sum(base.values()) if base else 0
    if not base:
        attention(f"{pid} : aucun portefeuille supposé trouvé (clé « portefeuille_suppose »)")
    elif absents:
        echec(f"{pid} : symboles absents des prix : {absents}")
    else:
        (ok if abs(somme - 1) < 0.01 else attention)(f"{pid} : {len(base)} actifs présents dans les prix, poids total {somme:.0%}")

# ------------------------------------------------------------------ 9. Passage complet (optionnel)
if "--pipeline" in sys.argv:
    titre("9. Passage complet Robert / Tesla (mode local, sans Bedrock)")
    os.environ["MODE"] = "local"
    config.MODE = "local"
    try:
        from src.orchestrateur import executer
        r = executer("robert", "Tout le monde parle de Tesla, je pense mettre 30 % dedans.")
    except Exception as e:                       # on veut un diagnostic, pas un plantage
        r = None
        echec(f"Le pipeline plante : {type(e).__name__} : {e}")
    if r is not None:
        (ok if not r["arret"] else echec)("Le pipeline va jusqu'au bout")
    if r is not None and not r["arret"]:
        print(f"   Règles violées : {len(r['verdicts']['violees'])} · alternative : "
              f"{r['alternative']['part'] if r['alternative'] else 'aucune'}")
        print(f"   Source indiquée dans la réponse : {r.get('source_donnees', '?')}")

# ------------------------------------------------------------------ Verdict
nb_ko, nb_warn = resultats.count("ko"), resultats.count("warn")
print("\n" + "═" * 64)
if nb_ko:
    print(f"❌ {nb_ko} problème(s) bloquant(s), {nb_warn} avertissement(s) : NE PAS faire la démo sur ces données.")
elif nb_warn:
    print(f"⚠️  Données réelles OK, mais {nb_warn} avertissement(s) à regarder.")
else:
    print("✅ L'application tourne sur les vraies données, et elles sont plausibles.")
sys.exit(1 if nb_ko else 0)
