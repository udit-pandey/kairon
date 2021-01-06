from datetime import datetime
from typing import Text

from loguru import logger
from kairon.utils import Utility
from .processor import MongoProcessor
from kairon.history_server.history import HistoryServer
from kairon.history_server.models import HistoryMonthEnum, HistoryMonth


class ChatHistory:
    """Class contains logic for fetching history data and metrics from mongo tracker"""

    mongo_processor = MongoProcessor()

    @staticmethod
    def fetch_chat_history(bot: Text, sender, month: HistoryMonthEnum = HistoryMonthEnum.One):
        """
        fetches chat history

        :param month: default is current month and max is last 6 months
        :param bot: bot id
        :param sender: history details for user
        :return: list of conversations
        """
        message = None
        endpoint = ChatHistory.get_tracker_endpoint(bot)
        if endpoint["tracker_endpoint"]["type"] == 'rest':
            api_endpoint = endpoint["tracker_endpoint"]["url"] + "/users/" + sender
            request = {"month": month.value}
            token = ''
            if Utility.environment["history_server"]["token"] is not None:
                token = Utility.environment["history_server"]["token"]
            auth_token = 'bearer ' + token
            response = Utility.execute_http_request(http_url=api_endpoint, request_method="GET",
                                                    request_body=request, auth_token=auth_token)
            events, message = (response['data']['history'], response['message'])
        else:
            events = HistoryServer.fetch_chat_history(
                sender, month=month, load_rest_tracker=False, endpoint=endpoint)
        return list(ChatHistory.__prepare_data(bot, events)), message

    @staticmethod
    def fetch_chat_users(bot: Text, month: HistoryMonthEnum = HistoryMonthEnum.One):
        """
        fetches user list who has conversation with the agent

        :param month: default is current month and max is last 6 months
        :param bot: bot id
        :return: list of user id
        """
        message = None
        endpoint = ChatHistory.get_tracker_endpoint(bot)
        if endpoint["tracker_endpoint"]["type"] == 'rest':
            api_endpoint = endpoint["tracker_endpoint"]["url"] + "/users"
            request = {"month": month.value}
            token = ''
            if Utility.environment["history_server"]["token"] is not None:
                token = Utility.environment["history_server"]["token"]
            auth_token = 'bearer ' + token
            response = Utility.execute_http_request(http_url=api_endpoint, request_method="GET",
                                                    request_body=request, auth_token=auth_token)
            users, message = (response['data']['users'], response['message'])
        else:
            users = HistoryServer.fetch_chat_users(month, False, endpoint)

        return users, message

    @staticmethod
    def __prepare_data(bot: Text, events):
        bot_action = None
        training_examples, ids = ChatHistory.mongo_processor.get_all_training_examples(
            bot
        )
        if events:
            event_list = ["user", "bot"]
            for i in range(events.__len__()):
                event = events[i]
                if event["event"] in event_list:
                    result = {
                        "event": event["event"],
                        "time": datetime.fromtimestamp(event["timestamp"]).time(),
                        "date": datetime.fromtimestamp(event["timestamp"]).date(),
                    }

                    if event.get("text"):
                        result["text"] = event.get("text")
                        text_data = str(event.get("text")).lower()
                        result["is_exists"] = text_data in training_examples
                        if result["is_exists"]:
                            result["_id"] = ids[training_examples.index(text_data)]

                    if event["event"] == "user":
                        parse_data = event["parse_data"]
                        result["intent"] = parse_data["intent"]["name"]
                        result["confidence"] = parse_data["intent"]["confidence"]
                    elif event["event"] == "bot":
                        if bot_action:
                            result["action"] = bot_action

                    if result:
                        yield result
                else:
                    bot_action = (
                        event["name"] if event["event"] == "action" else None
                    )

    @staticmethod
    def fetch_user_history(bot: Text, sender_id: Text, month: HistoryMonthEnum = HistoryMonthEnum.One):
        """
        loads list of conversation events from chat history

        :param month: default is current month and max is last 6 months
        :param bot: bot id
        :param sender_id: user id
        :return: list of conversation events
        """
        endpoint = ChatHistory.get_tracker_endpoint(bot)
        if endpoint["tracker_endpoint"]["type"] == 'rest':
            api_endpoint = endpoint["tracker_endpoint"]["url"] + "/users/" + sender_id
            request = {"month": month.value}
            token = ''
            if Utility.environment["history_server"]["token"] is not None:
                token = Utility.environment["history_server"]["token"]
            auth_token = 'bearer ' + token
            response = Utility.execute_http_request(http_url=api_endpoint, request_method="GET",
                                                    request_body=request, auth_token=auth_token)
            events, message = (response['data']['events'], response['message'])
        else:
            events, message = HistoryServer.fetch_user_history(sender_id, month, False, endpoint)

        return events, message

    @staticmethod
    def visitor_hit_fallback(bot: Text, month: HistoryMonthEnum = HistoryMonthEnum.One):
        """
        Counts the number of times, the agent was unable to provide a response to users

        :param bot: bot id
        :param month: default is current month and max is last 6 months
        :return: list of visitor fallback
        """
        message = None
        endpoint = ChatHistory.get_tracker_endpoint(bot)
        if endpoint["tracker_endpoint"]["type"] == 'rest':
            api_endpoint = endpoint["tracker_endpoint"]["url"] + "/metrics/fallback"
            request = {"month": month.value}
            token = ''
            if Utility.environment["history_server"]["token"] is not None:
                token = Utility.environment["history_server"]["token"]
            auth_token = 'bearer ' + token
            response = Utility.execute_http_request(http_url=api_endpoint, request_method="GET",
                                                    request_body=request, auth_token=auth_token)
            fallback_count, total_count, message = (
                response['data']['fallback_count'], response['data']['total_count'], response['message'])
        else:
            fallback_count, total_count = HistoryServer.visitor_hit_fallback(month, False, endpoint)

        return (
            {"fallback_count": fallback_count, "total_count": total_count}, message,
        )

    @staticmethod
    def conversation_steps(bot: Text, month: HistoryMonthEnum = HistoryMonthEnum.One):
        """
        calculates the number of conversation steps between agent and users

        :param bot: bot id
        :param month: default is current month and max is last 6 months
        :return: list of conversation step count
        """
        message = None
        endpoint = ChatHistory.get_tracker_endpoint(bot)
        if endpoint["tracker_endpoint"]["type"] == 'rest':
            api_endpoint = endpoint["tracker_endpoint"]["url"] + "/metrics/conversation/steps"
            request = {"month": month.value}
            token = ''
            if Utility.environment["history_server"]["token"] is not None:
                token = Utility.environment["history_server"]["token"]
            auth_token = 'bearer ' + token
            response = Utility.execute_http_request(http_url=api_endpoint, request_method="GET",
                                                    request_body=request, auth_token=auth_token)
            values, message = (response['data']['conversation_steps'], response['message'])
        else:
            values = HistoryServer.conversation_steps(month, False, endpoint)

        return values, message

    @staticmethod
    def conversation_time(bot: Text, month: HistoryMonthEnum = HistoryMonthEnum.One):
        """
        calculates the duration of between agent and users

        :param bot: bot id
        :param month: default is current month and max is last 6 months
        :return: list of users duration
        """
        message = None
        endpoint = ChatHistory.get_tracker_endpoint(bot)
        if endpoint["tracker_endpoint"]["type"] == 'rest':
            api_endpoint = endpoint["tracker_endpoint"]["url"] + "/metrics/conversation/time"
            request = {"month": month.value}
            token = ''
            if Utility.environment["history_server"]["token"] is not None:
                token = Utility.environment["history_server"]["token"]
            auth_token = 'bearer ' + token
            response = Utility.execute_http_request(http_url=api_endpoint, request_method="GET",
                                                    request_body=request, auth_token=auth_token)
            values, message = (response['data']['conversation_time'], response['message'])
        else:
            values = HistoryServer.conversation_time(month, False, endpoint)

        return values, message

    @staticmethod
    def user_with_metrics(bot, month: HistoryMonthEnum = HistoryMonthEnum.One):
        """
        fetches user with the steps and time in conversation

        :param bot: bot id
        :param month: default is current month and max is last 6 months
        :return: list of users with step and time in conversation
        """
        message = None
        endpoint = ChatHistory.get_tracker_endpoint(bot)
        if endpoint["tracker_endpoint"]["type"] == 'rest':
            api_endpoint = endpoint["tracker_endpoint"]["url"] + "/metrics/users"
            request = {"month": month.value}
            token = ''
            if Utility.environment["history_server"]["token"] is not None:
                token = Utility.environment["history_server"]["token"]
            auth_token = 'bearer ' + token
            response = Utility.execute_http_request(http_url=api_endpoint, request_method="GET",
                                                    request_body=request, auth_token=auth_token)
            users, message = (response['data']['users'], response['message'])
        else:
            users = HistoryServer.user_with_metrics(month, False)

        return users, message

    @staticmethod
    def get_tracker_endpoint(bot: Text):
        try:
            endpoint = ChatHistory.mongo_processor.get_endpoints(bot)
            endpoint["tracker_endpoint"]['collection'] = "conversations"
        except Exception:
            username, password, url, db_name = Utility.get_local_db()
            endpoint = {"tracker_endpoint": {}}
            endpoint["tracker_endpoint"]['url'] = url
            endpoint["tracker_endpoint"]['db'] = db_name
            endpoint["tracker_endpoint"]['username'] = username
            endpoint["tracker_endpoint"]['password'] = password
            endpoint["tracker_endpoint"]["type"] = 'mongo'
            endpoint["tracker_endpoint"]['collection'] = bot
        return endpoint
