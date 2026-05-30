# Multi-stage: build the React app with Node, serve the static bundle with nginx.
FROM node:20-alpine AS build
WORKDIR /app
COPY package.json package-lock.json* ./
RUN npm ci --no-audit --no-fund || npm install --no-audit --no-fund
COPY . .
RUN npm run build

FROM nginx:1.27-alpine AS serve
RUN rm /etc/nginx/conf.d/default.conf
COPY nginx.conf /etc/nginx/conf.d/storeiq.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 8050
HEALTHCHECK --interval=15s --timeout=3s --start-period=5s --retries=5 \
  CMD wget -q --spider http://localhost:8050/ || exit 1
CMD ["nginx", "-g", "daemon off;"]
