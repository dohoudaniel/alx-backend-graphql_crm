import datetime
import asyncio
from gql import gql, Client
from gql.transport.requests import RequestsHTTPTransport


def log_crm_heartbeat():
    now = datetime.datetime.now().strftime("%d/%m/%Y-%H:%M:%S")
    message = f"{now} CRM is alive"

    # Log to file (append mode)
    with open("/tmp/crm_heartbeat_log.txt", "a") as f:
        f.write(message + "\n")

    # Optional: check GraphQL hello query using gql
    try:
        transport = RequestsHTTPTransport(
            url="http://localhost:8000/graphql", verify=True, retries=3
        )
        client = Client(transport=transport, fetch_schema_from_transport=True)

        query = gql("{ hello }")

        # gql client is async, so we wrap in asyncio
        result = asyncio.run(client.execute_async(query))
        hello_value = result.get("hello", "No response")

        with open("/tmp/crm_heartbeat_log.txt", "a") as f:
            f.write(f"{now} GraphQL hello -> {hello_value}\n")

    except Exception as e:
        with open("/tmp/crm_heartbeat_log.txt", "a") as f:
            f.write(f"{now} GraphQL heartbeat failed: {e}\n")


def update_low_stock():
    now = datetime.datetime.now().strftime("%d/%m/%Y-%H:%M:%S")

    try:
        # Set up gql client
        transport = RequestsHTTPTransport(
            url="http://localhost:8000/graphql", verify=True, retries=3
        )
        client = Client(transport=transport, fetch_schema_from_transport=True)

        # Define mutation
        mutation = gql(
            """
            mutation {
                updateLowStockProducts {
                    success
                    updatedProducts {
                        name
                        stock
                    }
                }
            }
            """
        )

        # Execute mutation
        result = asyncio.run(client.execute_async(mutation))
        data = result.get("updateLowStockProducts", {})
        updated_products = data.get("updatedProducts", [])

        # Log results
        with open("/tmp/low_stock_updates_log.txt", "a") as f:
            f.write(f"{now} {data.get('success', 'No message')}\n")
            for product in updated_products:
                f.write(
                    f"{now} Updated {product['name']} -> New stock: {product['stock']}\n"
                )

    except Exception as e:
        with open("/tmp/low_stock_updates_log.txt", "a") as f:
            f.write(f"{now} Stock update failed: {e}\n")
