FROM node:22-slim AS deps
WORKDIR /app
COPY apps/web/package.json apps/web/package-lock.json ./
RUN npm ci

FROM node:22-slim AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY apps/web .
RUN npm run build

FROM node:22-slim AS runner
WORKDIR /app
ENV NODE_ENV=production
COPY --from=builder --chown=node:node /app/.next/standalone ./
COPY --from=builder --chown=node:node /app/.next/static ./.next/static
COPY --from=builder --chown=node:node /app/public ./public

# Phase 9: the official node images already ship an unprivileged `node`
# user (uid 1000) for exactly this — no reason to serve as root.
USER node

EXPOSE 3000

# Same reasoning as apps/api/Dockerfile's HEALTHCHECK — legible outside
# compose too. Next.js has no dedicated health route; the standalone
# server returns the dashboard page's static HTML for `/` regardless of
# whether the API is reachable (client components fetch after hydration),
# so a 200 there is a real "this process is alive and serving" signal.
# node:22-slim has no curl/wget, so this uses Node's own http client
# rather than adding a package just for the healthcheck. Reads $PORT
# (falls back to 3000, this image's EXPOSEd default) — the standalone
# server.js Next.js generates already binds to $PORT natively when set,
# so no CMD change is needed for that half, only this healthcheck's.
HEALTHCHECK --interval=10s --timeout=5s --retries=5 \
    CMD node -e "require('http').get('http://localhost:' + (process.env.PORT || 3000) + '/', r => process.exit(r.statusCode === 200 ? 0 : 1)).on('error', () => process.exit(1))"

CMD ["node", "server.js"]
