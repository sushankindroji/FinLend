# FinLend frontend (Angular) — container image.
# Builds the existing Angular app unchanged and serves the static output
# via Nginx, with SPA (client-side routing) fallback configured.

# ---- Stage 1: build ---------------------------------------------------
FROM node:20-bookworm-slim AS build

WORKDIR /app

COPY package.json package-lock.json ./
RUN npm ci

COPY . .
RUN npm run build -- --configuration production

# ---- Stage 2: serve -----------------------------------------------------
FROM nginx:1.27-alpine AS serve

COPY nginx.conf /etc/nginx/conf.d/default.conf

# Angular 18 "application" builder outputs to dist/<project>/browser
COPY --from=build /app/dist/finlend-frontend/browser /usr/share/nginx/html

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
