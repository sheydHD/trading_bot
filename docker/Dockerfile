# Multi-stage build for the React frontend
FROM node:16 AS frontend-build

# Set up working directory
WORKDIR /app

# Copy package.json and package-lock.json first for better caching
COPY frontend/package.json frontend/package-lock.json* ./
COPY frontend/config/package.json ./config-package.json
RUN if [ -f "package.json" ]; then npm install; elif [ -f "config-package.json" ]; then cp config-package.json package.json && npm install; fi

# Copy all frontend source files
COPY frontend/public/ ./public/
COPY frontend/src/ ./src/
COPY frontend/config/*.js ./

# Add environment variables for the React app
RUN echo "REACT_APP_API_URL=/api" > .env
RUN echo "REACT_APP_API_KEY=your-secret-api-key" >> .env

# Build the React app
RUN npm run build

# Debug what we built
RUN ls -la /app/build
RUN echo "Build directory contents:"
RUN find /app/build -type f | head -10

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
COPY backend/config/requirements.txt ./
RUN pip install --no-cache-dir -r requirements.txt

# Copy backend code structure
COPY backend/ backend/
COPY run.py ./

# Copy the frontend build from the previous stage to where the API expects it
COPY --from=frontend-build /app/build/ ./build/

# Create necessary directories
RUN mkdir -p backend/data/cache backend/logs

# Expose the API port
EXPOSE 5001
# Expose frontend port for direct access (if needed)
EXPOSE 3000

# Add the entrypoint script
COPY docker/docker-entrypoint.sh /usr/local/bin/
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

# Set the entrypoint
ENTRYPOINT ["docker-entrypoint.sh"]
CMD ["python", "run.py"] 