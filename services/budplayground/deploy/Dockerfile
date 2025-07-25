# Start Generation Here

# Use the official Node.js 18 image as the base image
FROM node:18 AS base

# Set the working directory
WORKDIR /app

# Install tailwindcss
RUN npm i -g @tailwindcss/oxide-linux-x64-gnu lightningcss-linux-x64-gnu

# Copy package.json and package-lock.json
COPY package.json package-lock.json ./

# Install dependencies
RUN npm install

# Copy the rest of the application code
COPY . .

# Build the Next.js application
RUN npm run build

# Use a regular Node.js image for runtime as well
FROM node:18 AS runtime

# Set the working directory
WORKDIR /app

# Copy the built application from the build stage
COPY --from=base /app ./

# Start the Next.js application. App will be running on port 3000
CMD ["npm", "start"]

# End Generation Here
