# Stage 1: build backend (TypeScript -> JS)
FROM node:20-alpine AS builder
WORKDIR /app

# Only what's needed to build the backend
COPY package.json package-lock.json* ./
RUN npm install

COPY tsconfig.base.json tsconfig.backend.json ./
COPY src/backend ./src/backend
COPY src/shared ./src/shared
RUN npx tsc -p tsconfig.backend.json

# Stage 2: runtime image (production deps only, no Electron/React/dev)
FROM node:20-alpine
WORKDIR /app

COPY package.json package-lock.json* ./
RUN npm install --omit=dev

COPY --from=builder /app/out/backend ./out/backend
COPY --from=builder /app/out/shared ./out/shared

ENV PORT=12393
EXPOSE 12393

CMD ["node", "out/backend/server.js"]
