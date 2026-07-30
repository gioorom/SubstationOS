/**
 * The one place the backend's address is decided.
 *
 * The default is `localhost`, **not** `127.0.0.1`, and the difference is
 * load-bearing since EPIC 30.3. The session cookie is `SameSite=Lax`, and
 * "site" is scheme plus registrable domain - ports are ignored, but
 * `localhost` and `127.0.0.1` are different hosts. Served from
 * `localhost:3000` against `localhost:8000` the two are same-site and the
 * cookie travels; against `127.0.0.1:8000` it silently would not, and
 * every request would arrive anonymous.
 *
 * In production both are served from one origin (or one reverse proxy),
 * which is the arrangement `security_architecture.md` documents and the
 * one that keeps SSO redirects sane later.
 */

const apiBaseUrl =
  process.env.NEXT_PUBLIC_API_BASE_URL ?? "http://localhost:8000";

export const env = {
  apiBaseUrl,
} as const;
