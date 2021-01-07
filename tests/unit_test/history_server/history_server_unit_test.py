import json

import pytest
from mongoengine import connect
from rasa.shared.core.domain import Domain
from rasa.core.tracker_store import MongoTrackerStore
import time
from kairon.history_server.exceptions import HistoryServerException
from kairon.history_server.history import HistoryServer, HistoryServerUtils
from kairon.history_server.models import HistoryMonthEnum
from kairon.utils import Utility
import os
from mongomock import MongoClient
from pymongo import MongoClient as pymongo_client


class TestHistoryServer:

    @pytest.fixture(autouse=True)
    def init_connection(self):
        os.environ["system_file"] = "tests/testing_data/system.yaml"
        Utility.load_evironment()
        connect(host=Utility.environment['database']["url"])

    def history_conversations(self, *args, **kwargs):
        json_data = json.load(
            open("tests/testing_data/history/conversations_history.json")
        )
        json_data[0]['events'][0]['timestamp'] = time.time()
        json_data[1]['events'][0]['timestamp'] = time.time()
        return json_data

    def get_mongo_tracker(self, *args, **kwargs):
        domain = Domain.from_file("tests/testing_data/initial/domain.yml")
        return MongoTrackerStore(domain, host="mongodb://192.168.100.140:27019")

    @pytest.fixture
    def mock_get_tracker_and_domain(self, monkeypatch):
        monkeypatch.setattr(
            HistoryServerUtils, "get_mongo_tracker_store", self.get_mongo_tracker
        )

    @pytest.fixture
    def mock_mongo_client(self, monkeypatch):
        def db_client(*args, **kwargs):
            client = MongoClient()
            db = client.get_database("conversation")
            conversations = db.get_collection("conversations")
            history = self.history_conversations()
            conversations.insert_many(history)
            return client, "conversation", "conversations"

        monkeypatch.setattr(HistoryServerUtils, "get_mongo_connection", db_client)

    @pytest.fixture
    def mock_invalid_mongo_client(self, monkeypatch):
        def db_client(*args, **kwargs):
            client = pymongo_client(host="mongodb://demo:27019")
            return client, "conversation", "conversations"

        monkeypatch.setattr(HistoryServerUtils, "get_mongo_connection", db_client)

    @pytest.fixture
    def mock_mongo_client_empty(self, monkeypatch):
        def client(*args, **kwargs):
            client = MongoClient()
            return client, "conversation", "conversations"

        monkeypatch.setattr(HistoryServerUtils, "get_mongo_connection", client)

    def endpoint_details(self, *args, **kwargs):
        return {"tracker_endpoint": {"url": "mongomock://localhost/test", "type": "mongo", "db": "conversation",
                                     "collection": "conversations"}}

    def events(self, *args, **kwargs):
        json_data = json.load(open("tests/testing_data/history/conversation.json"))
        for i, event in enumerate(json_data[0]['events']):
            json_data[0]['events'][i]['timestamp'] = time.time()

        return json_data[0]

    @pytest.fixture
    def mock_events(self, monkeypatch):
        def db_client(*args, **kwargs):
            client = MongoClient()
            db = client.get_database("conversation")
            conversations = db.get_collection("conversations")
            conversations.insert_one(self.events())
            return client, "conversation", "conversations"

        monkeypatch.setattr(HistoryServerUtils, "get_mongo_connection", db_client)

    def test_fetch_chat_users_db_error(self, mock_invalid_mongo_client):
        with pytest.raises(HistoryServerException):
            HistoryServer.fetch_chat_users()

    def test_fetch_chat_users(self, mock_mongo_client):
        users = HistoryServer.fetch_chat_users()
        assert len(users) == 2

    def test_fetch_chat_users_empty(self, mock_mongo_client_empty):
        users = HistoryServer.fetch_chat_users()
        assert len(users) == 0

    def test_fetch_chat_users_no_endpoint(self):
        with pytest.raises(HistoryServerException):
            HistoryServer.fetch_chat_users(HistoryMonthEnum.One, False, None)

    def test_fetch_chat_users_error(self, mock_invalid_mongo_client):
        with pytest.raises(HistoryServerException):
            users = HistoryServer.fetch_chat_users()
            assert users == 0

    def test_fetch_chat_history_error(self, mock_invalid_mongo_client):
        with pytest.raises(HistoryServerException):
            HistoryServer.fetch_chat_history(sender="123")

    def test_fetch_chat_history_empty(self, mock_mongo_client_empty):
        history = HistoryServer.fetch_chat_history(sender="123")
        assert len(history) == 0

    def test_fetch_chat_history(self, mock_events):
        history = HistoryServer.fetch_chat_history(
            sender='5b029887-bed2-4bbb-aa25-bd12fda26244'
        )
        assert len(history) == 25
        assert history[0]["event"]
        assert history[0]["timestamp"]

    def test_fetch_chat_history_no_endpoint(self):
        with pytest.raises(HistoryServerException):
            HistoryServer.fetch_chat_history(
                sender="5e564fbcdcf0d5fad89e3acd", month=HistoryMonthEnum.One, load_rest_tracker=False, endpoint=None
            )

    def test_fetch_chat_history_no_sender(self):
        with pytest.raises(HistoryServerException):
            HistoryServer.fetch_chat_history(
                sender="", month=HistoryMonthEnum.One, load_rest_tracker=False, endpoint=None
            )

    def test_visitor_hit_fallback_error(self, mock_invalid_mongo_client):
        with pytest.raises(HistoryServerException):
            HistoryServer.visitor_hit_fallback()

    def test_visitor_hit_fallback(self, mock_mongo_client):
        fallback_count, total_count = HistoryServer.visitor_hit_fallback()
        assert fallback_count == 0
        assert total_count == 0

    def test_visitor_hit_fallback_no_endpoint(self):
        with pytest.raises(HistoryServerException):
            HistoryServer.visitor_hit_fallback(HistoryMonthEnum.One, False, None)

    def test_conversation_time_error(self, mock_invalid_mongo_client):
        with pytest.raises(HistoryServerException):
            HistoryServer.conversation_time()

    def test_conversation_time_empty(self, mock_mongo_client_empty):
        conversation_time = HistoryServer.conversation_time()
        assert not conversation_time

    def test_conversation_time_empty_no_endpoint(self):
        with pytest.raises(HistoryServerException):
            HistoryServer.conversation_time(HistoryMonthEnum.One, False, None)

    def test_conversation_time(self, mock_mongo_client):
        conversation_time = HistoryServer.conversation_time()
        assert conversation_time == []

    def test_conversation_steps_error(self, mock_invalid_mongo_client):
        with pytest.raises(HistoryServerException):
            HistoryServer.conversation_steps()

    def test_conversation_steps_empty(self, mock_mongo_client_empty):
        conversation_steps = HistoryServer.conversation_steps()
        assert not conversation_steps

    def test_conversation_steps(self, mock_mongo_client):
        conversation_steps = HistoryServer.conversation_steps()
        assert conversation_steps == []

    def test_conversation_steps_no_endpoint(self):
        with pytest.raises(HistoryServerException):
            HistoryServer.conversation_steps(HistoryMonthEnum.One, False, None)

    def test_user_with_metrics(self, mock_mongo_client):
        users = HistoryServer.user_with_metrics()
        assert users == []

    def test_user_with_metrics_no_endpoint(self):
        with pytest.raises(HistoryServerException):
            HistoryServer.user_with_metrics(HistoryMonthEnum.One, False, None)
