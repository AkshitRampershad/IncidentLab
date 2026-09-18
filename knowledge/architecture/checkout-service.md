# Architecture: checkout service

## Dependencies

- **Postgres** — the primary datastore for cart and order state, accessed
  through a connection pool. Pool size is configured per deployment, not
  auto-scaled — a config change that shrinks it takes effect immediately
  on the next deploy.
- **Redis** — cache layer for cart/session lookups. checkout is designed
  to degrade gracefully on Redis unavailability (falls through to
  Postgres on a cache miss or eviction), so Redis issues alone should not
  cause checkout errors — they show up as elevated latency, not failures.
- **auth service** — validates request tokens. checkout does not manage
  its own auth; token expiry/format changes live in the auth service, not
  here.

## Failure characteristics

- Because checkout falls through to Postgres on any Redis miss, a Redis
  problem alone tends to be a distractor for checkout error-rate
  incidents, not a root cause — genuine checkout outages are far more
  often a Postgres/connection-pool issue than a cache issue.
