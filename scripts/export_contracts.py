import json
from pathlib import Path

from insureagent_api.main import app
from insureagent_domain.events import DomainEvent

root = Path(__file__).resolve().parents[1] / "contracts"
for name, content in [
    ("openapi.json", app.openapi()),
    ("events/record-stored.schema.json", DomainEvent.model_json_schema()),
]:
    path = root / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(content, ensure_ascii=False, indent=2) + "\n")
