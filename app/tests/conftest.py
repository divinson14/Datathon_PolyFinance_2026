import os
import sys
from pathlib import Path

os.environ.setdefault("MODE", "local")
os.environ.setdefault("DONNEES", "local")     # données réelles si data/processed existe, sinon démo fictive (repli auto)
os.environ.setdefault("TRACES", "local")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
