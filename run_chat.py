import argparse
import json

from src.realtime_service import InfraiRealtime, OrderUpdate


def main() -> None:
    parser = argparse.ArgumentParser(description="Publish an order-room update")
    parser.add_argument("order_id")
    parser.add_argument("status", choices=["checkout", "fulfilled", "receipt", "updated"])
    parser.add_argument("message")
    parser.add_argument("--account", required=True)
    args = parser.parse_args()
    client = InfraiRealtime()
    channel = f"orders:{args.order_id}"
    client.create_channel(channel)
    token = client.issue_token(f"customer-{args.account}", [channel])
    result = client.publish(channel, OrderUpdate(args.order_id, args.status, args.message), args.account)
    print(json.dumps({"channel": channel, "client_token": token["data"], "published": result["data"]}, indent=2))


if __name__ == "__main__":
    main()
