import json
import logging
import os

import azure.functions as func
from azure.cosmos import CosmosClient
from azure.cosmos.partition_key import PartitionKey

COSMOS_URL = os.environ.get("COSMOS_URL")
COSMOS_KEY = os.environ.get("COSMOS_KEY")
DATABASE_ID = os.environ.get("COSMOS_DATABASE")
CONTAINER_ID = os.environ.get("COSMOS_CONTAINER")

app = func.FunctionApp(http_auth_level=func.AuthLevel.ANONYMOUS)


def db_properties(database):
    properties = database.read()
    print(json.dumps(properties, indent=True))

def items_read(container, max_item_count=100):
    items = list(container.read_all_items(max_item_count))

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
@app.route(route="prompt")
def main(req: func.HttpRequest) -> func.HttpResponse:
    logging.info("DokTool - Prompts Management")

    id = req.params.get("id")

    try:
        body = req.get_json()
    except Exception:
        pass

    #
    client: CosmosClient = CosmosClient(COSMOS_URL, {"masterKey": COSMOS_KEY})
    db = client.create_database_if_not_exists(id=DATABASE_ID)
    container = db.create_container_if_not_exists(id=CONTAINER_ID, partition_key=PartitionKey(path='/id', kind='Hash'))

    method = req.method
    logging.info(f"DokTool - Prompts Management: handle '{method}")

    match method:
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
    result = {"method": method, "data": items}
    return func.HttpResponse(json.dumps(result, indent=4), status_code=200)
