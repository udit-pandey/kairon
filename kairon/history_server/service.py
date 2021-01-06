from fastapi import FastAPI, Request
from fastapi.security.utils import get_authorization_scheme_param
from starlette.middleware.cors import CORSMiddleware
from starlette.responses import JSONResponse

from .exceptions import HistoryServerException
from .history import HistoryServer, HistoryServerUtils
from .models import HistoryMonth, HistoryMonthEnum

from .models import Response

app = FastAPI()
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
    expose_headers=["content-disposition"],
)


@app.middleware("http")
async def check_auth(request: Request, call_next):
    """Checking auth token"""
    authorization: str = request.headers.get("Authorization")
    environment = HistoryServerUtils.load_environment()
    _, param = get_authorization_scheme_param(authorization)
    expected_token = ''
    if environment["tracker_endpoint"]['token'] is not None:
        expected_token = environment["tracker_endpoint"]['token'].strip()
    if param != expected_token:
        response = JSONResponse(
            Response(success=False, error_code=422, message="Invalid auth token").dict())
    else:
        response = await call_next(request)
    return response


@app.exception_handler(HistoryServerException)
async def app_exception_handler(request, exc):
    """ logs the HistoryServerException error detected and returns the
            appropriate message and details of the error """
    return JSONResponse(
        Response(success=False, error_code=422, message=str(exc)).dict()
    )


@app.get("/users", response_model=Response)
async def chat_history_users(month: HistoryMonth = HistoryMonthEnum.One):
    """
    Fetches the list of user who has conversation with the agent
    """
    users = HistoryServer.fetch_chat_users(month)
    return Response(data={"users": users})


@app.get("/users/{sender}", response_model=Response)
async def chat_history(sender: str, month: HistoryMonth = HistoryMonthEnum.One):
    """
    Fetches the list of conversation with the agent by particular user
    """
    history = HistoryServer.fetch_chat_history(sender, month)
    return Response(data={"history": history})


@app.get("/metrics/users", response_model=Response)
async def user_with_metrics(month: HistoryMonth = HistoryMonthEnum.One):
    """
    Fetches the list of user who has conversation with the agent with steps anf time
    """
    users = HistoryServer.user_with_metrics(month)
    return Response(data={"users": users})


@app.get("/metrics/fallback", response_model=Response)
async def visitor_hit_fallback(month: HistoryMonth = HistoryMonthEnum.One):
    """
    Fetches the number of times the agent hit a fallback (ie. not able to answer) to user queries
    """
    fallback_count, total_count = HistoryServer.visitor_hit_fallback(month)
    return Response(data={"fallback_count": fallback_count, "total_count": total_count})


@app.get("/metrics/conversation/steps", response_model=Response)
async def conversation_steps(month: HistoryMonth = HistoryMonthEnum.One):
    """
     Fetches the number of conversation steps that took place in the chat between the users and the agent
     """
    conversation_steps = HistoryServer.conversation_steps(month)
    return Response(data={"conversation_steps": conversation_steps})


@app.get("/metrics/conversation/time", response_model=Response)
async def conversation_time(month: HistoryMonth = HistoryMonthEnum.One):
    """
    Fetches the duration of the chat that took place between the users and the agent"""
    conversation_time = HistoryServer.conversation_time(month)
    return Response(data={"conversation_time": conversation_time})
