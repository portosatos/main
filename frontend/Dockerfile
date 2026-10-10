# Build the SPA with Node 22 LTS, serve it with nginx (proxy /api -> api:8000, see nginx.conf).
FROM node:22-alpine AS build
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
RUN npm run build

FROM nginx:1.29-alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
HEALTHCHECK --interval=5s --timeout=3s --retries=20 \
    CMD wget -q -O /dev/null http://127.0.0.1/ || exit 1
