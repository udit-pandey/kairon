import asyncio
import os

import pytest
from mongoengine import connect, ValidationError
from rasa.core.agent import Agent

from kairon.api.data_objects import Bot, User, UserEmailConfirmation, Account
from kairon.chat_server.channels.channels import KaironChannels
from kairon.chat_server.chat_server_utils import ChatServerUtils
from kairon.chat_server.data_objects import ChannelCredentials
from kairon.chat_server.exceptions import ChatServerException, AuthenticationException
from kairon.chat_server.processor import AgentProcessor, KaironMessageProcessor, AuthenticationProcessor, \
    ChannelCredentialsProcessor


class TestKaironMessageProcessor:

    @pytest.fixture
    def mock_agent_response(self, monkeypatch):
        def _get_agent(*args, **kwargs):
            return Agent

        def _agent_response(*args, **kwargs):
            future = asyncio.Future()
            future.set_result([{"recipient_id": "text_user_id", "text": "hello"}])
            return future

        monkeypatch.setattr(Agent, "handle_text", _agent_response)
        monkeypatch.setattr(AgentProcessor, "get_agent", _get_agent)

    @pytest.mark.asyncio
    async def test_process_test_message(self, mock_agent_response):
        response = await KaironMessageProcessor.process_text_message("test_bot", "hi", "kairon_user")
        assert response == "hello"


class TestAuthenticationProcessor:

    @pytest.fixture(autouse=True, scope="session")
    def init_connection(self):
        os.environ["chat_config_file"] = "./tests/testing_data/chat-config.yaml"
        ChatServerUtils.load_evironment()
        connect(host=ChatServerUtils.environment["database"]['url'])

    def test_validate_user_and_get_info(self):
        Bot(id="5ea8125db7c285f40551295c", name="5ea8125db7c285f40551295c", account=1, user="Admin").save()
        User(email="test@digite.com", first_name="test",
             last_name="user",
             password="$2b$12$mhxp/i29U1STS3ktERdIzOWigpgPtApOSjHdkMD/TtTcL0bu2SOna",
             role="admin",
             is_integration_user=False,
             account=1,
             bot="5ea8125db7c285f40551295c",
             user="Admin").save()
        UserEmailConfirmation(email="test@digite.com").save()
        Account(id=1, name="test", user="sysadmin").save()
        auth_token = ChatServerUtils.encode_auth_token("test@digite.com").decode("utf-8")

        user = AuthenticationProcessor.validate_user_and_get_info(auth_token)
        assert user['email'] == "test@digite.com"
        assert user['first_name'] == "test"
        assert user['last_name'] == "user"
        assert user['role'] == "admin"
        assert not user['is_integration_user']
        assert user['bot'] == '5ea8125db7c285f40551295c'
        assert user['user'] == 'Admin'

    def test_validate_user_and_get_info_empty_auth_token(self):
        with pytest.raises(AuthenticationException):
            AuthenticationProcessor.validate_user_and_get_info(None)

        with pytest.raises(AuthenticationException):
            AuthenticationProcessor.validate_user_and_get_info("")

    def test_validate_user_and_get_info_user_not_found(self):
        with pytest.raises(AuthenticationException):
            AuthenticationProcessor.validate_user_and_get_info(
                "eyJ0eXAiOiJKV1QiLCJhbGciOiJIUzI1NiJ9.eyJzdWIiOiJ0ZXN0QGRpZ2l0ZS5jb20iLCJleHAiOjE2MTQ0MTQyNTcsImlhdCI6MTYxNDQxNDI1Mn0.iFWhGp0nxNjDmfYDuktdON7W-H0Q7O4jWvHmon7upCk")

    def test_validate_user_and_get_info_deleted_bot(self):
        Bot(id="5ea8125db7c285f40551295e", name="5ea8125db7c285f40551295e", account=3, user="Admin",
            status=False).save()
        User(email="test_2@digite.com", first_name="test",
             last_name="user",
             password="$2b$12$mhxp/i29U1STS3ktERdIzOWigpgPtApOSjHdkMD/TtTcL0bu2SOna",
             role="admin",
             is_integration_user=False,
             account=3,
             bot="5ea8125db7c285f40551295e",
             user="Admin").save()
        UserEmailConfirmation(email="test_2@digite.com").save()
        Account(id=3, name="test", user="sysadmin").save()

        auth_token = ChatServerUtils.encode_auth_token("test_2@digite.com").decode("utf-8")

        with pytest.raises(ValidationError):
            AuthenticationProcessor.validate_user_and_get_info(auth_token)

    def test_validate_user_and_get_info_inactive_account(self):
        Bot(id="5ea8125db7c285f40551296a", name="5ea8125db7c285f40551296a", account=5, user="Admin").save()
        User(email="test_5@digite.com", first_name="test",
             last_name="user",
             password="$2b$12$mhxp/i29U1STS3ktERdIzOWigpgPtApOSjHdkMD/TtTcL0bu2SOna",
             role="admin",
             is_integration_user=False,
             account=5,
             bot="5ea8125db7c285f40551296a",
             user="Admin",
             status=False).save()
        UserEmailConfirmation(email="test_4@digite.com").save()
        Account(id=5, name="test", user="sysadmin").save()

        auth_token = ChatServerUtils.encode_auth_token("test_5@digite.com").decode("utf-8")

        with pytest.raises(ValidationError):
            AuthenticationProcessor.validate_user_and_get_info(auth_token)

    def test_validate_user_and_get_info_invalid_auth(self):
        with pytest.raises(Exception):
            AuthenticationProcessor.validate_user_and_get_info(
                "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiIxMjM0NTY3ODkwIiwibmFtZSI6IkpvaG4gRG9lIiwiaWF0IjoxNTE2MjM5MDIyfQ.abcdefghijklmnopqrstuvwxyzabcdefghijklmnopq")


class TestChannelCredentialsProcessor:

    @pytest.fixture(autouse=True, scope="session")
    def init_connection(self):
        os.environ["chat_config_file"] = "./tests/testing_data/chat-config.yaml"
        ChatServerUtils.load_evironment()
        connect(host=ChatServerUtils.environment["database"]['url'])

    def test_add_credentials(self):
        credentials = {"auth_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9"}
        ChannelCredentialsProcessor.add_credentials("test_bot", "test@digite.com", KaironChannels.TELEGRAM, credentials)

        creds = ChannelCredentials.objects.get(bot="test_bot", user="test@digite.com", channel=KaironChannels.TELEGRAM,
                                               status=True)
        assert creds['credentials']['auth_token'] == "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9"

    def test_add_credentials_existing(self):
        credentials = {"auth_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9"}
        with pytest.raises(ChatServerException):
            ChannelCredentialsProcessor.add_credentials("test_bot", "test@digite.com", KaironChannels.TELEGRAM,
                                                        credentials)

    def test_get_credentials(self):
        creds = ChannelCredentialsProcessor.get_credentials("test_bot", "test@digite.com", KaironChannels.TELEGRAM)
        assert creds
        assert creds['bot'] == "test_bot"
        assert creds['user'] == 'test@digite.com'
        assert creds['channel'] == KaironChannels.TELEGRAM
        assert creds['credentials']
        assert creds['timestamp']
        assert creds['status']
        assert creds['credentials']['auth_token'] == "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9"

    def test_get_credentials_non_existing(self):
        with pytest.raises(ChatServerException):
            ChannelCredentialsProcessor.get_credentials("test_bot_non_existing", "test_non_existing@digite.com", KaironChannels.TELEGRAM)

    def test_update_credentials(self):
        credentials = {"auth_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJJ"}
        ChannelCredentialsProcessor.update_credentials("test_bot", "test@digite.com", KaironChannels.TELEGRAM,
                                                       credentials)
        creds = ChannelCredentials.objects.get(bot="test_bot", user="test@digite.com", channel=KaironChannels.TELEGRAM,
                                               status=True)
        assert creds['credentials']['auth_token'] == "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJJ"

    def test_update_non_existing(self):
        credentials = {"auth_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJJ"}
        with pytest.raises(ChatServerException):
            ChannelCredentialsProcessor.update_credentials("test_bot_non_existing", "test_non_existing@digite.com", KaironChannels.TELEGRAM,
                                                           credentials)

    def test_delete_credentials(self):
        ChannelCredentialsProcessor.delete_credentials("test_bot", "test@digite.com", KaironChannels.TELEGRAM)
        creds = ChannelCredentials.objects.get(bot="test_bot", user="test@digite.com", channel=KaironChannels.TELEGRAM,
                                               status=False)
        assert creds
        assert creds['credentials']['auth_token'] == "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJJ"

    def test_delete_credentials_non_existing(self):
        with pytest.raises(ChatServerException):
            ChannelCredentialsProcessor.delete_credentials("test_bot", "test_non_existing@digite.com",
                                                           KaironChannels.TELEGRAM)

    def test_add_credentials_more(self):
        credentials = {"auth_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCCC"}
        ChannelCredentialsProcessor.add_credentials("test_bot_1", "test_1@digite.com", KaironChannels.TELEGRAM,
                                                    credentials)

        credentials = {"auth_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVDDD"}
        ChannelCredentialsProcessor.add_credentials("test_bot_2", "test_2@digite.com", KaironChannels.TELEGRAM,
                                                    credentials)
        credentials = {"auth_token": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCCC"}
        ChannelCredentialsProcessor.add_credentials("test_bot_2", "test_2@digite.com", KaironChannels.FACEBOOK,
                                                    credentials)
        creds = ChannelCredentialsProcessor.list_credentials("test_bot_2", "test_2@digite.com")
        creds = list(creds)
        print(creds)
        assert creds[0]['credentials']['auth_token'] == "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVDDD"
        assert creds[1]['credentials']['auth_token'] == "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCCC"

    def test_list_credentials_empty(self):
        creds = ChannelCredentialsProcessor.list_credentials("test_bot_1", "test_1@digite.com")
        assert len(list(creds)) == 1

        creds = ChannelCredentialsProcessor.list_credentials("test_bot_2", "test_2@digite.com")
        assert len(list(creds)) == 2

        ChannelCredentialsProcessor.delete_credentials("test_bot_1", "test_1@digite.com", KaironChannels.TELEGRAM)
        ChannelCredentialsProcessor.delete_credentials("test_bot_2", "test_2@digite.com", KaironChannels.TELEGRAM)
        assert len(list(creds)) == 0
