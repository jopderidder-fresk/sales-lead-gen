FROM node:20-alpine AS base

ENV PNPM_HOME="/pnpm"
ENV PATH="$PNPM_HOME:$PATH"
RUN corepack enable && corepack prepare pnpm@latest --activate

WORKDIR /app

COPY frontend/package.json frontend/pnpm-lock.yaml ./
RUN pnpm install --frozen-lockfile

COPY --chown=node:node frontend/ .

# Development target: Vite dev server with HMR
FROM base AS dev
EXPOSE 5173
USER node
CMD ["pnpm", "exec", "vite", "--host", "0.0.0.0"]

# Production target: build and serve with nginx
FROM base AS build
ARG VITE_API_URL=""
ENV VITE_API_URL=${VITE_API_URL}
ENV NODE_OPTIONS="--max-old-space-size=1024"
RUN pnpm run build

FROM nginx:alpine AS prod
COPY docker/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
