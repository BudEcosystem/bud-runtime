# Stage 1: Install dependencies
FROM node:20.12 AS deps

WORKDIR /usr/bin/src

# Install dependencies based on the package.json and yarn.lock files
COPY package.json ./
RUN npm i

# Stage 2: Build the application
FROM node:20.12 AS builder

WORKDIR /usr/bin/src

# Copy the dependencies from the previous stage
COPY --from=deps /usr/bin/src/node_modules ./node_modules

# Copy the rest of the application files
COPY . .
RUN npm i
RUN rm .env

# Environment variable placeholders (can be overridden at runtime)
ENV OPENAI_API_KEY=NEXT_PUBLIC_OPENAI_API_KEY
ENV NEXT_PUBLIC_VERCEL_ENV=NEXT_PUBLIC_VERCEL_ENV
ENV NEXT_PUBLIC_PASSWORD=NEXT_PUBLIC_PASSWORD
ENV NEXT_PUBLIC_PRIVATE_KEY=NEXT_PUBLIC_PRIVATE_KEY
ENV NEXT_PUBLIC_BASE_URL=NEXT_PUBLIC_BASE_URL
ENV NEXT_PUBLIC_TEMP_API_BASE_URL=NEXT_PUBLIC_TEMP_API_BASE_URL
ENV NEXT_PUBLIC_COPY_CODE_API_BASE_URL=NEXT_PUBLIC_COPY_CODE_API_BASE_URL
ENV NEXT_PUBLIC_TEMP_API_ASSET_URL=NEXT_PUBLIC_TEMP_API_ASSET_URL
ENV NODE_TLS_REJECT_UNAUTHORIZED=NEXT_PUBLIC_NODE_TLS_REJECT_UNAUTHORIZED

# Build the Next.js app
RUN npm run build

# Stage 3: Run the application
FROM node:lts-alpine AS runner

WORKDIR /usr/bin/src

# Set production environment
ENV NODE_ENV=production

# Copy only necessary files for running the app
COPY --from=builder /usr/bin/src/public ./public
COPY --from=builder /usr/bin/src/.next ./.next
COPY --from=builder /usr/bin/src/node_modules ./node_modules
COPY --from=builder /usr/bin/src/package.json ./package.json

# Copy the entrypoint script
COPY entrypoint.sh /usr/bin/
RUN chmod +x /usr/bin/entrypoint.sh
ENTRYPOINT ["entrypoint.sh"]

# Default command (you can customize this if needed)
CMD ["node_modules/.bin/next", "start"]
#ENTRYPOINT ["sleep", "1000"]
