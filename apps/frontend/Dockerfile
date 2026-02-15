# --------------- Build Stage ---------------
FROM node:20-alpine AS build

WORKDIR /app

RUN corepack enable && corepack prepare pnpm@9.12.1 --activate

COPY apps/frontend/package.json apps/frontend/pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile || pnpm install

COPY apps/frontend/ ./

# Vite inlines VITE_* env vars at build time
ARG VITE_API_KEY
ENV VITE_API_KEY=${VITE_API_KEY}

RUN pnpm build

# --------------- Serve Stage ---------------
FROM nginx:stable-alpine

COPY --from=build /app/build /usr/share/nginx/html
COPY apps/frontend/nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 3000

CMD ["nginx", "-g", "daemon off;"]
