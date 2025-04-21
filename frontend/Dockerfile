# frontend/Dockerfile

# 1. Use an official Node.js runtime as a parent image
# Choose a version compatible with Vite and your dependencies (e.g., LTS version)
FROM node:20-alpine AS base

# 2. Set the working directory in the container
WORKDIR /app

# 3. Copy package.json and package-lock.json (or yarn.lock)
# This is done first to leverage Docker layer caching for dependencies
COPY package.json package-lock.json* ./
# If using yarn:
# COPY package.json yarn.lock ./

# 4. Install dependencies
# Use 'ci' for potentially faster and more reliable installs in CI/CD,
# but 'install' is fine for general use.
RUN npm install
# If using yarn:
# RUN yarn install --frozen-lockfile
RUN npm install --save-dev @types/node

# 5. Copy the rest of the application code
COPY . .

# 6. Expose the port the Vite dev server runs on (default is 5173)
EXPOSE 5173

# 7. Define the default command to run the Vite dev server
# The '--host' flag makes it accessible outside the container
CMD ["npm", "run", "dev", "--", "--host"]
# If using yarn:
# CMD ["yarn", "dev", "--host"]

# --- Optional Production Stage ---
# You could add a multi-stage build here for production later:
# FROM base AS builder
# RUN npm run build
#
# FROM nginx:alpine AS production
# COPY --from=builder /app/dist /usr/share/nginx/html
# COPY nginx.conf /etc/nginx/nginx.conf # You'd need an nginx.conf file
# EXPOSE 80
# CMD ["nginx", "-g", "daemon off;"]