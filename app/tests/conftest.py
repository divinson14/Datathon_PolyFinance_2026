import os
import sys
from pathlib import Path

os.environ.setdefault("MODE", "local")
os.environ.setdefault("DONNEES", "demo")      # les tests tournent sans data/processed ni AWS
os.environ.setdefault("TRACES", "local")
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
