# Dev stage: used by docker-compose.dev.yml (target: dev) to run the Vite
# dev server with bind-mounted sources.
FROM node:20-alpine AS dev
WORKDIR /app
COPY package.json package-lock.json ./
RUN npm ci
COPY . .
EXPOSE 5173
CMD ["npm", "run", "dev", "--", "--host", "0.0.0.0", "--port", "5173"]

# Build stage: type-check + bundle.
FROM dev AS build
RUN npm run build

# §9.1: nginx serves the static bundle and proxies /api/ to the api service.
FROM nginx:alpine
COPY nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 80
