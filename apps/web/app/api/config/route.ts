// Deployment-only route: exposes the API's base URL to the browser at
// request time, read from a plain (non "NEXT_PUBLIC_"-prefixed) server
// env var. Next.js inlines every `process.env.NEXT_PUBLIC_*` reference
// into the client bundle at `docker build` time — before a PaaS like
// Render has even created this service, let alone assigned it or the
// API's URL. A plain env var has no such prefix, so Next.js never
// inlines it; this route reads it live, on every request, and hands it
// to the browser. See docs/design-decisions.md for the full reasoning.
//
// `force-dynamic` is required: without it, this route could be
// statically evaluated once at build time (same problem as the
// "NEXT_PUBLIC_" prefix, just via a different mechanism), baking in
// whatever (probably empty) value was present during `docker build`.
export const dynamic = "force-dynamic";

export async function GET() {
  const apiUrl =
    process.env.API_URL ?? process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
  return Response.json({ apiUrl });
}
