FROM node:20-alpine

WORKDIR /app
# 釘死 pnpm 10.x（最後支援 Node 20 的 major）；避免 corepack 抓到 pnpm 11 要求 Node 22+
RUN corepack enable && corepack prepare pnpm@10.11.0 --activate

COPY package.json ./
RUN pnpm install --no-frozen-lockfile

COPY . .

EXPOSE 3000
CMD ["pnpm", "dev"]
