"""Journal d'audit : chaque appel d'outil et chaque verdict y laisse une trace avec un ID.

TRACES=local    → fichier JSONL dans app/traces_locales/ (ou /tmp/traces_locales sur AWS Lambda) ;
TRACES=dynamodb → table DynamoDB (DYNAMODB_TABLE, clé de partition « session », clé de tri « id »).
Si l'écriture DynamoDB échoue (droits, réseau, identifiants expirés), la trace n'est jamais perdue :
elle est écrite dans le fichier local, et l'échec est signalé dans les logs. L'analyse continue.
"""
import json
import logging
import os
import pathlib
import uuid
from datetime import datetime, timezone

from src.config import APP, TRACES

log = logging.getLogger(__name__)


class Journal:
    def __init__(self):
        self.session = uuid.uuid4().hex[:8]
        self.traces: list[dict] = []
        self._table = None
        self.dynamodb_ok = None                     # None : non utilisé · True : écrit · False : repli local
        if TRACES == "dynamodb":
            try:
                import boto3
                self._table = boto3.resource("dynamodb", region_name=os.getenv("AWS_REGION", "us-east-1")).Table(
                    os.getenv("DYNAMODB_TABLE", "alphaforge-traces"))
            except Exception as e:                  # boto3 absent ou configuration invalide : repli local
                log.warning("DynamoDB indisponible (%s) : traces écrites en local", e)

    def log(self, **trace) -> str:
        tid = f"T-{len(self.traces) + 1:02d}"
        trace = {"id": tid, "session": self.session, "horodatage": datetime.now(timezone.utc).isoformat(), **trace}
        self.traces.append(trace)
        if self._table is not None:
            try:
                self._table.put_item(Item={"session": self.session, "id": tid,
                                           **{str(k): str(v) for k, v in trace.items() if k not in ("session", "id")}})
                self.dynamodb_ok = self.dynamodb_ok is not False
                return tid
            except Exception as e:                  # la trace n'est jamais perdue : repli sur le fichier local
                log.warning("Écriture DynamoDB impossible pour %s/%s (%s) : trace écrite en local", self.session, tid, e)
                self.dynamodb_ok = False
        self._ecrire_local(trace)
        return tid

    def _ecrire_local(self, trace: dict) -> None:
        base = pathlib.Path("/tmp") if os.getenv("AWS_LAMBDA_FUNCTION_NAME") else APP
        dossier = base / "traces_locales"
        dossier.mkdir(exist_ok=True)
        with open(dossier / f"{self.session}.jsonl", "a", encoding="utf-8") as f:
            f.write(json.dumps(trace, ensure_ascii=False) + "\n")

    def trouver(self, tid: str) -> dict | None:
        return next((t for t in self.traces if t["id"] == tid), None)
