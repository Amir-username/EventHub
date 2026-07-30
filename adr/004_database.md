# ADR-001: Use PostgreSQL as the Primary Database

**Status:** Accepted  
**Date:** 2026-07-30  

---

## Context and Problem Statement

EventHub is a scaled-down event management and ticketing platform. The system must support:

- **Customers** browsing published events, reserving tickets, and completing payments.
- **Admins** managing venues, events, and ticket inventory with transactional integrity.
- **External partners** pulling event data through a versioned, rate-limited API.

We need a primary database that supports complex relational data (events ↔ venues ↔ tickets ↔ orders), strong consistency for inventory and payments, and extensibility for future search or analytics needs.

## Decision Drivers

- **Relational data model**: Events, venues, tickets, orders, and payments have rich relationships and require referential integrity.
- **ACID compliance**: Ticket inventory and payment records must be strongly consistent to prevent overselling or double-charging.
- **Complex queries**: Admins need aggregations, filtering, and reporting across multiple entities.
- **JSON flexibility**: The public API serves versioned, semi-structured event data; we need to store and query schemaless payload fields without sacrificing relational rigor.
- **Operational maturity**: The team has deep operational experience with PostgreSQL.
- **Ecosystem**: Need robust tooling, driver support, and hosted options (AWS RDS, GCP Cloud SQL, etc.).

## Considered Options

| Option | Pros | Cons |
|---|---|---|
| **PostgreSQL** | Full ACID, rich relational + JSON support, mature ecosystem, excellent concurrency control, extensible (PostGIS, full-text search) | Horizontal write scaling requires effort (read replicas, partitioning, or external caches) |
| **MySQL** | Wide adoption, good performance | Weaker JSON querying, less strict default isolation, less expressive data types |
| **MongoDB** | Flexible schema, easy horizontal scaling | Weak transactional guarantees across collections, no native joins, risk of data inconsistency for inventory |
| **DynamoDB** | Serverless, massive scale, low latency | Complex relational modeling (single-table design), limited querying, eventual consistency concerns |
| **CockroachDB / YugabyteDB** | Distributed SQL, horizontal scaling | Higher operational complexity, smaller ecosystem, overkill at current scale |

## Decision

**We will use PostgreSQL as the primary database for EventHub.**

PostgreSQL satisfies our core requirement for strict consistency in ticket inventory and payment records while offering the flexibility to store and index JSON payloads for our public API. Its support for advanced features (row-level security, partial indexes, `FOR UPDATE` locks, CTEs) makes it the best fit for the admin and customer workflows described.

## Consequences

### Positive
- **Data integrity**: Foreign keys, constraints, and ACID transactions prevent overselling and ensure payment consistency.
- **Flexible schema**: JSONB columns allow versioned API payloads and future schema evolution without full migrations.
- **Rich querying**: Admins can run complex reports and aggregations natively.
- **Ecosystem**: Mature ORM support, migration tools, monitoring, and managed hosting options.

### Negative
- **Write scaling**: A single PostgreSQL instance may become a bottleneck if ticket sales spike massively. Mitigation: connection pooling (PgBouncer), read replicas for analytics, and table partitioning if needed.
- **Not a search engine**: Full-text search is adequate initially, but a dedicated search index (e.g., Elasticsearch, Meilisearch) may be added later for customer-facing event discovery.
- **No native horizontal sharding**: If we outgrow a single instance, we may need to evaluate Citus or migrate hot paths to a cache/queue layer.

## Mitigations

- Use **connection pooling** (PgBouncer or RDS Proxy) to handle burst traffic.
- Offload read-heavy API traffic to **read replicas** where stale data is acceptable.
- Cache hot event data in **Redis** to reduce database load for the public API.
- Partition high-volume tables (e.g., `orders`, `payments`) by time if growth demands it.