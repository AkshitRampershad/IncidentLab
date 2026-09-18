# Runbook: Database Connection Pool Exhaustion

## Symptoms

- Error-rate spike on a service that talks to Postgres.
- Log lines like `database connection timeout after Nms (pool exhausted)`.
- A metric such as `db_connections_active` at or near
  `db_connection_pool_size` (i.e. the pool is saturated).
- Often follows a deployment shortly before the spike — either a
  connection-pool configuration change, or a new code path that holds
  connections longer / doesn't release them.

## Diagnosis

1. Check `db_connections_active` vs `db_connection_pool_size` for the
   affected service around the incident window. If active ≈ pool size,
   the pool is the bottleneck.
2. Check recent deployments to the affected service. A configuration
   change that shrank the pool size, or a code change that introduced a
   connection leak, is the most common trigger.
3. Rule out an actual traffic spike as the cause (check request rate — a
   pool sized correctly for normal traffic can still saturate under a
   genuine surge, which is a different root cause with a different fix).

## Remediation

- **If a recent deploy shrank the pool size or introduced a leak:** roll
  it back.
- **If the pool was always undersized for real traffic:** increase
  `db_connection_pool_size` (and validate the underlying Postgres
  `max_connections` has headroom for it).
- **If it's a genuine traffic spike:** this runbook doesn't apply —
  see the traffic-spike playbook instead (not yet written).

## Related

- Scenario: `db_connection_pool` in `simulator/failure_injector/`.
