# DAHA web: Next.js production server on :3000 (Person A owns this one file inside web/).
#   docker build -t daha-web web
# The API address and the NEXT_PUBLIC_* flags are baked in at build time (Next.js compiles
# rewrites and public env vars into the build), so they are build args, not runtime env.
FROM node:lts-slim AS base
ENV PNPM_HOME=/pnpm PATH=/pnpm:$PATH NEXT_TELEMETRY_DISABLED=1
RUN npm install -g pnpm@12
WORKDIR /app

FROM base AS deps
COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./
RUN pnpm install --frozen-lockfile

FROM base AS build
ARG API_PROXY_TARGET=http://api:8000
ARG NEXT_PUBLIC_MOCK=none
ARG NEXT_PUBLIC_DEMO_MODE=true
ENV API_PROXY_TARGET=$API_PROXY_TARGET \
    NEXT_PUBLIC_MOCK=$NEXT_PUBLIC_MOCK \
    NEXT_PUBLIC_DEMO_MODE=$NEXT_PUBLIC_DEMO_MODE
COPY --from=deps /app/node_modules ./node_modules
# Copy only the sources (never the laptop's node_modules, .next, or env files).
COPY package.json pnpm-lock.yaml pnpm-workspace.yaml next.config.ts tsconfig.json ./
COPY public ./public
COPY src ./src
RUN pnpm build

FROM base AS run
ENV NODE_ENV=production
ARG API_PROXY_TARGET=http://api:8000
ENV API_PROXY_TARGET=$API_PROXY_TARGET
COPY --from=build --chown=node:node /app ./
USER node
EXPOSE 3000
HEALTHCHECK --interval=5s --timeout=3s --start-period=30s --retries=30 \
    CMD node -e "fetch('http://localhost:3000/login').then(r=>process.exit(r.ok?0:1)).catch(()=>process.exit(1))"
CMD ["pnpm", "start", "--hostname", "0.0.0.0", "--port", "3000"]
