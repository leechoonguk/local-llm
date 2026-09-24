# --- build stage ---
FROM node:22-alpine@sha256:b6f26b36c8ff49624cfdac716b8ea1138d606df02586a77d364bb5536a634f85 AS build
WORKDIR /app
COPY package.json package-lock.json ./
# --ignore-scripts: the manifest also carries the harness's tools (ast-grep, the
# language servers) because `.omp/hooks/lib/ast-rules.ts` resolves them from
# frontend/node_modules. Their postinstall scripts fetch a native binary for the
# platform the lockfile was written on, so they fail in this image and took the
# whole build with them. Vite and TypeScript need no install script, so skipping
# them also means the image runs no third-party code at build time.
RUN npm ci --ignore-scripts
COPY . .
RUN npm run build

# --- serve stage ---
FROM nginx:alpine@sha256:62ff2089abf5a9ed33bd232895bef5e22f7bb4b200675cec49a5ebc48e3d4ac8
COPY --from=build /app/dist /usr/share/nginx/html
COPY nginx.conf /etc/nginx/conf.d/default.conf
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
