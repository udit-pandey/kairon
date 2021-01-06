import json
import time
from fastapi.testclient import TestClient
import pytest
from kairon.history_server.service import app
from kairon.history_server.history import HistoryServerUtils
from mongomock import MongoClient
from pymongo import MongoClient as pymongo_client

client = TestClient(app)


def load_env_valid_token(*args, **kwargs):
    return {
        'tracker_endpoint': {'token': 'b9d01861392757c66daaf1f214268e2739a5baac935071d06e2ea71a66dc5bcd'}}


def load_env_token_none(*args, **kwargs):
    return {
        'tracker_endpoint': {'token': None}}


@pytest.fixture
def mock_env_var_token(monkeypatch):
    monkeypatch.setattr(HistoryServerUtils, "load_environment", load_env_valid_token)


@pytest.fixture
def mock_history_server_env_var_none(monkeypatch):
    monkeypatch.setattr(
        HistoryServerUtils, "load_environment", load_env_token_none)


def endpoint_details(*args, **kwargs):
    return {"tracker_endpoint": {"url": "http://192.168.100.101", "type": "rest", "db": "conversation"}}


def invalid_endpoint_details(*args, **kwargs):
    return {"tracker_endpoint": {"url": "192.168.100.101", "type": "rest", "db": "conversation"}}


@pytest.fixture
def mock_db_client(monkeypatch):
    def db_client(*args, **kwargs):
        return MongoClient(), "conversation", "conversations"

    monkeypatch.setattr(HistoryServerUtils, "get_mongo_connection", db_client)


@pytest.fixture
def mock_invalid_db_client(monkeypatch):
    def db_client(*args, **kwargs):
        return pymongo_client(host="192.168.100.101"), "conversation", "conversations"

    monkeypatch.setattr(HistoryServerUtils, "get_mongo_connection", db_client)


def history_conversations(*args, **kwargs):
    json_data = json.load(
        open("tests/testing_data/history/conversations_history.json")
    )
    json_data[0]['events'][0]['timestamp'] = time.time()
    json_data[1]['events'][0]['timestamp'] = time.time()
    return json_data


@pytest.fixture
def mock_mongo_client(monkeypatch):
    def db_client(*args, **kwargs):
        client = MongoClient()
        db = client.get_database("conversation")
        conversations = db.get_collection("conversations")
        conversations.insert_many(history_conversations())
        return client, "conversation", "conversations"

    monkeypatch.setattr(HistoryServerUtils, "get_mongo_connection", db_client)


def events(*args, **kwargs):
    json_data = json.load(open("tests/testing_data/history/conversation.json"))
    for i, event in enumerate(json_data[0]['events']):
        json_data[0]['events'][i]['timestamp'] = time.time()

    return json_data[0]


@pytest.fixture
def mock_events(monkeypatch):
    def db_client(*args, **kwargs):
        client = MongoClient()
        db = client.get_database("conversation")
        conversations = db.get_collection("conversations")
        conversations.insert_one(events())
        return client, "conversation", "conversations"

    monkeypatch.setattr(HistoryServerUtils, "get_mongo_connection", db_client)


def test_chat_history_users_connection_error(mock_invalid_db_client, mock_env_var_token):
    token = load_env_valid_token()
    response = client.get(
        url="/users",
        headers={"Authorization": 'bearer ' + token['tracker_endpoint']['token']}
    )

    actual = response.json()
    assert actual["error_code"] == 422
    assert actual["data"] is None
    assert actual["message"]
    assert not actual["success"]


def test_chat_history_users_connection_error_2(mock_invalid_db_client, mock_env_var_token):
    token = load_env_valid_token()
    response = client.get(
        "/users",
        json={"month": 2},
        headers={"Authorization": 'bearer ' + token['tracker_endpoint']['token']}
    )

    actual = response.json()
    assert actual["error_code"] == 422
    assert actual["data"] is None
    assert actual["message"]
    assert not actual["success"]


def test_chat_history_users(mock_mongo_client, mock_env_var_token):
    token = load_env_valid_token()
    response = client.get(
        url="/users",
        headers={"Authorization": 'bearer ' + token['tracker_endpoint']['token']}
    )

    actual = response.json()
    assert actual["error_code"] == 0
    assert len(actual["data"]["users"]) == 2
    assert actual["message"] is None
    assert actual["success"]


def test_chat_history(mock_events, mock_env_var_token):
    token = load_env_valid_token()
    response = client.get(
        url="/users/5b029887-bed2-4bbb-aa25-bd12fda26244",
        headers={"Authorization": 'bearer ' + token['tracker_endpoint']['token']}
    )

    actual = response.json()
    assert actual["error_code"] == 0
    assert len(actual["data"]["history"]) == 25
    assert actual["message"] is None
    assert actual["success"]


def test_visitor_hit_fallback(mock_mongo_client, mock_env_var_token):
    token = load_env_valid_token()
    response = client.get(
        url="/metrics/fallback",
        headers={"Authorization": 'bearer ' + token['tracker_endpoint']['token']}
    )

    actual = response.json()
    assert actual["error_code"] == 0
    assert actual["data"]["fallback_count"] == 0
    assert actual["data"]["total_count"] == 0
    assert actual["message"] is None
    assert actual["success"]


def test_conversation_steps(mock_mongo_client, mock_env_var_token):
    token = load_env_valid_token()
    response = client.get(
        url="/metrics/conversation/steps",
        headers={"Authorization": 'bearer ' + token['tracker_endpoint']['token']}
    )

    actual = response.json()
    assert actual["error_code"] == 0
    assert len(actual["data"]["conversation_steps"]) == 0
    assert actual["message"] is None
    assert actual["success"]


def test_conversation_time(mock_mongo_client, mock_env_var_token):
    token = load_env_valid_token()
    response = client.get(
        url="/metrics/conversation/time",
        headers={"Authorization": 'bearer ' + token['tracker_endpoint']['token']}
    )

    actual = response.json()
    assert actual["error_code"] == 0
    assert len(actual["data"]["conversation_time"]) == 0
    assert actual["message"] is None
    assert actual["success"]


def test_user_with_metrics(mock_mongo_client, mock_env_var_token):
    token = load_env_valid_token()
    response = client.get(
        url="/metrics/users",
        headers={"Authorization": 'bearer ' + token['tracker_endpoint']['token']}
    )

    actual = response.json()
    assert actual["error_code"] == 0
    assert actual["data"]["users"] == []
    assert actual["message"] is None
    assert actual["success"]


def test_invalid_auth_token(mock_mongo_client, mock_env_var_token):
    header = {"Authorization": "bearer bdhfjsdhf"}
    response = client.get(
        url="/metrics/users",
        headers=header
    )

    actual = response.json()
    assert actual["error_code"] == 422
    assert actual["data"] is None
    assert actual["message"] == "Invalid auth token"
    assert not actual["success"]


def test_no_token_1(mock_mongo_client, mock_env_var_token):
    header = {"Authorization": None}
    response = client.get(
        url="/metrics/users",
        headers=header
    )

    actual = response.json()
    assert actual["error_code"] == 422
    assert actual["data"] is None
    assert actual["message"] == "Invalid auth token"
    assert not actual["success"]


def test_no_token_2(mock_mongo_client, mock_history_server_env_var_none):
    header = {"Authorization": None}
    response = client.get(
        url="/metrics/users",
        headers=header
    )

    actual = response.json()
    assert actual["error_code"] == 0
    assert actual["data"]["users"] == []
    assert actual["message"] is None
    assert actual["success"]
