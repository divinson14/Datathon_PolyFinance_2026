"""Essai manuel de la chaîne Profil → Analyste → Gouvernance sur un message au choix. Depuis app/ :

    python tests/essai_gouvernance.py                                          # Robert, Microsoft 15 %
    python tests/essai_gouvernance.py amira "Je pense mettre 20 % dans Nvidia."
    MODE=local python tests/essai_gouvernance.py mateo "Et si je mettais 15 % dans Shopify ?"   # sans AWS

Le mode (local / bedrock) vient de app/.env, sauf s'il est forcé devant la commande.
Pas collecté par pytest (le nom ne commence pas par test_).
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")       # accents et émojis dans le terminal Windows

from src import config  # noqa: E402
from src.orchestrateur import executer  # noqa: E402

persona = sys.argv[1] if len(sys.argv) > 1 else "robert"
message = sys.argv[2] if len(sys.argv) > 2 else "Je pense mettre 15 % dans Microsoft."
print(f"MODE={config.MODE} · ANALYSTE={config.ANALYSTE} · persona={persona}\nMessage : « {message} »\n")

r = executer(persona, message)
for e in r["etapes"]:
    if e["agent"].startswith(("Agent Explicabilité", "Vérificateur")):
        continue                                   # on s'arrête à la Gouvernance
    print(f"[{e['statut']:>4}] {e['agent']} — {e['texte']}")
    for ligne in e.get("mandat", []):
        print(f"         {ligne[0]} : {ligne[1]}")
    for calcul in e.get("calculs", []):
        print(f"         {calcul[0]} : {calcul[1]}  ({calcul[2]})")
    for regle in e.get("regles", []):
        print(f"         {'✅' if regle['ok'] else '❌'} {regle['regle']} : {regle['valeur']} (limite {regle['limite']})")
    if e.get("resume"):
        print(f"         Résumé : {e['resume']}")
    if e.get("consigne"):
        print(f"         Consigne → Analyste : {e['consigne']}")
    for tension in e.get("tensions") or []:
        print(f"         ⚖️  {tension}")
    if e.get("note"):
        print(f"         Note : {e['note'][:300]}")

if not r["arret"]:
    v = r["verdicts"]
    print(f"\n=> Statut (calculé par le code) : {v['statut']} · rédaction : {v['redaction']}")
    print(f"=> Alternative : {r['alternative']['part'] if r['alternative'] else 'aucune'}")
    replis = [t["sortie"] for t in r["journal"].traces if t["titre"].startswith("Repli")]
    print(f"=> Replis : {replis or 'aucun'}")
