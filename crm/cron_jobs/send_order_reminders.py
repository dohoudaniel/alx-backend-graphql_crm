#!/usr/bin/env python3

import sys
import asyncio
from datetime import datetime, timedelta
from gql import Client, gql
from gql.transport.aiohttp import AIOHTTPTransport

async def fetch_pending_orders():
    # GraphQL endpoint
    transport = AIOHTTPTransport(url="http://localhost:8000/graphql")
    client = Client(transport=transport, fetch_schema_from_transport=True)

    # Calculate date range (last 7 days)
    seven_days_ago = (datetime.now() - timedelta(days=7)).date().isoformat()

    # GraphQL query
    query = gql(
        """
        query GetRecentOrders($since: Date!) {
            orders(orderDate_Gte: $since, status: "PENDING") {
                id
                customer {
                    email
                }
            }
        }
        """
    )

    variables = {"since": seven_days_ago}

    try:
        result = await client.execute_async(query, variable_values=variables)
        orders = result.get("orders", [])

        # Log orders
        with open("/tmp/order_reminders_log.txt", "a") as log_file:
            for order in orders:
                log_file.write(
                    f"{datetime.now()}: Order {order['id']} -> {order['customer']['email']}\n"
                )

        print("Order reminders processed!")

    except Exception as e:
        sys.stderr.write(f"Error fetching orders: {e}\n")


if __name__ == "__main__":
    asyncio.run(fetch_pending_orders())
