import os

import pytest
import quart
from telebot import TeleBot

from kairon.chat_server.channels.channels import ChannelClientDictionary, KaironChannels
from kairon.chat_server.channels.telegram import KaironTelegramClient
from kairon.chat_server.chat_server_utils import ChatServerUtils
from kairon.chat_server.exceptions import ChatServerException
from kairon.chat_server.middleware import authenticate_and_get_request
from kairon.chat_server.models import CreateClientRequest
from kairon.chat_server.processor import KaironMessageProcessor


class TestChannelClientDictionary:
    clients = ChannelClientDictionary()

    @pytest.fixture
    def mock_telegram_client(self, monkeypatch):
        def _mock_telegram_client(*args, **kwargs):
            return None

        monkeypatch.setattr(KaironTelegramClient, "__init__", _mock_telegram_client)

    def test_put(self, mock_telegram_client):
        client = KaironTelegramClient("auth", "hello_bot", "http://webhook")
        TestChannelClientDictionary.clients.put("hello_bot", KaironChannels.TELEGRAM, client)

        client = KaironTelegramClient("auth", "hello_bot", "http://webhook")
        TestChannelClientDictionary.clients.put("hello_bot", KaironChannels.FACEBOOK, client)

        client = KaironTelegramClient("auth", "bye_bot", "http://webhook")
        TestChannelClientDictionary.clients.put("bye_bot", KaironChannels.TELEGRAM, client)

    def test_get(self):
        client = TestChannelClientDictionary.clients.get("hello_bot", KaironChannels.TELEGRAM)
        assert isinstance(client, KaironTelegramClient)

        client = TestChannelClientDictionary.clients.get("hello_bot", KaironChannels.FACEBOOK)
        assert isinstance(client, KaironTelegramClient)

        client = TestChannelClientDictionary.clients.get("bye_bot", KaironChannels.TELEGRAM)
        assert isinstance(client, KaironTelegramClient)

        client = TestChannelClientDictionary.clients.get("bye_bot", KaironChannels.FACEBOOK)
        assert not client

        client = TestChannelClientDictionary.clients.get("bot_non_existing", KaironChannels.FACEBOOK)
        assert not client

    def test_is_present(self):
        client = TestChannelClientDictionary.clients.is_present("hello_bot", KaironChannels.TELEGRAM)
        assert client

        client = TestChannelClientDictionary.clients.is_present("bye_bot", KaironChannels.TELEGRAM)
        assert client

        client = TestChannelClientDictionary.clients.is_present("hello_bot", KaironChannels.FACEBOOK)
        assert client

        client = TestChannelClientDictionary.clients.is_present("bye_bot", KaironChannels.FACEBOOK)
        assert not client

        client = TestChannelClientDictionary.clients.is_present("bot_non_existing", KaironChannels.FACEBOOK)
        assert not client

        with pytest.raises(ChatServerException):
            TestChannelClientDictionary.clients.is_present("bye_bot", KaironChannels.FACEBOOK, True)

        with pytest.raises(ChatServerException):
            TestChannelClientDictionary.clients.is_present("bot_non_existing", KaironChannels.FACEBOOK, True)

    def test_replace(self, mock_telegram_client):
        client = KaironTelegramClient("auth", "hello_bot", "http://webhook")
        TestChannelClientDictionary.clients.put("hello_bot", KaironChannels.TELEGRAM, client)

        client_replaced = TestChannelClientDictionary.clients.get("hello_bot", KaironChannels.TELEGRAM)
        assert isinstance(client_replaced, KaironTelegramClient)


class TestKaironTelegramClient:

    @pytest.fixture
    def mock_telegram_client(self, monkeypatch):
        def _mock_set_webhook(*args, **kwargs):
            return None

        monkeypatch.setattr(TeleBot, "set_webhook", _mock_set_webhook)

    @pytest.fixture
    def mock_model_response(self, monkeypatch):
        def _mock_model_response(*args, **kwargs):
            return "hello"

        monkeypatch.setattr(KaironMessageProcessor, "process_text_message", _mock_model_response)

    @pytest.fixture
    def mock_send_response(self, monkeypatch):
        def _mock_send_response(*args, **kwargs):
            return None

        monkeypatch.setattr(TeleBot, "send_message", _mock_send_response)

    @pytest.fixture
    def mock_send_response_exception(self, monkeypatch):
        def _mock_send_response_exception(*args, **kwargs):
            raise Exception()

        monkeypatch.setattr(TeleBot, "send_message", _mock_send_response_exception)

    @pytest.fixture
    def mock_send_voice_response(self, monkeypatch):
        def _mock_send_voice_response(*args, **kwargs):
            return None

        monkeypatch.setattr(TeleBot, "send_voice", _mock_send_voice_response)

    def test_set_webhook(self, mock_telegram_client):
        client = KaironTelegramClient("auth_token", "hello_bot", "http://webhook")
        assert client
        assert client.name == "hello_bot"
        assert client.type == KaironChannels.TELEGRAM

    def test_handle_message(self, mock_telegram_client, mock_model_response, mock_send_response):
        message = {
            "update_id": 646911460,
            "message": {
                "message_id": 93,
                "from": {
                    "id": 100001111,
                    "is_bot": False,
                    "first_name": "kairon",
                    "username": "user",
                    "language_code": "en-US"
                },
                "chat": {
                    "id": 100001111,
                    "first_name": "kairon",
                    "username": "user",
                    "type": "private"
                },
                "date": 1509641174,
                "text": "hi"
            }
        }
        client = KaironTelegramClient("auth_token", "hello_bot", "http://webhook")
        assert client
        client.handle_message(message)

    def test_handle_message_exception(self, mock_telegram_client, mock_model_response, mock_send_response_exception):
        message = {
            "update_id": 646911460,
            "message": {
                "message_id": 93,
                "from": {
                    "id": 100001111,
                    "is_bot": False,
                    "first_name": "kairon",
                    "username": "user",
                    "language_code": "en-US"
                },
                "chat": {
                    "id": 100001111,
                    "first_name": "kairon",
                    "username": "user",
                    "type": "private"
                },
                "date": 1509641174,
                "text": "hi"
            }
        }
        client = KaironTelegramClient("auth_token", "hello_bot", "http://webhook")
        assert client
        with pytest.raises(Exception):
            client.handle_message(message)

    def test_handle_voice_message(self, mock_telegram_client, mock_model_response, mock_send_voice_response):
        message = {
            "update_id": 646911460,
            "message": {
                "message_id": 93,
                "from": {
                    "id": 100001111,
                    "is_bot": False,
                    "first_name": "kairon",
                    "username": "user",
                    "language_code": "en-US"
                },
                "chat": {
                    "id": 100001111,
                    "first_name": "kairon",
                    "username": "user",
                    "type": "private"
                },
                "date": 1509641174,
                "voice": "http://filename"
            }
        }
        client = KaironTelegramClient("auth_token", "hello_bot", "http://webhook")
        assert client
        client.handle_message(message)

    def test_handle_other_message_types(self, mock_telegram_client, mock_model_response, mock_send_response):
        message = {
            "update_id": 646911460,
            "message": {
                "message_id": 93,
                "from": {
                    "id": 100001111,
                    "is_bot": False,
                    "first_name": "kairon",
                    "username": "user",
                    "language_code": "en-US"
                },
                "chat": {
                    "id": 100001111,
                    "first_name": "kairon",
                    "username": "user",
                    "type": "private"
                },
                "date": 1509641174,
                "audio": "http://filename"
            }
        }
        client = KaironTelegramClient("auth_token", "hello_bot", "http://webhook")
        assert client
        client.handle_message(message)

    def test_is_text_message(self):
        message = {
            "update_id": 646911460,
            "message": {
                "message_id": 93,
                "from": {
                    "id": 100001111,
                    "is_bot": False,
                    "first_name": "kairon",
                    "username": "user",
                    "language_code": "en-US"
                },
                "chat": {
                    "id": 100001111,
                    "first_name": "kairon",
                    "username": "user",
                    "type": "private"
                },
                "date": 1509641174,
                "text": "hi"
            }
        }
        assert KaironTelegramClient.is_text_message(message)

        message = {
            "update_id": 646911460,
            "message": {
                "message_id": 93,
                "from": {
                    "id": 100001111,
                    "is_bot": False,
                    "first_name": "kairon",
                    "username": "user",
                    "language_code": "en-US"
                },
                "chat": {
                    "id": 100001111,
                    "first_name": "kairon",
                    "username": "user",
                    "type": "private"
                },
                "date": 1509641174,
                "voice": "http://filename"
            }
        }
        assert not KaironTelegramClient.is_text_message(message)

    def test_is_voice_message(self):
        message = {
            "update_id": 646911460,
            "message": {
                "message_id": 93,
                "from": {
                    "id": 100001111,
                    "is_bot": False,
                    "first_name": "kairon",
                    "username": "user",
                    "language_code": "en-US"
                },
                "chat": {
                    "id": 100001111,
                    "first_name": "kairon",
                    "username": "user",
                    "type": "private"
                },
                "date": 1509641174,
                "text": "hi"
            }
        }
        assert not KaironTelegramClient.is_voice_msg(message)

        message = {
            "update_id": 646911460,
            "message": {
                "message_id": 93,
                "from": {
                    "id": 100001111,
                    "is_bot": False,
                    "first_name": "kairon",
                    "username": "user",
                    "language_code": "en-US"
                },
                "chat": {
                    "id": 100001111,
                    "first_name": "kairon",
                    "username": "user",
                    "type": "private"
                },
                "date": 1509641174,
                "voice": "http://filename"
            }
        }
        assert KaironTelegramClient.is_voice_msg(message)


class TestChatServerUtils:

    @pytest.fixture(autouse=True, scope='session')
    def setup(self):
        os.environ["chat_config_file"] = "./tests/testing_data/chat-config.yaml"
        ChatServerUtils.load_evironment()

    def test_encode_and_decode(self):
        auth_token = ChatServerUtils.encode_auth_token("test@digite.com")
        assert auth_token

        username = ChatServerUtils.decode_auth_token(auth_token)
        assert username == "test@digite.com"

    def test_is_empty(self):
        assert ChatServerUtils.is_empty("")
        assert ChatServerUtils.is_empty("        ")
        assert ChatServerUtils.is_empty(None)
        assert not ChatServerUtils.is_empty("non-empty string")
