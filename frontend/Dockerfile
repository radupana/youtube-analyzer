FROM node:20-slim

WORKDIR /app

# Install dependencies
COPY package*.json ./
RUN npm ci || npm install

# Copy application
COPY . .

# Build for production
RUN npm run build

EXPOSE 3000

CMD ["npm", "start"]
