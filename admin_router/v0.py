from fastapi import APIRouter, Request, Response, BackgroundTasks
import json
import importlib
from fastapi.responses import JSONResponse
from database import mysql as db_mysql
import time
import base64
import datetime
from database import session_helper
from tools import calculate

app_messages_verify = session_helper.Session("admin_app_messages_verify") #服务端发出的消息，服务端验证使用
app_messages_to_client = session_helper.Session("admin_app_messages_to_client") #服务端发出的消息，客户端验证使用
client_messages_verify = session_helper.Session("client_messages_verify") #客户端发出的消息，服务端验证使用
client_messages_to_app = session_helper.Session("client_messages_to_app")

router = APIRouter(prefix="/v0",
                   responses={
                       404: {
                           "ret": 404,
                           "msg": "Not found"
                       },
                       500: {
                           "ret": 500,
                           "msg": "Server error"
                       },
                       400: {
                           "ret": 400,
                           "msg": "Bad request"
                       },
                       401: {
                           "ret": 401,
                           "msg": "UnAuthorized"
                       }
                   })


@router.post("/ping")
async def post_ping(request: Request):
    return JSONResponse({"ret": 0, "msg": "pong"})


@router.post("/east/addmessage")
async def post_addtask(request: Request, backgroundtasks: BackgroundTasks):
    #TODO add a message to task
    data = request.state.origin_data
    message_id = data["message_id"]
    source = data["source"]
    destination = data["destination"]
    message = data["message"]
    if type(message) == dict or type(message) == list:
        message = calculate.base64_encode(json.dumps(message, indent=0))
    if app_messages_verify.get(".".join([destination, source, message_id])) == None:
        app_messages_verify.add(".".join([destination, source, message_id]), message)
        app_messages_to_client.add(".".join([destination, source, message_id]), message)
    return JSONResponse({"ret": 0, "msg": "ok"})


@router.post("/east/addmessages")
async def post_addtasks(request: Request, backgroundtasks: BackgroundTasks):
    #TODO add multi tasks
    data = request.state.origin_data
    messages = data["messages"]
    for newmessage in messages:
        message_id = newmessage["message_id"]
        source = newmessage["source"]
        destination = newmessage["destination"]
        message = newmessage["message"]
        if type(message) == dict or type(message) == list:
            message = calculate.base64_encode(json.dumps(message, indent=0))
        if app_messages_verify.get(".".join([destination, source, message_id])) == None:
            app_messages_verify.add(".".join([destination, source, message_id]), message)
            app_messages_to_client.add(".".join([destination, source, message_id]), message)
    return JSONResponse({"ret": 0, "msg": "ok"})


@router.post("/east/getstatus")
async def post_status(request: Request, backgroundtasks: BackgroundTasks):
    #TODO get status
    data = request.state.origin_data
    message_id = data["message_id"]
    source = data["source"]
    destination = data["destination"]
    message = app_messages_verify.get(".".join([destination, source, message_id]))
    if message == None:
        return JSONResponse({"ret": 404, "msg": "Not found"})
    if type(message) == bytes:
        message = message.decode('utf-8')
    sign = calculate.sha512(".".join([message_id, destination, source, message]))
    return JSONResponse({"ret": 0, "msg": "ok", "sign": sign})


@router.post("/east/getmultistatus")
async def post_multi(request: Request, backgroundtasks: BackgroundTasks):
    data = request.state.origin_data
    messages = data["messages"]
    ret = {}
    for newmessage in messages:
        if newmessage["message_id"] == None:
            continue
        message_id = newmessage["message_id"]
        source = newmessage["source"]
        destination = newmessage["destination"]
        message = app_messages_verify.get(".".join([destination, source, message_id]))
        if message == None:
            continue
        if type(message) == bytes:
            message = message.decode('utf-8')
        sign = calculate.sha512(".".join(
            [message_id, destination, source, message]))
        ret[message_id] = sign
    return JSONResponse({"ret": 0, "msg": "ok", "signs": ret})


@router.post("/west/getmessages")
async def post_messages(request: Request, backgroundtasks: BackgroundTasks):
    #TODO get messages
    data = request.state.origin_data
    user_uuid = request.state.user_uuid
    messages = {}
    new_messages = client_messages_to_app.find(user_uuid)
    for new_message in new_messages:
        
        message = client_messages_to_app.get(new_message)
        message_id = new_message.split(".")[2]
        source = new_message.split(".")[1]
        destination = new_message.split(".")[0]
        if type(message) == bytes:
            message = message.decode('utf-8')
        messages[message_id] = {
            "destination": destination,
            "message": message,
            "source": source
        }
    return JSONResponse({"ret": 0, "msg": "ok", "messages": messages})


@router.post("/west/updatestatus")
async def post_updatestatus(request: Request,
                            backgroundtasks: BackgroundTasks):
    #TODO update status
    data = request.state.origin_data
    message_id = data["message_id"]
    source = data["source"]
    destination = request.state.user_uuid
    sign = data["sign"]
    message = client_messages_to_app.get(".".join([destination, source, message_id]))
    if message == None:
        return JSONResponse({"ret": 404, "msg": "Not found"})
    if type(message) == bytes:
        message = message.decode('utf-8')
    if calculate.sha512_verify(
            ".".join([message_id, destination, source, message]), sign):
        client_messages_to_app.remove(".".join([destination, source, message_id]))
        return JSONResponse({"ret": 0, "msg": "ok"})
    else:
        return JSONResponse({"ret": 401, "msg": "Sign Invalid"})


@router.post("/west/updatemultistatus")
async def post_updatemultistatus(request: Request,
                                 backgroundtasks: BackgroundTasks):
    data = request.state.origin_data
    destination = request.state.user_uuid
    messages = data["messages"]
    for newmessage in messages:
        message_id = newmessage["message_id"]
        sign = newmessage["sign"]
        source = newmessage["source"]
        message = client_messages_to_app.get(".".join([destination, source, message_id]))
        if message == None:
            continue
        if type(message) == bytes:
            message = message.decode('utf-8')
        if calculate.sha512_verify(
                ".".join([message_id, destination, source, message]), sign):
            client_messages_to_app.remove(".".join([destination, source, message_id]))
    return JSONResponse({"ret": 0, "msg": "ok"})
