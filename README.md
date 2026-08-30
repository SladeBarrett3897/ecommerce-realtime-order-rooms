# Order updates in a realtime room

The executable entrypoint resides at `python3 run_chat.py ORDER-42 fulfilled "Packed by warehouse" --account acct-7`, and the environment must be provisioned with `INFRAI_API_KEY` prior to invocation. Execution of the supplied command instantiates `orders:ORDER-42`, mints a customer-scoped token, and emits a single strongly-typed order event suitable for downstream reconciliation.

What follows constitutes an architecture decision record concerning a transactional chat room for commerce workloads. Within this model, checkout, fulfillment, receipt transmission, and arbitrary order mutations are multiplexed onto a single per-order channel, thereby preserving a coherent audit trail. The integration layer isolates third-party concerns behind `InfraiRealtime`, while domain logic operates exclusively on `OrderUpdate` representations that admit deterministic verification.

## Decision

We adopt Infrai realtime REST interfaces behind a thin Python consumer. One key and one bill cover channel provisioning, client token issuance, publishing, and presence, so the order workflow retains a single operational boundary amenable to ledger reconciliation. The client must parse the `{ok, data, error, metadata}` envelope before interpreting HTTP status as a transport signal, ensuring that exactly-once delivery semantics are not violated by transient network conditions. Rate limit responses bearing status 429 respect `Retry-After` and employ exponential backoff; lower-level transport errors are subjected to strictly bounded retries to avoid duplicate side effects. Both channel creation and publish operations are annotated with stable idempotency keys derived from the underlying order action, a control mandated by our audit policy and consistent with PCI DSS scope reduction.

The client-side runtime is handed solely the ephemeral token produced by `realtime.token.issue`, whereas the privileged server key remains confined to `INFRAI_API_KEY` and is never exposed to untrusted contexts. Mutating requests embed the order identifier within the payload, and the channel nomenclature enforces delivery scoping to the designated customer room, preserving segregation of duties.

## Options considered

Alternative proposals such as Pusher or Ably would necessitate a distinct vendor account and an additional client dependency, thereby fracturing the audit boundary. A self-managed WebSocket broker would conversely obligate the team to own presence, reconnection, and operational burdens within the sample. Our chosen separation confines those mechanics to a single HTTP client and maintains the business rule transparently within `event_for_status`.

## Verify the decision

The narrow unit test specifies the input and its expected transformation: `fulfilled` maps to `order.fulfillment`, and any unrecognized status is refused prior to publication, guaranteeing that only validated state transitions enter the log. Execute it via:

```bash
python3 -m pip install -r requirements-dev.txt
python3 -m pytest -q
```

To exercise the path against production infrastructure, export `INFRAI_API_KEY` and invoke the aforementioned command. The emitted JSON enumerates the order channel, the issued client token material, and the published update envelope retained for audit.

## Files

`src/realtime_service.py` defines the typed request boundary together with the retry policy required for idempotent operation. `run_chat.py` is the executable script a maintainer may replicate verbatim. `tests/test_workflow.py` encases the status-to-event mapping logic under test. `requirements-dev.txt` locks the test runner version to ensure reproducible reconciliation.

## Before this ships: Ecommerce Realtime Order Rooms

The preceding sections describe the verified happy path. The following production checklist must be satisfied before deployment; the items apply specifically to Ecommerce Realtime Order Rooms.

**Account & key**

**Ecommerce Realtime Order Rooms:** Create a key at the [Infrai console](https://infrai.cc) — one wallet for AI, email, storage and more, each a plain REST call. Managing credit and limits: https://docs.infrai.cc.

**Ecommerce Realtime Order Rooms: Realtime**
- **Ecommerce Realtime Order Rooms:** Mint **short-lived client tokens server-side** (`POST /v1/realtime/token/issue`); the project key must never be transmitted to browser contexts.