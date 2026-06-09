# Stage 1: Build dependencies (includes python, make, g++ for better-sqlite3)
FROM node:20 AS builder
WORKDIR /app
COPY serpro-viewer/package*.json ./
RUN npm ci

# Stage 2: Runtime
FROM node:20-slim
WORKDIR /app

# Copy node_modules from builder (with compiled better-sqlite3)
COPY --from=builder /app/node_modules ./node_modules
# Copy application code
COPY serpro-viewer/ .

EXPOSE 3000

ENV PORT=3000
ENV DB_PATH=/data/base_dados.db
ENV NODE_ENV=production

CMD ["node", "server-mapa-empresas.js"]
