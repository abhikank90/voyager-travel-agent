import os
import json
import hashlib
import boto3
from botocore.exceptions import ClientError

from .base_agent import BaseAgent


class PersonalisationAgent(BaseAgent):
    """Loads and saves user profiles from DynamoDB (falls back to local JSON in dev)."""

    name = "personalisation"
    description = "Retrieves and persists user travel preferences from DynamoDB"

    TABLE_NAME = os.getenv("DYNAMODB_TABLE", "voyager-user-profiles")
    LOCAL_STORE = "/tmp/voyager_profiles.json"

    def _setup(self):
        self._use_dynamo = bool(os.getenv("AWS_ACCESS_KEY_ID"))
        if self._use_dynamo:
            self._dynamo = boto3.resource("dynamodb", region_name=os.getenv("AWS_REGION", "us-east-1"))
            self._table = self._dynamo.Table(self.TABLE_NAME)

    async def _execute(self, state: dict) -> dict:
        user_id = state.get("user_id", "anonymous")
        profile = await self._load_profile(user_id)

        intent = state.get("intent", {})
        if profile:
            if not intent.get("origin") and profile.get("home_city"):
                intent["origin"] = profile["home_city"]
            if not intent.get("group_size") and profile.get("usual_group_size"):
                intent["group_size"] = profile["usual_group_size"]

        return {
            "user_profile": profile,
            "intent": intent,
        }

    async def _load_profile(self, user_id: str) -> dict:
        if self._use_dynamo:
            try:
                resp = self._table.get_item(Key={"user_id": user_id})
                return resp.get("Item", {})
            except ClientError:
                return {}
        return self._load_local(user_id)

    def _load_local(self, user_id: str) -> dict:
        try:
            with open(self.LOCAL_STORE) as f:
                store = json.load(f)
            return store.get(user_id, {})
        except FileNotFoundError:
            return {}

    async def save_profile(self, user_id: str, profile: dict):
        if self._use_dynamo:
            self._table.put_item(Item={"user_id": user_id, **profile})
        else:
            try:
                with open(self.LOCAL_STORE) as f:
                    store = json.load(f)
            except FileNotFoundError:
                store = {}
            store[user_id] = profile
            with open(self.LOCAL_STORE, "w") as f:
                json.dump(store, f, indent=2)
