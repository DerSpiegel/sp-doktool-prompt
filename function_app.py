import json
import logging
import os

import azure.functions as func
from azure.cosmos import CosmosClient
from azure.cosmos.partition_key import PartitionKey
from requests import Response

COSMOS_URL = os.environ.get("COSMOS_URL")
COSMOS_KEY = os.environ.get("COSMOS_KEY")
COSMOS_DATABASE = os.environ.get("COSMOS_DATABASE")
COSMOS_CONTAINER = os.environ.get("COSMOS_CONTAINER")

STATE_ERROR = "ERROR"
STATE_OK = "OK"

app = func.FunctionApp(http_auth_level=func.AuthLevel.ANONYMOUS)


def item_removeinternalfields(item):
     return {k:v for k,v in item.items() if not k.startswith("_")}

def items_read(container, max_item_count=100):
    items = []

    for item in list(container.read_all_items(max_item_count)):
        temp = item_removeinternalfields(item)
        items.append(temp)

    return items

def item_create(container, item):
    response = None

    try:
        temp = container.create_item(body=item)
        response = item_removeinternalfields(temp)

    except Exception as ex:
        message = ex.message.split('\r')[0]
        return STATE_ERROR, response, f"{message} {ex.reason}: {ex.status_code}"

    return STATE_OK, response, None

def item_read(container, doc_id):
    item = container.read_item(item=doc_id, partition_key=doc_id)
    temp = item_removeinternalfields(item)

    return temp

def item_update(container, doc_id, changes):
    olditem = item_read(container, doc_id)

    newitem = item_read(container, doc_id)
    newitem.update(changes)

    response = container.upsert_item(newitem)
    return {
        'item': olditem,
        'updated': response
    }

def item_delete(container, doc_id):
    # Ignore Ruff Linting: Local variable `deleted` is assigned to but never used
    # ruff: noqa: F841
    deleted = container.delete_item(item=doc_id, partition_key=doc_id)
    response = list(container.read_all_items())

    return response

def items_query(container,  doc_id = None, query="SELECT * FROM r"):
    # query = "SELECT * FROM r WHERE r.id=@id"
    response = container.query_items(
              query=query,
              parameters=[{"name": "@id", "value": doc_id}]
    )

    return response

#
#
#
def checkConfig():
    config = {}

    config = {
        "COSMOS_URL": COSMOS_URL,
        # "COSMOS_KEY": COSMOS_KEY,
        "COSMOS_DATABASE": COSMOS_DATABASE,
        "COSMOS_CONTAINER": COSMOS_CONTAINER,
    }

    reason = ""
    if COSMOS_URL is None:
        reason = " COSMOS_URL is missing"

    if COSMOS_KEY is None:
        reason = " COSMOS_KEY is missing"

    if COSMOS_DATABASE is None:
        reason = " COSMOS_DATABASE is missing"

    if COSMOS_CONTAINER is None:
        reason = " COSMOS_CONTAINER is missing"

    if reason:
        return STATE_ERROR, config

    return STATE_OK, config

#
#
#
def handleError(response: Response = None, message: str = None, exception: Exception = None, config = None):
    result = {}
    result["status"] = STATE_ERROR

    if message is not None and message != "":
        result["message"] = message
    elif response is not None:
        result["message"] = response['error']['message']

    if exception is not None:
        result["exception"] = str(exception)

    if response is not None:
        result["response"] = response

    if config is not None:
        result["config"] = config

    func.HttpResponse.mimetype = 'application/json'
    func.HttpResponse.charset = 'utf-8'

    return func.HttpResponse(json.dumps(result, indent=4), status_code=200)

def handleResponse(response: Response = None, message: str = None, additional = None, config = None):
    """

    """
    result = {}
    result["status"] = STATE_OK

    if message is not None and message != "":
        result["message"] = message

    result["data"] = response

    if additional is not None:
        result.update(additional)

    if config is not None:
        result["config"] = config

    func.HttpResponse.mimetype = 'application/json'
    func.HttpResponse.charset = 'utf-8'

    return func.HttpResponse(json.dumps(response, indent=4), status_code=200)

#
#
#
@app.route(route="prompt")
def main(req: func.HttpRequest) -> func.HttpResponse:
    logging.info("DokTool - Prompts Management")

    state, config = checkConfig()

    if state == STATE_ERROR:
        return handleError(message = "Error in  configuration", config=config)

    #
    id = req.params.get("id")

    try:
        body = req.get_json()
    except Exception:
        pass

    #
    try:
        client: CosmosClient = CosmosClient(COSMOS_URL, {"masterKey": COSMOS_KEY})
        db = client.create_database_if_not_exists(id=COSMOS_DATABASE)
        container = db.create_container_if_not_exists(id=COSMOS_CONTAINER, partition_key=PartitionKey(path='/id', kind='Hash'))
    except Exception as ex:
        return handleError(message = "Couild not connect to database", exception=ex, config=config)

    method = req.method
    logging.info(f"DokTool - Prompts Management: handle '{method}")

    state = STATE_OK

    match method:
        # GET:     Get all items or one item by ID
        # POST:    Create a new item
        # PUT:     Update a item
        # DELETE:  Delete a Item
        # HEAD:    Get all items without data (just ids)
        # OPTIONS: Show possible actions /API Links

        case "GET":
            if id is None:
                items = items_read(container)
            else:
                items = item_read(container, id)
        case "POST":
            state, items, message = item_create(container, body)
        case "PUT":
            items = item_update(container, id, body)
        case "DELETE":
            items = item_delete(container, id)
        case "HEAD":
            pass
        case "OPTIONS":
            pass
        case _:
            items = {}

    #
    # additional = {"method": method}
    if (state == STATE_OK):
        return handleResponse(items, additional=None, config=None)
    else:
        return handleError(message=message)
