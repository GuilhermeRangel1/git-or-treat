FROM node:24-slim AS build
WORKDIR /app
ARG VITE_GENAI_SQL_ANALYSIS_ENABLED=false
ENV VITE_API_URL=/ VITE_GENAI_SQL_ANALYSIS_ENABLED=${VITE_GENAI_SQL_ANALYSIS_ENABLED}
COPY frontend/package*.json ./
RUN npm ci --no-audit --no-fund
COPY frontend/ .
RUN npm run build

FROM nginx:1.28-alpine
COPY frontend/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/dist /usr/share/nginx/html
EXPOSE 5173
