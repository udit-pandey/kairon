import os
from datetime import datetime, timedelta
from typing import Text

from loguru import logger
from pymongo import MongoClient
from pymongo.errors import InvalidURI
from pymongo.uri_parser import SCHEME, SCHEME_LEN, SRV_SCHEME, SRV_SCHEME_LEN, parse_userinfo
from rasa.shared.core.domain import Domain
from rasa.core.tracker_store import MongoTrackerStore
from smart_config import ConfigLoader

from .exceptions import HistoryServerException
from .models import HistoryMonthEnum, HistoryMonth


class HistoryServerUtils:

    @staticmethod
    def load_environment(load_tracker: bool = True):
        """
        Utility to load environment variables from tracker.yaml when tracker type is mongo
        and system.yaml when tracker type is rest

        :return: None
        """
        if load_tracker:
            environment = ConfigLoader(os.getenv("system_file", "./tracker.yaml")).get_config()
        else:
            environment = ConfigLoader(os.getenv("system_file", "./system.yaml")).get_config()
        return environment

    @staticmethod
    def get_month_as_int(month):
        if isinstance(month, HistoryMonthEnum):
            month_as_int = month.value
        elif isinstance(month, HistoryMonth):
            month_as_int = month.month.value
        else:
            month_as_int = int(month)
        return month_as_int

    @staticmethod
    def get_timestamp_previous_month(month: int):
        start_time = datetime.now() - timedelta(month * 30, seconds=0, minutes=0, hours=0)
        return start_time.timestamp()

    @staticmethod
    def extract_user_password(uri: str):
        """
        extract username, password and host with port from mongo uri

        :param uri: mongo uri
        :return: username, password, scheme, hosts
        """
        if uri.startswith(SCHEME):
            scheme_free = uri[SCHEME_LEN:]
            scheme = uri[:SCHEME_LEN]
        elif uri.startswith(SRV_SCHEME):
            scheme_free = uri[SRV_SCHEME_LEN:]
            scheme = uri[:SRV_SCHEME_LEN]
        else:
            raise InvalidURI(
                "Invalid URI scheme: URI must "
                "begin with '%s' or '%s'" % (SCHEME, SRV_SCHEME)
            )

        if not scheme_free:
            raise InvalidURI("Must provide at least one hostname or IP.")

        host_part, _, _ = scheme_free.partition("/")
        if "@" in host_part:
            userinfo, _, hosts = host_part.rpartition("@")
            user, passwd = parse_userinfo(userinfo)
            return user, passwd, scheme + hosts
        else:
            return None, None, scheme + host_part

    @staticmethod
    def get_mongo_tracker_store(bot: Text, domain: Domain, load_rest_tracker: bool = True, endpoint=None):
        """
        loads mongo tracker using user configured
        mongo tracker endpoint details

        :param bot: bot id
        :param domain: domain data
        :param load_rest_tracker: True then it is a rest endpoint, otherwise
                                  it is a mongo tracker endpoint.
        :param endpoint: Mongo tracker endpoint details
        :return: mongo tracker
        """
        if load_rest_tracker:
            endpoint = HistoryServerUtils.load_environment(load_rest_tracker)
        else:
            if not endpoint or not endpoint["tracker_endpoint"] or \
                    not endpoint['tracker_endpoint']["url"] or \
                    not endpoint["tracker_endpoint"]['db']:
                raise HistoryServerException('Mongo tracker endpoint details missing')

        host = endpoint['tracker_endpoint']["url"]
        db = endpoint["tracker_endpoint"]['db']
        if not load_rest_tracker:
            username = endpoint['tracker_endpoint'].get("username")
            password = endpoint['tracker_endpoint'].get("password")
        else:
            username, password, host = HistoryServerUtils.extract_user_password(host)
        return MongoTrackerStore(
            domain=domain,
            host=host,
            db=db,
            collection=bot,
            username=username,
            password=password,
        )

    @staticmethod
    def get_mongo_connection(load_rest_tracker: bool = True, endpoint=None):
        """
        Creates mongo client from mongo tracker endpoint details if given otherwise connects
        to local database.
        :param load_rest_tracker: True then it is a rest endpoint, otherwise
                                  it is a mongo tracker endpoint.
        :param endpoint: Mongo tracker endpoint details
        :return: Mongo client, database and collection
        """
        if load_rest_tracker:
            endpoint = HistoryServerUtils.load_environment(load_rest_tracker)
        else:
            if not endpoint or not endpoint["tracker_endpoint"] or \
                    not endpoint['tracker_endpoint']["url"] or \
                    not endpoint["tracker_endpoint"]['db']:
                raise HistoryServerException('Mongo tracker endpoint details missing')

        host = endpoint['tracker_endpoint']["url"]
        if not load_rest_tracker:
            username = endpoint['tracker_endpoint'].get("username")
            password = endpoint['tracker_endpoint'].get("password")
        else:
            username, password, host = HistoryServerUtils.extract_user_password(host)
        try:
            client = MongoClient(host=host, username=username, password=password)
            db = endpoint["tracker_endpoint"]['db']
        except Exception as e:
            raise HistoryServerException(str(e))

        return client, db, endpoint["tracker_endpoint"]['collection']


class HistoryServer:
    """Class contains logic for fetching history data and metrics from mongo tracker"""

    @staticmethod
    def fetch_chat_history(sender, month: HistoryMonthEnum = 1, load_rest_tracker: bool = True, endpoint=None):
        """
        fetches chat history

        :param month: default is current month and max is last 6 months
        :param sender: history details for user
        :param load_rest_tracker: False when tracker type is mongo, true if it is rest
        :param endpoint: Mongo tracker endpoint details
        :return: list of conversations
        """
        events = HistoryServer.fetch_user_history(sender, month=month,
                                                  load_rest_tracker=load_rest_tracker, endpoint=endpoint)
        return events

    @staticmethod
    def fetch_chat_users(month: HistoryMonthEnum = 1, load_rest_tracker: bool = True, endpoint=None):
        """
        fetches user list who has conversation with the agent

        :param month: default is current month and max is last 6 months
        :param load_rest_tracker: False when tracker type is mongo, true if it is rest
        :param endpoint: Mongo tracker endpoint details
        :return: list of user id
        """
        client, db_name, collection = HistoryServerUtils.get_mongo_connection(load_rest_tracker, endpoint)
        db = client.get_database(db_name)
        conversations = db.get_collection(collection)
        month_as_int = HistoryServerUtils.get_month_as_int(month)
        try:
            values = conversations.find(
                {"events.timestamp": {"$gte": HistoryServerUtils.get_timestamp_previous_month(month_as_int)}},
                {"_id": 0, "sender_id": 1})
            users = [sender["sender_id"] for sender in values]
        except Exception as e:
            raise HistoryServerException(e)
        finally:
            client.close()
        return users

    @staticmethod
    def fetch_user_history(sender_id: Text, month: HistoryMonthEnum = 1, load_rest_tracker: bool = True, endpoint=None):
        """
        loads list of conversation events from chat history

        :param month: default is current month and max is last 6 months
        :param load_rest_tracker: False when tracker type is mongo, true if it is rest
        :param sender_id: user id
        :param endpoint: Mongo tracker endpoint details
        :return: list of conversation events
        """
        if not sender_id or not sender_id.strip():
            raise HistoryServerException("sender_id cannot be empty")
        client, db_name, collection = HistoryServerUtils.get_mongo_connection(load_rest_tracker, endpoint)
        try:
            db = client.get_database(db_name)
            conversations = db.get_collection(collection)
            month_as_int = HistoryServerUtils.get_month_as_int(month)
            values = list(conversations
                          .aggregate([{"$match": {"sender_id": sender_id, "events.timestamp": {
                "$gte": HistoryServerUtils.get_timestamp_previous_month(month_as_int)}}},
                                      {"$unwind": "$events"},
                                      {"$match": {"events.event": {"$in": ["user", "bot", "action"]}}},
                                      {"$group": {"_id": None, "events": {"$push": "$events"}}},
                                      {"$project": {"_id": 0, "events": 1}}])
                          )
            if values:
                return (
                    values[0]['events']
                )
            return []
        except Exception as e:
            raise HistoryServerException(e)
        finally:
            client.close()

    @staticmethod
    def visitor_hit_fallback(month: HistoryMonthEnum = 1, load_rest_tracker: bool = True, endpoint=None):
        """
        Counts the number of times, the agent was unable to provide a response to users

        :param month: default is current month and max is last 6 months
        :param load_rest_tracker: False when tracker type is mongo, true if it is rest
        :param endpoint: Mongo tracker endpoint details
        :return: list of visitor fallback
        """

        client, database, collection = HistoryServerUtils.get_mongo_connection(load_rest_tracker, endpoint)
        db = client.get_database(database)
        conversations = db.get_collection(collection)
        month_as_int = HistoryServerUtils.get_month_as_int(month)
        try:
            values = list(conversations.aggregate([{"$unwind": "$events"},
                                                   {"$match": {"events.event": "action", "events.timestamp": {
                                                       "$gte": HistoryServerUtils.get_timestamp_previous_month(
                                                           month_as_int)}}},
                                                   {"$group": {"_id": "$sender_id", "total_count": {"$sum": 1},
                                                               "events": {"$push": "$events"}}},
                                                   {"$unwind": "$events"},
                                                   {"$match": {
                                                       "events.name": {"$regex": ".*fallback*.", "$options": "$i"}}},
                                                   {"$group": {"_id": None, "total_count": {"$first": "$total_count"},
                                                               "fallback_count": {"$sum": 1}}},
                                                   {"$project": {"total_count": 1, "fallback_count": 1, "_id": 0}}
                                                   ], allowDiskUse=True))
        except Exception as e:
            raise HistoryServerException(e)
        finally:
            client.close()
        if not values:
            fallback_count = 0
            total_count = 0
        else:
            fallback_count = values[0]['fallback_count'] if values[0]['fallback_count'] else 0
            total_count = values[0]['total_count'] if values[0]['total_count'] else 0
        return fallback_count, total_count

    @staticmethod
    def conversation_steps(month: HistoryMonthEnum = 1, load_rest_tracker: bool = True, endpoint=None):
        """
        calculates the number of conversation steps between agent and users

        :param month: default is current month and max is last 6 months
        :param load_rest_tracker: False when tracker type is mongo, true if it is rest
        :param endpoint: Mongo tracker endpoint details
        :return: list of conversation step count
        """
        client, database, collection = HistoryServerUtils.get_mongo_connection(load_rest_tracker, endpoint)
        db = client.get_database(database)
        conversations = db.get_collection(collection)
        month_as_int = HistoryServerUtils.get_month_as_int(month)
        try:
            values = list(conversations
                          .aggregate([{"$unwind": {"path": "$events", "includeArrayIndex": "arrayIndex"}},
                                      {"$match": {"events.event": {"$in": ["user", "bot"]},
                                                  "events.timestamp": {
                                                      "$gte": HistoryServerUtils.get_timestamp_previous_month(
                                                          month_as_int)}}},
                                      {"$group": {"_id": "$sender_id", "events": {"$push": "$events"},
                                                  "allevents": {"$push": "$events"}}},
                                      {"$unwind": "$events"},
                                      {"$project": {
                                          "_id": 1,
                                          "events": 1,
                                          "following_events": {
                                              "$arrayElemAt": [
                                                  "$allevents",
                                                  {"$add": [{"$indexOfArray": ["$allevents", "$events"]}, 1]}
                                              ]
                                          }
                                      }},
                                      {"$project": {
                                          "user_event": "$events.event",
                                          "bot_event": "$following_events.event",
                                      }},
                                      {"$match": {"user_event": "user", "bot_event": "bot"}},
                                      {"$group": {"_id": "$_id", "event": {"$sum": 1}}},
                                      {"$project": {
                                          "sender_id": "$_id",
                                          "_id": 0,
                                          "event": 1,
                                      }}
                                      ], allowDiskUse=True)
                          )
        except Exception as e:
            raise HistoryServerException(e)
        return values

    @staticmethod
    def conversation_time(month: HistoryMonthEnum = 1, load_rest_tracker: bool = True, endpoint=None):
        """
        calculates the duration of between agent and users

        :param month: default is current month and max is last 6 months
        :param load_rest_tracker: False when tracker type is mongo, true if it is rest
        :param endpoint: Mongo tracker endpoint details
        :return: list of users duration
        """
        client, database, collection = HistoryServerUtils.get_mongo_connection(load_rest_tracker, endpoint)
        db = client.get_database(database)
        conversations = db.get_collection(collection)
        month_as_int = HistoryServerUtils.get_month_as_int(month)
        try:
            values = list(conversations
                          .aggregate([{"$unwind": "$events"},
                                      {"$match": {"events.event": {"$in": ["user", "bot"]},
                                                  "events.timestamp": {
                                                      "$gte": HistoryServerUtils.get_timestamp_previous_month(
                                                          month_as_int)}}},
                                      {"$group": {"_id": "$sender_id", "events": {"$push": "$events"},
                                                  "allevents": {"$push": "$events"}}},
                                      {"$unwind": "$events"},
                                      {"$project": {
                                          "_id": 1,
                                          "events": 1,
                                          "following_events": {
                                              "$arrayElemAt": [
                                                  "$allevents",
                                                  {"$add": [{"$indexOfArray": ["$allevents", "$events"]}, 1]}
                                              ]
                                          }
                                      }},
                                      {"$project": {
                                          "user_event": "$events.event",
                                          "bot_event": "$following_events.event",
                                          "time_diff": {
                                              "$subtract": ["$following_events.timestamp", "$events.timestamp"]
                                          }
                                      }},
                                      {"$match": {"user_event": "user", "bot_event": "bot"}},
                                      {"$group": {"_id": "$_id", "time": {"$sum": "$time_diff"}}},
                                      {"$project": {
                                          "sender_id": "$_id",
                                          "_id": 0,
                                          "time": 1,
                                      }}
                                      ], allowDiskUse=True)
                          )
        except Exception as e:
            raise HistoryServerException(e)
        return values

    @staticmethod
    def get_conversations(bot: Text, domain: Domain):
        """
        fetches all the conversations between agent and users

        :param domain: bot domain
        :return: list of conversations, message
        """
        _, tracker = HistoryServerUtils.get_mongo_tracker_store(bot, domain)
        try:
            conversations = list(tracker.conversations.find())
        except Exception as e:
            raise HistoryServerException(e)
        finally:
            tracker.client.close()
        return conversations

    @staticmethod
    def user_with_metrics(month: HistoryMonthEnum = 1, load_rest_tracker: bool = True, endpoint=None):
        """
        fetches user with the steps and time in conversation

        :param month: default is current month and max is last 6 months
        :param load_rest_tracker: False when tracker type is mongo, true if it is rest
        :param endpoint: Mongo tracker endpoint details
        :return: list of users with step and time in conversation
        """
        client, database, collection = HistoryServerUtils.get_mongo_connection(load_rest_tracker, endpoint)
        db = client.get_database(database)
        conversations = db.get_collection(collection)
        users = []
        month_as_int = HistoryServerUtils.get_month_as_int(month)
        try:
            users = list(
                conversations.aggregate([{"$unwind": {"path": "$events", "includeArrayIndex": "arrayIndex"}},
                                         {"$match": {"events.event": {"$in": ["user", "bot"]},
                                                     "events.timestamp": {
                                                         "$gte": HistoryServerUtils.get_timestamp_previous_month(
                                                             month_as_int)}}},
                                         {"$group": {"_id": "$sender_id",
                                                     "latest_event_time": {"$first": "$latest_event_time"},
                                                     "events": {"$push": "$events"},
                                                     "allevents": {"$push": "$events"}}},
                                         {"$unwind": "$events"},
                                         {"$project": {
                                             "_id": 1,
                                             "events": 1,
                                             "latest_event_time": 1,
                                             "following_events": {
                                                 "$arrayElemAt": [
                                                     "$allevents",
                                                     {"$add": [{"$indexOfArray": ["$allevents", "$events"]}, 1]}
                                                 ]
                                             }
                                         }},
                                         {"$project": {
                                             "latest_event_time": 1,
                                             "user_timestamp": "$events.timestamp",
                                             "bot_timestamp": "$following_events.timestamp",
                                             "user_event": "$events.event",
                                             "bot_event": "$following_events.event",
                                             "time_diff": {
                                                 "$subtract": ["$following_events.timestamp", "$events.timestamp"]
                                             }
                                         }},
                                         {"$match": {"user_event": "user", "bot_event": "bot"}},
                                         {"$group": {"_id": "$_id",
                                                     "latest_event_time": {"$first": "$latest_event_time"},
                                                     "steps": {"$sum": 1}, "time": {"$sum": "$time_diff"}}},
                                         {"$project": {
                                             "sender_id": "$_id",
                                             "_id": 0,
                                             "steps": 1,
                                             "time": 1,
                                             "latest_event_time": 1,
                                         }}
                                         ], allowDiskUse=True))
        except Exception as e:
            logger.info(e)
        finally:
            client.close()
        return users
