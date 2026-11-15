import os
import sys
from pathlib import Path

os.environ.setdefault("MODE", "local")
os.environ.setdefault("DONNEES", "local")     # données réelles si data/processed existe, sinon démo fictive (repli auto)
os.environ.setdefault("TRACES", "local")
# Aucun test n'appelle le vrai Bedrock Guardrails : les tests qui en ont besoin définissent un faux client.
os.environ["BEDROCK_GUARDRAIL_ID"] = ""
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
