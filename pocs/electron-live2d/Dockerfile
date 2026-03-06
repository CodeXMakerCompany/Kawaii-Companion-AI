FROM node:20-alpine
WORKDIR /app

COPY package.json package-lock.json* ./
RUN npm install

COPY tsconfig.base.json tsconfig.backend.json ./
COPY src ./src
RUN npx tsc -p tsconfig.backend.json

ENV PORT=12393
EXPOSE 12393

CMD ["node", "out/backend/server.js"]
