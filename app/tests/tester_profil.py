"""Banc d'essai de l'Agent Profil, à lancer à la main AVANT un commit. Depuis app/ :

    python tests/tester_profil.py                 # local : règles + alias, aucun appel AWS
    python tests/tester_profil.py --aws           # vérifie identifiants, région, modèle et guardrail (sans appeler le LLM)
    python tests/tester_profil.py --modeles       # liste les profils d'inférence Bedrock accessibles (pour remplir .env)
    python tests/tester_profil.py --bedrock       # VRAIS appels Bedrock (quelques centimes), comparés au mode local
    python tests/tester_profil.py --diagnostic    # UN appel par modèle, message d'erreur AWS complet

Rien n'est écrit ailleurs que dans traces_locales/. Aucun secret n'est affiché.
"""
import argparse
import os
import sys
from pathlib import Path

parser = argparse.ArgumentParser()
parser.add_argument("--aws", action="store_true", help="contrôle de la configuration AWS seulement")
parser.add_argument("--modeles", action="store_true", help="liste les profils d'inférence Bedrock")
parser.add_argument("--bedrock", action="store_true", help="vrais appels Bedrock")
parser.add_argument("--diagnostic", action="store_true", help="un appel par modèle, erreur complète")
args = parser.parse_args()
if args.bedrock or args.diagnostic:
    os.environ["MODE"] = "bedrock"           # avant tout import de src.config
os.environ.setdefault("TRACES", "local")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src import bedrock_client  # noqa: E402
from src.agents import profil  # noqa: E402
from src.donnees.chargeur import charger  # noqa: E402
from src.formatage import pct  # noqa: E402
from src.traces.journal import Journal  # noqa: E402

# (persona, message, attendu : symbole, part, arrêt ?)
CAS = [
    ("robert", "Tout le monde parle de Tesla, je pense mettre 30 % dedans.", "TSLA", 0.30, False),
    ("robert", "J'ai 200 000 $ de côté, je voudrais placer 50 000 $ dans Tesla.", "TSLA", 0.25, False),
    ("amira", "Et si je mettais 5 % en Bitcoin ?", "BTC-USD", 0.05, False),
    ("amira", "Je veux 15 % dans le constructeur de voitures électriques d'Elon Musk.", "TSLA", 0.15, False),  # périphrase : LLM seulement
    ("mateo", "10 % dans la Banque Royale, c'est raisonnable ?", "RY.TO", 0.10, False),
    ("robert", "Je veux investir dans Tesla.", None, None, True),
    ("amira", "Je veux mettre 10 % dans Tesla ou dans Nvidia.", None, None, True),
    ("amira", "Je mets 150 % dans Tesla.", None, None, True),
    ("robert", "Je veux mettre 20 % dans Bombardier.", None, None, True),
]


def verifier_aws() -> bool:
    import boto3
    ok = True
    session = boto3.Session()
    cred = session.get_credentials()
    region = os.getenv("AWS_REGION") or session.region_name
    print(f"Identifiants AWS : {'trouvés (' + cred.method + ')' if cred else 'AUCUN → aws configure, ou variables fournies par les organisateurs'}")
    print(f"Région           : {region or 'AUCUNE → AWS_REGION dans app/.env'}")
    ok &= bool(cred) and bool(region)
    for var in ("BEDROCK_MODELE_RAPIDE", "BEDROCK_MODELE_REDACTION"):
        print(f"{var:<16} : {os.getenv(var) or 'VIDE → python tests/tester_profil.py --modeles'}")
        ok &= bool(os.getenv(var))
    print(f"Guardrail        : {'défini' if os.getenv('BEDROCK_GUARDRAIL_ID') else 'non défini (facultatif pour tester le Profil)'}")
    if cred:
        try:
            ident = boto3.client("sts", region_name=region).get_caller_identity()
            print(f"Compte           : …{ident['Account'][-4:]} (appel STS réussi)")
        except Exception as e:                                        # noqa: BLE001
            print(f"Appel STS refusé : {type(e).__name__} → identifiants expirés ou invalides")
            ok = False
    return ok


def lister_modeles():
    import boto3
    client = boto3.client("bedrock", region_name=os.getenv("AWS_REGION", "us-east-1"))
    profils = client.list_inference_profiles(maxResults=100).get("inferenceProfileSummaries", [])
    print("Profils d'inférence accessibles (à copier dans BEDROCK_MODELE_RAPIDE / _REDACTION) :")
    for p in sorted(profils, key=lambda p: p["inferenceProfileId"]):
        print(f"  {p['inferenceProfileId']:<55} {p.get('status', '')}")
    if not profils:
        print("  aucun : activer l'accès aux modèles dans la console Bedrock (Model access).")


def executer_cas():
    _, univers, source = charger()
    from src.config import PERSONAS
    mode = "BEDROCK (vrais appels)" if bedrock_client.actif() else "LOCAL (règles + alias)"
    print(f"Mode : {mode} · données : {source}\n")
    journal = Journal()
    reussis = 0
    for pid, message, sym, part, arret in CAS:
        mandat = profil.construire_mandat(pid, journal=journal)
        try:
            r = profil.extraire(message, mandat["profil"], univers, journal)
        except Exception as e:                                        # noqa: BLE001
            print(f"❌ ERREUR {type(e).__name__}: {e}\n   « {message} »")
            continue
        obtenu_arret = bool(r["informations_manquantes"])
        ok = obtenu_arret == arret and (arret or (r["symbole"] == sym and abs((r["part"] or 0) - part) < 1e-9))
        if not ok and "Elon Musk" in message and not bedrock_client.actif():
            etat = "➖ attendu en local (périphrase : seul le LLM la comprend)"
            ok = True
        else:
            etat = "✅" if ok else "❌"
        reussis += ok
        res = r["question"] if obtenu_arret else f"{r['symbole']} · {pct(r['part'])}"
        print(f"{etat} [{pid}] « {message} »\n   → {res}\n   méthode : {r['methode']} · trace {r['trace']}")
    print(f"\n{reussis}/{len(CAS)} cas conformes · {len(journal.traces)} traces dans traces_locales/{journal.session}.jsonl")
    return reussis == len(CAS)


def diagnostiquer():
    """Un appel minimal par modèle configuré, avec le message d'erreur AWS complet (aucun secret dedans)."""
    for cle in ("rapide", "redaction"):
        var = "BEDROCK_MODELE_RAPIDE" if cle == "rapide" else "BEDROCK_MODELE_REDACTION"
        print(f"\n{var} = {os.getenv(var)}")
        try:
            rep = bedrock_client.appeler('Réponds uniquement par le JSON {"ok": true}', modele=cle, max_tokens=50)
            print(f"  ✅ réponse : {rep.strip()[:200]}")
        except Exception as e:                                        # noqa: BLE001
            print(f"  ❌ {type(e).__name__} : {e}")


if args.modeles:
    lister_modeles()
elif args.diagnostic:
    if verifier_aws():
        diagnostiquer()
elif args.aws:
    sys.exit(0 if verifier_aws() else 1)
else:
    if args.bedrock and not verifier_aws():
        sys.exit("\nConfiguration AWS incomplète : corrige les lignes ci-dessus avant --bedrock.")
    sys.exit(0 if executer_cas() else 1)
