FROM node:22-alpine

# Dev-only image; still pull pending Alpine security fixes
RUN apk update && apk upgrade --no-cache

WORKDIR /app

COPY package.json package-lock.json* ./
RUN npm install

COPY . .
CMD ["npm", "run", "dev"]
