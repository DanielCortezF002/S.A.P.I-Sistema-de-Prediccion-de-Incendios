"""Build the inactive manual preview workflow from the tested pure policy."""

import json
from pathlib import Path

HERE = Path(__file__).resolve().parent


def build() -> dict:
    policy = (HERE / "policy.js").read_text(encoding="utf-8")
    nodes = []

    def node(name, kind, version, parameters, **extra):
        nodes.append(
            dict(
                id=f"sapi-preview-{len(nodes)}",
                name=name,
                type=f"n8n-nodes-base.{kind}",
                typeVersion=version,
                position=[len(nodes) * 240, 0],
                parameters=parameters,
                **extra,
            )
        )

    node("Manual pilot only", "manualTrigger", 1, {})
    node(
        "Read bridge",
        "httpRequest",
        4.5,
        {
            "url": "http://host.docker.internal:8600/score",
            "options": {
                "timeout": 30000,
                "response": {
                    "response": {
                        "fullResponse": True,
                        "neverError": True,
                        "responseFormat": "text",
                    }
                },
            },
        },
        onError="continueRegularOutput",
        retryOnFail=False,
    )
    node(
        "Policy",
        "code",
        2,
        {
            "jsCode": policy + "\nreturn [{json: evaluate($input.first().json, "
            "new Date().toISOString(), $execution.id)}];"
        },
    )
    node(
        "Ensure preview ledger",
        "dataTable",
        1.1,
        {
            "resource": "table",
            "operation": "create",
            "tableName": "sapi_controlled_preview_v1",
            "columns": {"column": [{"name": "record", "type": "string"}]},
            "options": {"createIfNotExists": True},
        },
    )
    table = {
        "__rl": True,
        "value": "={{ $('Ensure preview ledger').first().json.id }}",
        "mode": "id",
    }
    node(
        "Previous condition",
        "dataTable",
        1.1,
        {
            "operation": "get",
            "dataTableId": table,
            "limit": 1,
            "orderBy": True,
            "orderByColumn": "id",
            "orderByDirection": "DESC",
        },
        alwaysOutputData=True,
    )
    node(
        "Dedupe",
        "code",
        2,
        {
            "jsCode": policy + "\nconst row = $input.first().json;\n"
            "const previous = row.record ? JSON.parse(row.record) : null;\n"
            "return [{json: deduplicate($('Policy').first().json, previous)}];"
        },
    )
    node(
        "Persist preview",
        "dataTable",
        1.1,
        {
            "operation": "insert",
            "dataTableId": table,
            "columns": {
                "mappingMode": "defineBelow",
                "value": {"record": "={{ JSON.stringify($json) }}"},
            },
            "options": {},
        },
    )
    node(
        "Preview only - NO DELIVERY",
        "code",
        2,
        {
            "jsCode": "return [{json: {...JSON.parse($input.first().json.record), "
            "delivery: 'NOT_SENT'}}];"
        },
    )
    return {
        "id": "SapiControlledPreviewV1",
        "name": "SAPI - Controlled preview (NO DELIVERY)",
        "active": False,
        "nodes": nodes,
        "connections": {
            a["name"]: {"main": [[{"node": b["name"], "type": "main", "index": 0}]]}
            for a, b in zip(nodes, nodes[1:])
        },
        "settings": {
            "executionOrder": "v1",
            "timezone": "America/Santiago",
            "saveDataSuccessExecution": "all",
            "saveDataErrorExecution": "all",
        },
    }


if __name__ == "__main__":
    (HERE / "controlled-preview.json").write_text(
        json.dumps(build(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
