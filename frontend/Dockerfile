FROM node:lts-slim

WORKDIR /app

# Dependency layer first.
COPY package.json package-lock.json ./
RUN npm ci

COPY . .

# Dev server; run as the unprivileged user shipped with the node image.
RUN chown -R node:node /app
USER node
EXPOSE 5173

CMD ["npx", "vite", "--host", "0.0.0.0"]
