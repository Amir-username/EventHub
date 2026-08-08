# ADR 007: Pagination Strategy — Offset/Limit (Deferred Cursor Migration)

## Status

Accepted

## Context

EventHub exposes multiple list endpoints (events, venues, ticket types, users) that return paginated results. As the dataset grows — especially for events and ticket types during busy periods — the pagination strategy affects both **API correctness** and **database performance**.

We evaluated two primary approaches:

1. **Offset/Limit** — pass `offset` and `limit` query parameters; the database skips `offset` rows and returns `limit` rows.
2. **Cursor-Based (Keyset)** — pass a cursor derived from the last row's sort value (e.g., `starts_at` + `id`); the database uses a `WHERE col > cursor` condition.

Additional variants considered: **page-number based** (a convenience wrapper over offset), **seek method** (cursor with tie-breaker), and **ID-based sliding window**.

### Key Constraints

- The project is in **early development** — data volume is currently small and will grow gradually.
- Events and ticket types will see **frequent inserts** as the platform onboards organizers.
- Admin endpoints (users, venues) have **low write volume** and benefit from random page access.
- The frontend has not been built yet, so the pagination contract is still flexible.

## Decision

We will use **Offset/Limit pagination** for all list endpoints at this stage.

The response schema is consistent across all paginated endpoints:

```json
{
  "items": [...],
  "total": 47,
  "offset": 0,
  "limit": 20
}
```

This decision is **deferred, not final**. When data volume reaches a threshold where offset performance degrades or duplicate-row issues are observed in production, we will migrate high-traffic public endpoints (events, ticket types) to cursor-based pagination.

## Consequences

### Positive

- **Simplicity**: Offset/Limit is trivially understood by developers and API consumers. The `total` count enables the frontend to render page numbers and a total item count.
- **Random access**: Admins can jump directly to any page (e.g., page 50 of users) without iterating through previous pages.
- **Consistent contract**: Every paginated endpoint returns the same `Paginated*` schema (`items`, `total`, `offset`, `limit`), reducing cognitive load.
- **Low implementation cost**: No additional logic needed for cursor encoding, direction handling, or tie-breaking.
- **Adequate for current scale**: With fewer than ~10,000 rows per table, PostgreSQL handles `OFFSET` efficiently. Performance issues typically appear at 100,000+ rows.

### Negative

- **Duplicate rows on concurrent writes**: If a new record is inserted between page loads, all subsequent records shift by one. A user scrolling from page 1 to page 2 may see the last item of page 1 repeated as the first item of page 2.
- **Degraded performance at high offsets**: `OFFSET 100,000 LIMIT 20` requires PostgreSQL to scan and discard 100,000 rows before returning results. This is O(offset) rather than O(1).
- **Inaccurate total count**: `SELECT COUNT(*)` on a large, frequently-updated table is approximate (PostgreSQL does not use row-level locks for COUNT). The `total` may be stale by the time the client receives it.

## Migration Plan

When offset pagination becomes a bottleneck, the migration path is:

1. **Add cursor parameters alongside offset/limit** — e.g., `?cursor=eyJpZCI6NDJ9&limit=20`. Old clients using `offset` continue to work.
2. **Convert high-traffic public endpoints first** — `GET /events/public` (ordered by `starts_at, id`) and `GET /ticket-types/public/events/{event_id}` (ordered by `id`).
3. **Keep offset/limit on admin endpoints** — these have low write volume and benefit from random page access.
4. **Deprecate offset/limit on public endpoints** after a grace period.

### Which Endpoints Will Migrate

| Endpoint | Current Strategy | Future Strategy | Reason |
|---|---|---|---|
| `GET /events/public` | Offset/Limit | Cursor (`starts_at, id`) | High read volume, frequent inserts |
| `GET /ticket-types/public/events/{id}` | Offset/Limit | Cursor (`id`) | Tied to event, but still public-facing |
| `GET /venues/public` | Offset/Limit | Keep Offset/Limit | Low write volume, small dataset |
| `GET /admin/users` | Offset/Limit | Keep Offset/Limit | Admin panel, needs page jumping |
| `GET /admin/events` | Offset/Limit | Cursor (`id`) | May grow large |

## Alternatives Considered

| Strategy | Why it was rejected (for now) |
|---|---|
| **Cursor-Based (Keyset)** | Ideal for correctness and performance at scale, but adds complexity (cursor encoding, no random page access, bidirectional navigation) that is unnecessary at current data volumes. Will be adopted when the tradeoff shifts. |
| **Page Number** | A cosmetic wrapper over offset. Has the same performance and duplication issues while hiding the underlying mechanism. No benefit over explicit offset. |
| **ID-Based Sliding Window** | Extremely fast, but only supports forward traversal. Not suitable for admin endpoints that need random access. Could be used for specific infinite-scroll features in the future. |

## Date

2026-08-08