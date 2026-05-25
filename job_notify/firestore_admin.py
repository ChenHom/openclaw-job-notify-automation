"""Small Firestore REST adapter for local admin scripts."""

from __future__ import annotations

import json
import subprocess
import urllib.parse
import urllib.request
from typing import Any

from job_notify.config import JobNotifyConfig, load_config


def access_token(config: JobNotifyConfig | None = None) -> str:
    config = config or load_config()
    module = json.dumps(config.firebase_tools_auth_module)
    script = f"""
const authModule = await import({module});
const auth = authModule.default || authModule;
const account = await auth.getGlobalDefaultAccount();
if (!account?.tokens?.refresh_token) throw new Error('Firebase CLI is not logged in');
const token = await auth.getAccessToken(account.tokens.refresh_token, ['https://www.googleapis.com/auth/cloud-platform']);
console.log(token.access_token);
"""
    result = subprocess.run([config.node_binary, "--input-type=module", "-e", script], text=True, check=True, capture_output=True)
    return result.stdout.strip()


def firestore_request(path: str, *, method: str = "GET", body: dict[str, Any] | None = None, config: JobNotifyConfig | None = None) -> dict[str, Any] | None:
    config = config or load_config()
    if not config.firestore_project_id:
        raise RuntimeError("firestoreProjectId is required for Firestore access")
    token = access_token(config)
    url = f"https://firestore.googleapis.com/v1/projects/{config.firestore_project_id}/databases/{urllib.parse.quote(config.firestore_database, safe='')}/documents{path}"
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(
        url,
        method=method,
        data=data,
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(req, timeout=45) as res:
            raw = res.read().decode("utf-8", "replace")
            return json.loads(raw) if raw else None
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode("utf-8", "replace")
        raise RuntimeError(f"Firestore {method} {path} failed: {exc.code} {detail}") from exc


def firestore_value(value: Any) -> dict[str, Any]:
    if value is None:
        return {"nullValue": None}
    if isinstance(value, bool):
        return {"booleanValue": value}
    if isinstance(value, int):
        return {"integerValue": str(value)}
    if isinstance(value, float):
        return {"doubleValue": value}
    if isinstance(value, str):
        return {"stringValue": value}
    if isinstance(value, list):
        return {"arrayValue": {"values": [firestore_value(item) for item in value]}}
    if isinstance(value, dict):
        return {"mapValue": {"fields": to_fields(value)}}
    return {"stringValue": str(value)}


def to_fields(data: dict[str, Any]) -> dict[str, Any]:
    return {key: firestore_value(value) for key, value in data.items()}


def from_value(value: dict[str, Any]) -> Any:
    if "stringValue" in value:
        return value["stringValue"]
    if "timestampValue" in value:
        return value["timestampValue"]
    if "booleanValue" in value:
        return value["booleanValue"]
    if "integerValue" in value:
        return int(value["integerValue"])
    if "doubleValue" in value:
        return float(value["doubleValue"])
    if "arrayValue" in value:
        return [from_value(item) for item in value.get("arrayValue", {}).get("values", [])]
    if "mapValue" in value:
        return from_fields(value.get("mapValue", {}).get("fields", {}))
    return None


def from_fields(fields: dict[str, Any]) -> dict[str, Any]:
    return {key: from_value(value) for key, value in (fields or {}).items()}


def run_query(structured_query: dict[str, Any], config: JobNotifyConfig | None = None) -> list[dict[str, Any]]:
    result = firestore_request(":runQuery", method="POST", body={"structuredQuery": structured_query}, config=config) or []
    docs = []
    for row in result:
        document = row.get("document")
        if not document:
            continue
        docs.append({"id": document["name"].split("/")[-1], **from_fields(document.get("fields", {}))})
    return docs


def list_feedback(config: JobNotifyConfig | None = None) -> list[dict[str, Any]]:
    return run_query({"from": [{"collectionId": "jobs", "allDescendants": True}], "limit": 1000}, config=config)


def write_document(collection: str, doc_id: str, data: dict[str, Any], config: JobNotifyConfig | None = None) -> None:
    firestore_request(f"/{collection}/{urllib.parse.quote(doc_id, safe='')}", method="PATCH", body={"fields": to_fields(data)}, config=config)


def write_document_path(path: str, data: dict[str, Any], config: JobNotifyConfig | None = None) -> None:
    safe_path = "/" + "/".join(urllib.parse.quote(part, safe="") for part in path.strip("/").split("/"))
    firestore_request(safe_path, method="PATCH", body={"fields": to_fields(data)}, config=config)


class FirestoreFeedbackStore:
    """FeedbackStore adapter backed by Firestore REST."""

    def __init__(self, config: JobNotifyConfig | None = None):
        self.config = config or load_config()

    def list_feedback(self) -> list[dict[str, Any]]:
        return list_feedback(config=self.config)

    def write_document(self, collection: str, doc_id: str, data: dict[str, Any]) -> None:
        write_document(collection, doc_id, data, config=self.config)


class FirestoreApplicationStore:
    """Application request adapter backed by Firestore REST."""

    def __init__(self, config: JobNotifyConfig | None = None):
        self.config = config or load_config()

    def list_requested(self, limit: int = 5) -> list[dict[str, Any]]:
        return run_query(
            {
                "from": [{"collectionId": "requests", "allDescendants": True}],
                "where": {
                    "fieldFilter": {
                        "field": {"fieldPath": "status"},
                        "op": "EQUAL",
                        "value": {"stringValue": "requested"},
                    }
                },
                "limit": limit,
            },
            config=self.config,
        )

    def update_status(self, request: dict[str, Any], status: str, extra: dict[str, Any] | None = None) -> None:
        uid = request["uid"]
        request_id = request["applicationId"]
        payload = {"status": status, **(extra or {})}
        write_document_path(f"jobApplications/{uid}/requests/{request_id}", payload, config=self.config)


class FixtureFeedbackStore:
    """FeedbackStore adapter for local tests and examples."""

    def __init__(self, feedback: list[dict[str, Any]] | None = None):
        self.feedback = feedback or []
        self.writes: list[tuple[str, str, dict[str, Any]]] = []

    def list_feedback(self) -> list[dict[str, Any]]:
        return list(self.feedback)

    def write_document(self, collection: str, doc_id: str, data: dict[str, Any]) -> None:
        self.writes.append((collection, doc_id, data))


class FixtureApplicationStore:
    """Application request store for tests and dry local workflows."""

    def __init__(self, requests: list[dict[str, Any]] | None = None):
        self.requests = requests or []
        self.status_updates: list[tuple[str, str, dict[str, Any]]] = []

    def list_requested(self, limit: int = 5) -> list[dict[str, Any]]:
        return [item for item in self.requests if item.get("status") == "requested"][:limit]

    def update_status(self, request: dict[str, Any], status: str, extra: dict[str, Any] | None = None) -> None:
        self.status_updates.append((request["applicationId"], status, extra or {}))
        request["status"] = status
        request.update(extra or {})
