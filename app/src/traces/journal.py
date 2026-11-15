"""Journal d'audit : chaque appel d'outil et chaque verdict y laisse une trace avec un ID.
local = fichier JSONL dans app/traces_locales/ ; dynamodb = table DynamoDB."""
import json
import os
import uuid
import pathlib
from datetime import datetime, timezone

from src.config import APP, TRACES


class Journal:
    def __init__(self):
        self.session = uuid.uuid4().hex[:8]
        self.traces: list[dict] = []
        self._table = None
        print(f"DEBUG INIT -> TRACES env: {os.getenv('TRACES')} | Table: {os.getenv('DYNAMODB_TABLE')}")
        if TRACES == "dynamodb":
            import boto3
            self._table = boto3.resource("dynamodb", region_name=os.getenv("AWS_REGION", "us-east-1")).Table(
                os.getenv("DYNAMODB_TABLE", "alphaforge-traces"))
            print(f"DEBUG -> Table DynamoDB initialisée avec succès : {self._table}")
        else:
            print("DEBUG -> Mode LOCAL activé (pas de DynamoDB)")
    
            
    def log(self, **trace) -> str:
        tid = f"T-{len(self.traces) + 1:02d}"
        trace = {"id": tid, "session": self.session, "horodatage": datetime.now(timezone.utc).isoformat(), **trace}
        self.traces.append(trace)
        
        if self._table is not None:
            try:
                item_propre = {
                    "session": str(self.session), 
                    "id": str(tid), 
                    **{str(k): str(v) for k, v in trace.items() if k not in ("session", "id")}
                }
                self._table.put_item(Item=item_propre)
                print(f"SUCCÈS DYNAMODB : Élément {tid} inséré avec succès.")
            except Exception as e:
                print(f"ERREUR DYNAMODB : Échec de l'insertion -> {str(e)}")
        else:
            base_path = pathlib.Path("/tmp") if os.getenv("AWS_LAMBDA_FUNCTION_NAME") else APP
            dossier = base_path / "traces_locales"
            dossier.mkdir(exist_ok=True)
            with open(dossier / f"{self.session}.jsonl", "a", encoding="utf-8") as f:
                f.write(json.dumps(trace, ensure_ascii=False) + "\n")
        return tid

    def trouver(self, tid: str) -> dict | None:
        return next((t for t in self.traces if t["id"] == tid), None)
