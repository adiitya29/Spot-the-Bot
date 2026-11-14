# Multi-stage Dockerfile for Spot the Bot frontend
# Stage 1: Development server (Vite dev)
FROM node:22-alpine AS dev

WORKDIR /app

COPY frontend/package*.json ./
RUN npm install

COPY frontend/ ./

EXPOSE 5173
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0", "--port", "5173"]

# Stage 2: Production static build
FROM dev AS build
RUN npm run build

# Stage 3: Production Nginx image serving built SPA and proxying API/WebSockets
FROM nginx:1.27-alpine AS prod

RUN rm -rf /etc/nginx/conf.d/*
COPY docker/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html

HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
  CMD wget -qO- http://localhost/nginx-health || exit 1

EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
