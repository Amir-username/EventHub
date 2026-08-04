# ADR 006: JWT Signing Algorithm — RS256 over HS256

## Status

Accepted

## Context

EventHub's authentication layer uses JWT access tokens and refresh tokens to manage user sessions. The choice of signing algorithm impacts:

1. **Service topology**: EventHub is architected with separate concerns — the main API, a mock payment provider, background workers, and a planned external partner API (see ADR 001). These components may run as independent processes or services.
2. **Token verification distribution**: Any service that receives a JWT (API gateways, payment webhooks, worker queues, third-party integrations) must verify its signature.
3. **Key management posture**: We need to minimize the blast radius if a service is compromised.
4. **Future scalability**: The project roadmap includes rate-limited external APIs and webhook delivery systems that will need to validate tokens independently.

We evaluated **HS256** (HMAC with SHA-256, symmetric) and **RS256** (RSA with SHA-256, asymmetric).

## Decision

We will use **RS256** as the JWT signing algorithm for EventHub.

## Consequences

### Positive

- **Distributed verification without shared secrets**: With RS256, the private key is used only to *sign* tokens (on the auth service), while the public key is used to *verify* them. Background workers, the payment provider mock, webhook handlers, and external partner services can all validate tokens using only the public key. They never need access to the signing secret.
- **Reduced blast radius on key compromise**: If a verifying service (e.g., a worker or partner integration) is compromised, the attacker gains only the public key — which is useless for forging new tokens. With HS256, any service that verifies tokens must possess the shared secret, meaning a compromise of *any* verifier allows token forgery.
- **Key rotation without mass invalidation**: RS256 supports rotating the private signing key while retaining old public keys in a verification key set (JWKS). Existing user sessions remain valid during rotation. HS256 rotation forces all active sessions to re-authenticate because there is only one shared secret.
- **Alignment with external API strategy**: ADR 001 explicitly calls for a "versioned, rate-limited external API for third-party partners." RS256 allows us to publish a `.well-known/jwks.json` endpoint so partners can verify tokens using standard OIDC/JWT libraries without us sharing secrets over secure channels.
- **Docker Secrets friendly**: The private key is mounted as a Docker secret (`/run/secrets/private_key.pem`), readable only by the API container. The public key can be exposed via an HTTP endpoint or baked into downstream service images without security risk.
- **Audit and compliance posture**: Asymmetric signing is the industry standard for multi-service architectures. It simplifies future compliance requirements (SOC 2, PCI-DSS adjacent) by clearly separating signing and verification duties.

### Negative

- **Slightly larger token size**: RSA signatures are larger than HMAC signatures (~256 bytes vs ~32 bytes). This adds marginal overhead to HTTP headers and Redis cache storage. For EventHub's payload size, this is negligible.
- **Key generation complexity**: We must generate and securely store an RSA key pair (2048-bit minimum) instead of a single random string. We have addressed this via the `scripts/` directory and Docker Secrets.
- **Performance cost**: RSA signing and verification are computationally slower than HMAC. In benchmarks, RS256 verification is ~10× slower than HS256. However, EventHub's expected traffic (even during flash sales) is well within the throughput of a single CPU core for RSA operations. If this becomes a bottleneck, we can cache verified token payloads in Redis or switch to ES256 (ECDSA) later.
- **Library dependency**: We rely on `cryptography` (already in `pyproject.toml`) for RSA operations, adding a compiled dependency. This is acceptable given the security benefits.

## Alternatives Considered

| Algorithm | Why it was rejected |
|---|---|
| **HS256** | Simple and fast, but requires the *same* secret for signing and verification. Every service that validates tokens (workers, payment mock, future partner gateways) would need the shared secret. This violates the principle of least privilege and means any compromised verifier can forge tokens for any user. Key rotation also invalidates all active sessions. |
| **ES256** (ECDSA) | Offers the same asymmetric benefits as RS256 with smaller signatures and faster verification. It was a close contender. However, RS256 has broader library support across languages (critical for third-party partner integrations) and is more familiar to the team. We can migrate to ES256 in the future if token size or verification throughput becomes a constraint. |
| **EdDSA** (Ed25519) | Modern, fast, and secure. Limited support in some legacy JWT libraries that partners may use. We may revisit this as the ecosystem matures. |
| **PS256** (RSA-PSS) | More secure padding scheme than RS256's PKCS#1 v1.5, but less widely supported in JWT libraries. RS256 is sufficient for EventHub's threat model and maximizes compatibility. |

## Date

2026-08-04