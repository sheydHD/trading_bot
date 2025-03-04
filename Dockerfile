# Multi-stage build for the React frontend
FROM node:16 AS frontend-build

WORKDIR /app
COPY package.json package-lock.json ./
RUN npm install

# Copy all frontend files and build
COPY public/ public/
COPY src/ src/
COPY postcss.config.js tailwind.config.js ./
RUN npm run build

# Add after copying the frontend build
RUN ls -la /app/build
RUN echo "Build directory contents:"
RUN find /app/build -type f | head -10

# Create .env file for React build
RUN echo "REACT_APP_API_KEY=your-secret-api-key" > /app/.env.production.local

# Backend stage that will serve both the API and frontend
FROM python:3.10-slim

# Install dependencies and debugging tools
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    python3-dev \
    curl \
    nano \
    && rm -rf /var/lib/apt/lists/*

# Set up working directory
WORKDIR /app

# Copy Python requirements
COPY requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend code
COPY api/ api/
COPY utils/ utils/
COPY main.py ./
COPY .env ./

# Copy the frontend build from the previous stage
COPY --from=frontend-build /app/build/ build/

# Expose the API port
EXPOSE 5001

# Add the entrypoint script
COPY docker-entrypoint.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

# Set the entrypoint
ENTRYPOINT ["docker-entrypoint.sh"]
CMD ["python", "api/app.py"] 