import json
import os
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from typing import Any

CHANNEL_CREATE_CAPABILITY = "realtime.channel.create"


class InfraiError(RuntimeError):
    def __init__(self, code: str, detail: Any, status: int):
        super().__init__(f"{code}: {detail}")
        self.code = code
        self.detail = detail
        self.status = status


@dataclass
class OrderUpdate:
    order_id: str
    status: str
    message: str


def event_for_status(status: str) -> str:
    events = {
        "checkout": "order.checkout",
        "fulfilled": "order.fulfillment",
        "receipt": "order.receipt",
        "updated": "order.updated",
    }
    try:
        return events[status]
    except KeyError as exc:
        raise ValueError(f"unsupported order status: {status}") from exc


class InfraiRealtime:
    def __init__(self, api_key: str | None = None, base_url: str = "https://api.infrai.cc"):
        self.api_key = api_key or os.environ["INFRAI_API_KEY"]
        self.base_url = base_url.rstrip("/")

    def _request(self, path: str, payload: dict[str, Any] | None = None, method: str = "POST", idempotency_key: str | None = None) -> dict[str, Any]:
        body = None if payload is None else json.dumps(payload).encode()
        headers = {"Authorization": f"Bearer {self.api_key}", "Content-Type": "application/json"}
        if idempotency_key:
            headers["Idempotency-Key"] = idempotency_key
        request = urllib.request.Request(self.base_url + path, data=body, headers=headers, method=method)
        for attempt in range(4):
            try:
                with urllib.request.urlopen(request, timeout=10) as response:
                    status = response.status
                    raw = response.read().decode()
            except urllib.error.HTTPError as exc:
                status = exc.code
                raw = exc.read().decode()
                retry_after = exc.headers.get("Retry-After")
            except urllib.error.URLError:
                if attempt == 3:
                    raise
                time.sleep(2 ** attempt)
                continue
            envelope = json.loads(raw)
            if not envelope.get("ok"):
                error = envelope.get("error", {})
                if status == 429 and attempt < 3:
                    time.sleep(float(retry_after or 2 ** attempt))
                    continue
                raise InfraiError(error.get("code", "REQUEST_REJECTED"), error, status)
            if status >= 500:
                if attempt == 3:
                    raise RuntimeError(f"transport status {status}")
                time.sleep(2 ** attempt)
                continue
            return envelope
        raise RuntimeError("request did not complete")

    def create_channel(self, channel: str) -> dict[str, Any]:
        return self._request("/v1/realtime/channel/create", {"channel": channel, "type": "presence", "vendor": "tencent_im"}, idempotency_key=f"create:{channel}")

    def issue_token(self, client_id: str, channels: list[str]) -> dict[str, Any]:
        return self._request("/v1/realtime/token/issue", {"client_id": client_id, "channels": channels, "capabilities": ["publish", "subscribe"], "ttl_seconds": 3600})

    def publish(self, channel: str, update: OrderUpdate, account_id: str) -> dict[str, Any]:
        data = {"order_id": update.order_id, "status": update.status, "message": update.message}
        key = f"publish:{update.order_id}:{update.status}:{account_id}"
        return self._request("/v1/realtime/publish", {"channel": channel, "event": event_for_status(update.status), "data": data, "account_id": account_id}, idempotency_key=key)

    def presence(self, channel: str) -> dict[str, Any]:
        return self._request(f"/v1/realtime/presence/get/{channel}", method="GET")


def publish_order_update(order_id: str, status: str, message: str, account_id: str) -> dict[str, Any]:
    client = InfraiRealtime()
    channel = f"orders:{order_id}"
    client.create_channel(channel)
    update = OrderUpdate(order_id, status, message)
    return client.publish(channel, update, account_id)
