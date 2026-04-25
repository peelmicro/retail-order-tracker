# syntax=docker/dockerfile:1.7
# Multi-stage: build the SPA, then serve it with nginx.
#
# Base images come from Google's transparent Docker Hub mirror by default
# (mirror.gcr.io/library) to avoid Docker Hub rate limits and Cloudflare R2
# unreachability from Spanish ISPs during LaLiga matches. Same images, same
# layer SHAs — just a different CDN. Override with --build-arg or .env:
#   BASE_REGISTRY=docker.io/library

ARG BASE_REGISTRY=mirror.gcr.io/library

# ---- Stage 1: build -----------------------------------------------------
FROM ${BASE_REGISTRY}/node:24-alpine AS build

WORKDIR /app

# Install deps from a clean slate (npm ci respects package-lock.json)
COPY package.json package-lock.json* ./
RUN npm ci

# Copy source and build
COPY . .
ARG VITE_API_URL=http://localhost:8000
ENV VITE_API_URL=$VITE_API_URL
RUN npm run build

# ---- Stage 2: serve -----------------------------------------------------
FROM ${BASE_REGISTRY}/nginx:alpine

COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf

EXPOSE 80
