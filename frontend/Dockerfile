# syntax=docker/dockerfile:1

FROM node:22-alpine AS build

WORKDIR /app/frontend

COPY frontend/package.json frontend/package-lock.json ./
RUN npm ci

COPY frontend/ ./

ARG VITE_API_URL=http://localhost:8001
ENV VITE_API_URL=$VITE_API_URL

RUN npm run build


FROM nginx:alpine AS runtime

COPY frontend/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=build /app/frontend/dist/ /usr/share/nginx/html/

EXPOSE 80
