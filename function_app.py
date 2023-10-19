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


def items_read(container, max_item_count=100):
    items = list(container.read_all_items(max_item_count))

    for item in items:
        print(item)


    return items

def item_create(container, item):
    response = container.create_item(body=item)

    return {
        'item': item,
        'created': response
    }

def item_read(container, doc_id):
    response = container.read_item(item=doc_id, partition_key=doc_id)

    return response

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
    response = container.delete_item(item=doc_id, partition_key=doc_id)

    response = list(container.read_all_items())

    return {
        'items': response,
        'deleted': doc_id
    }

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

    return func.HttpResponse(json.dumps(result, indent=4), status_code=200)

def handleResponse(response: Response = None, message: str = None, additional = None, config = None):
    """

    """
    result = {}
    result["status"] = STATE_OK

    if message is not None and message != "":
        result["message"] = message

    result["responses"] = response

    if additional is not None:
        result.update(additional)

    if config is not None:
        result["config"] = config

    return func.HttpResponse(json.dumps(result, indent=4), status_code=200)

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
            items = item_create(container, body)
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
    return handleResponse(items, additional=None, config=None)
