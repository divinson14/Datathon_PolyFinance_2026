"""Lance les scénarios piégés et produit le tableau pour la documentation.
Depuis app/ :  python tests/lancer_scenarios.py"""
import os
import sys
from pathlib import Path

os.environ.setdefault("MODE", "local")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import yaml
from src.orchestrateur import executer

scenarios = yaml.safe_load((Path(__file__).parent / "scenarios_pieges.yaml").read_text(encoding="utf-8"))
lignes = ["| Scénario | Attendu | Obtenu | Résultat |", "|---|---|---|---|"]
reussis = 0
for s in scenarios:
    r = executer(s.get("persona"), s["message"], profil_saisi=s.get("profil_saisi"))
    a = s["attendu"]
    ok = r["arret"] == a["arret"]
    obtenu = "arrêt : " + r["etapes"][-1]["agent"] if r["arret"] else f"{len(r['verdicts']['violees'])} règle(s) violée(s)"
    if not r["arret"]:
        ok &= len(r["verdicts"]["violees"]) >= a.get("regles_violees_min", 0)
        if "alternative" in a:
            ok &= (r["alternative"] is not None) == a["alternative"]
            obtenu += ", alternative " + ("trouvée" if r["alternative"] else "absente")
    reussis += ok
    lignes.append(f"| {s['nom']} | {a} | {obtenu} | {'✅' if ok else '❌'} |")
lignes.append(f"\n**{reussis}/{len(scenarios)} scénarios conformes.**")
print("\n".join(lignes))
sys.exit(0 if reussis == len(scenarios) else 1)
