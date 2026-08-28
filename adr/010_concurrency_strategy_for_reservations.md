# ADR 010: Concurrency Strategy for Ticket Reservations — Pessimistic Locking

## Status

Accepted

## Context

EventHub's reservation system allows multiple customers to reserve tickets for the same event simultaneously. During popular events or flash sales, many concurrent requests will compete for a limited pool of tickets. Without a correct concurrency strategy, any of the following can occur:

1. **Overselling**: Two requests read the same `reserved_quantity` value (e.g. 90/100), both decide 10 more tickets are available, and both succeed — resulting in 110 reserved tickets against a cap of 100.
2. **Counter drift**: The denormalized `reserved_quantity` and `sold_quantity` columns on `ticket_types` drift out of sync with the actual number of `Reservation` rows, making availability checks unreliable.
3. **Lost updates**: A `SELECT` reads a stale value that has already been overwritten by another transaction's `UPDATE`, and the new write is based on the stale read.

### Domain Constraints

- **PostgreSQL** is the production database (SQLite for tests/dev). Any solution must work correctly with PostgreSQL's MVCC and transaction semantics.
- **Async SQLAlchemy**: All database operations use `AsyncSession`. The concurrency strategy must be compatible with async session management (no thread-local state assumptions).
- **No external coordination service**: We do not run Redis (yet) or any distributed lock manager. The solution must work with database-level primitives only.
- **Idempotency**: Network retries from clients (mobile apps, unreliable networks) must not create duplicate reservations. A failed response followed by a retry should return the existing reservation, not create a second one.
- **Expiry**: Pending reservations that are not confirmed within a time window must be automatically released, returning tickets to the available pool.

### Design Space

We evaluated three families of approaches: optimistic locking, pessimistic locking, and application-level serialization.

## Decision

We use **pessimistic locking via `SELECT … FOR UPDATE`** on the `ticket_types` row for all write operations that modify reservation state or ticket counters.

### How It Works

Every write operation in `ReservationRepository` that affects ticket availability follows this pattern:

```
BEGIN
  SELECT * FROM ticket_types WHERE id = ? FOR UPDATE   -- acquire row-level lock
  -- business checks (availability, sale window, status)
  UPDATE ticket_types SET reserved_quantity = ? WHERE id = ?
  INSERT INTO reservations (…) VALUES (…)
COMMIT                                           -- release lock
```

The `FOR UPDATE` lock is held from the `SELECT` until `COMMIT`. Any other transaction attempting to lock the same `ticket_types` row will block until the first transaction commits. This serializes all concurrent reservation attempts for the same ticket type.

### Where It Applies

| Operation | Locks `ticket_types`? | Counter Change |
|---|---|---|
| `create()` | Yes | `reserved_quantity += quantity` |
| `cancel()` | Yes | `reserved_quantity -= quantity` |
| `confirm()` | Yes | `reserved_quantity -= quantity`, `sold_quantity += quantity` |
| `expire()` | Yes | `reserved_quantity -= quantity` |
| `get_by_id()` | No (read-only) | — |
| `list_by_user()` | No (read-only) | — |

### Idempotency Handling

A unique `idempotency_key` column on the `reservations` table prevents duplicate reservations from network retries. The `create()` method checks for an existing reservation with the same key before acquiring the lock:

1. Look up existing reservation by `idempotency_key` (no lock needed).
2. If found and in a terminal state (`EXPIRED` or `CANCELLED`), reject with an error — the client must generate a new key.
3. If found and still `PENDING` or `CONFIRMED`, return it as-is (safe retry).
4. If not found, proceed with the locked write path.

### Expiry via Background Worker

A background worker (planned for `app/workers/`) periodically queries for pending reservations whose `expires_at < now()` and transitions them to `EXPIRED`. The worker uses the same `expire()` repository method, which acquires the `FOR UPDATE` lock before decrementing `reserved_quantity`. This means the worker and customer-facing cancel operations are serialized against each other — no counter drift is possible.

## Consequences

### Positive

- **No overselling is possible**: The `FOR UPDATE` lock ensures only one transaction can read and modify a given `ticket_types` row at a time. The availability check (`reserved_quantity + quantity <= total_quantity`) and the counter update happen within the same locked transaction, so the check is always against the latest value.
- **Counter consistency is guaranteed**: Both the counter update and the reservation status change are committed atomically. If the transaction fails (e.g., constraint violation, connection drop), both are rolled back. There is no window where the counter is updated but the reservation row is not (or vice versa).
- **Simple mental model**: Developers only need to remember one rule — "lock the `ticket_types` row before modifying counters." There is no version tracking, no retry loop, no conflict resolution logic.
- **No external dependencies**: The strategy uses only PostgreSQL's built-in row-level locking. No Redis, no ZooKeeper, no application-level mutex.
- **Works with async SQLAlchemy**: `SELECT … FOR UPDATE` is a standard SQLAlchemy construct that works identically in sync and async modes.
- **Graceful degradation under contention**: Under heavy load, concurrent requests for the same ticket type queue up at the database level. They do not fail, spin, or cause application-level errors — they simply wait for the lock. PostgreSQL's lock wait timeout (default: no timeout) means requests will eventually succeed unless the holding transaction is stuck.

### Negative

- **Lock contention on popular ticket types**: For a single ticket type, all reservation requests are serialized. If 100 customers try to reserve the same VIP ticket type simultaneously, they are processed one at a time. The lock hold time is short (a single transaction: one SELECT + one UPDATE + one INSERT + COMMIT), so each request completes in milliseconds, but throughput is capped by the lock acquisition rate.
- **No partitioning across ticket types**: Locks are per-`ticket_types` row, so reservations for *different* ticket types do not contend with each other. However, all reservations for the *same* ticket type share a single lock. This is acceptable for EventHub's scale (hundreds to low thousands of concurrent requests per ticket type) but would become a bottleneck at massive scale (tens of thousands per second for the same ticket).
- **Potential for long-held locks**: If a transaction acquires the `FOR UPDATE` lock and then performs slow operations (e.g., an external API call) before committing, other transactions are blocked. The current implementation only performs database operations within the locked section, so this is not a risk — but future developers must be aware of this constraint.
- **Not testable with SQLite**: SQLite does not support `SELECT … FOR UPDATE` (it silently ignores the clause). Unit tests using in-memory SQLite cannot verify locking behavior. Concurrency correctness must be verified through integration tests against PostgreSQL or through code review.

## Alternatives Considered

| Approach | How It Works | Why It Was Rejected |
|---|---|---|
| **Optimistic locking** (version column) | Add an integer `version` column to `ticket_types`. Read the current version, perform the availability check, then `UPDATE … WHERE version = ?`. If zero rows are affected, retry from the beginning. | Correct, but requires a retry loop with a maximum retry count. Under high contention, many transactions conflict and retry, wasting database work. The retry logic adds complexity to every write path and makes error messages harder to reason about ("too many retries" vs. a clean "not enough tickets"). Also, the counter update is a read-then-write pattern that is inherently racy without a lock. |
| **Application-level mutex / semaphore** | Use an `asyncio.Lock` per ticket type ID in the Python process. | Only works within a single process. In production with multiple Uvicorn workers (or multiple pod replicas), each process has its own lock state — no cross-process coordination. Would need to be combined with a distributed lock (Redis) for correctness, adding an external dependency.
| **Redis distributed lock** (RedLock) | Acquire a Redis lock before performing the database transaction. | Adds Redis as a hard dependency for the reservation flow. Introduces a new failure mode: Redis is available but PostgreSQL is not (or vice versa). Lock expiry in Redis creates a window where the lock is released but the database transaction is still in progress. Correct distributed locking is notoriously difficult to implement. |
| **Database-level advisory locks** | `SELECT pg_advisory_lock(ticket_type_id)` before the transaction. | Functionally equivalent to `FOR UPDATE` for our use case, but advisory locks are not tied to the row being modified. If a developer acquires an advisory lock but forgets to release it (or the application crashes), the lock persists until the connection is closed. `FOR UPDATE` locks are automatically released on commit/rollback, which is safer. Advisory locks also do not show up in `pg_locks` with the same clarity as row-level locks, making debugging harder. |
| **Serialized via queue** | All reservation requests go into a message queue (e.g., RabbitMQ) and are processed sequentially per ticket type. | Correct and scales well, but adds significant infrastructure complexity (a message broker, consumer processes, dead-letter queues, delivery guarantees). Overkill for EventHub's current scale. Can be adopted later if the application outgrows database-level locking. |
| **Atomic UPDATE with WHERE clause** | `UPDATE ticket_types SET reserved_quantity = reserved_quantity + ? WHERE id = ? AND reserved_quantity + ? <= total_quantity` — no SELECT needed. | Clever and avoids locks entirely, but has several problems: (1) we cannot check the sale window (`sales_start_at` / `sales_end_at`) without a separate SELECT; (2) we cannot return the updated row with relationship data for the response without an additional SELECT; (3) the idempotency check still requires a prior SELECT, which reintroduces the race condition between the check and the UPDATE. Combining these would result in a complex CTE or stored procedure that is harder to maintain than the straightforward `FOR UPDATE` approach. |

## Date

2026-08-28
