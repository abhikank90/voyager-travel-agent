"""Unit tests for PersonalisationAgent's DynamoDB fallback behaviour.

No AWS calls: the DynamoDB table is replaced with a stub that raises.
"""

import asyncio
import json

from botocore.exceptions import ClientError, EndpointConnectionError

from agents.personalisation import PersonalisationAgent


class _RaisingTable:
    def __init__(self, exc):
        self._exc = exc

    def get_item(self, **_kwargs):
        raise self._exc


def _agent_with_table(monkeypatch, tmp_path, exc):
    store = tmp_path / "profiles.json"
    store.write_text(json.dumps({"u1": {"home_city": "Los Angeles"}}))
    monkeypatch.setattr(PersonalisationAgent, "LOCAL_STORE", str(store))
    monkeypatch.delenv("AWS_ACCESS_KEY_ID", raising=False)
    agent = PersonalisationAgent()
    agent._use_dynamo = True
    agent._table = _RaisingTable(exc)
    return agent


def test_falls_back_to_local_store_when_endpoint_unreachable(monkeypatch, tmp_path):
    exc = EndpointConnectionError(endpoint_url="http://localhost:4566/")
    agent = _agent_with_table(monkeypatch, tmp_path, exc)
    profile = asyncio.run(agent._load_profile("u1"))
    assert profile == {"home_city": "Los Angeles"}


def test_falls_back_to_local_store_on_client_error(monkeypatch, tmp_path):
    exc = ClientError({"Error": {"Code": "ResourceNotFoundException", "Message": "x"}}, "GetItem")
    agent = _agent_with_table(monkeypatch, tmp_path, exc)
    profile = asyncio.run(agent._load_profile("u1"))
    assert profile == {"home_city": "Los Angeles"}


def test_run_does_not_error_when_dynamo_unreachable(monkeypatch, tmp_path):
    exc = EndpointConnectionError(endpoint_url="http://localhost:4566/")
    agent = _agent_with_table(monkeypatch, tmp_path, exc)
    result = asyncio.run(agent._execute({"user_id": "u1", "intent": {}}))
    assert result["user_profile"] == {"home_city": "Los Angeles"}
    assert result["intent"]["origin"] == "Los Angeles"
