#!/bin/bash
echo "Checking container structure..."
docker-compose exec trading-app ls -la /app
docker-compose exec trading-app ls -la /app/build
docker-compose exec trading-app ls -la /app/api 