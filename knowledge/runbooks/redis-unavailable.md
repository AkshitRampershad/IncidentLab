# Runbook: Redis Unavailable

## Symptoms

- `cache_hit_rate` collapses (near 0) while `error_rate` stays normal.
- Elevated `latency_p99_ms`, but the service keeps serving requests
  successfully — not an outage, a slowdown.
- Log lines like `redis connection refused: falling through to primary
  datastore`.

## Diagnosis

1. Check `cache_hit_rate` for the affected service around the incident
   window. A collapse to near-zero, not a gradual decline, points to
   Redis being unreachable rather than a normal cache-warming dip.
2. Confirm `error_rate` is *not* elevated. If it is, this isn't a pure
   cache-layer incident — the fallback path itself may be failing (e.g.
   the primary datastore is also under strain), which is a different,
   more serious problem.
3. Check Redis's own health directly (connection count, memory, process
   status) rather than inferring it only from checkout's metrics.

## Remediation

- Restart or fail over the Redis instance/cluster.
- No checkout-side rollback is needed if `error_rate` stayed normal — the
  fallback-to-primary path did its job. Verify `latency_p99_ms` recovers
  once Redis is back, and watch primary-datastore load in the meantime
  (a prolonged outage means 100% of traffic that would've hit cache is
  now hitting the primary datastore instead).

## Related

- Scenario: `redis_unavailable` in `simulator/failure_injector/`.
- See `knowledge/architecture/checkout-service.md` for why checkout
  degrades gracefully on Redis loss instead of failing outright.
