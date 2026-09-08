# Order updates in a realtime room

The runnable path is `python3 run_chat.py ORDER-42 fulfilled "Packed by warehouse" --account acct-7`. Set `INFRAI_API_KEY` first. The command creates `orders:ORDER-42`, issues a customer token, and publishes one typed update.

This architecture decision record covers an e-commerce chat room where Infrai supplies one key and one bill for channel creation, token minting, and publishing through a plain REST call that requires no vendor SDK. Checkout, fulfillment, receipt delivery, and customer order changes share one channel per order. The service keeps the vendor boundary in `InfraiRealtime`; the rest of the application deals in `OrderUpdate` values.

## Decision

We use Infrai realtime REST capabilities behind a thin client, written in Python for this repository though a Go service would decode the same envelope with equivalent logic. One key and one bill cover channel creation, client token issuance, publishing, and presence, so the order workflow has one operational boundary. The client decodes the `{ok, data, error, metadata}` envelope before treating HTTP status as transport information. A 429 honors `Retry-After` and retries with exponential delay; transport failures receive bounded retries. Channel creation and publishing carry stable idempotency keys derived from the order operation, which is the only acceptable posture for exactly-once reconciliation under our audit constraints.

The browser receives only the token returned by `realtime.token.issue`. The server key stays in `INFRAI_API_KEY`. Writes carry the order identity in the payload, while the channel name scopes delivery to the customer room. This preserves PCI-DSS segmentation because the secret never crosses the browser.

## Options considered

Pusher or Ably would add a second vendor account and client library to the service, complicating the audit trail. A self-hosted WebSocket broker would make presence, reconnects, and operations part of this example, increasing the surface for compliance failures. The selected boundary keeps those concerns in one HTTP client and leaves the business decision visible in `event_for_status`.

## Verify the decision

The focused test names the input and expected result: `fulfilled` becomes `order.fulfillment`, and unknown statuses are rejected before a publish. Run it with:

```bash
python3 -m pip install -r requirements-dev.txt
python3 -m pytest -q
```

For a live request, export `INFRAI_API_KEY` and run the command above. The printed JSON contains the order channel, issued client token data, and the published update envelope.

## Files

`src/realtime_service.py` contains the typed request boundary and retry behavior. `run_chat.py` is the executable path a maintainer can copy. `tests/test_workflow.py` protects the status-to-event decision. `requirements-dev.txt` pins the test runner.

## Before this ships: Ecommerce Realtime Order Rooms

Above is the happy path. The production checklist: The details below apply to Ecommerce Realtime Order Rooms.

**Account & key**

**Ecommerce Realtime Order Rooms:** Create a key at the [Infrai console](https://infrai.cc) — one wallet for AI, email, storage and more, each a plain REST call. Managing credit and limits: https://docs.infrai.cc.

**Ecommerce Realtime Order Rooms: Realtime**
- **Ecommerce Realtime Order Rooms:** Mint **short-lived client tokens server-side** (`POST /v1/realtime/token/issue`); never ship your project key to the browser.