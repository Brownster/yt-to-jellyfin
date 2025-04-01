#!/bin/bash
# Script to test Docker build and functionality

set -e  # Exit on any error

echo "Building Docker image..."
docker build -t yt-to-jellyfin:test .

echo "Creating test directories..."
mkdir -p ./test-media
mkdir -p ./test-config

echo "Starting test container..."
docker run --name yt-to-jellyfin-test -d \
  -v $PWD/test-media:/media \
  -v $PWD/test-config:/config \
  -p 8000:8000 \
  -e WEB_ENABLED=true \
  -e WEB_PORT=8000 \
  -e WEB_HOST=0.0.0.0 \
  yt-to-jellyfin:test --web-only

# Wait for container to start
echo "Waiting for container to start..."
sleep 5

# Check if container is running
if [ "$(docker inspect -f {{.State.Running}} yt-to-jellyfin-test)" = "true" ]; then
  echo "Container is running successfully"
else
  echo "Container failed to start"
  docker logs yt-to-jellyfin-test
  docker rm yt-to-jellyfin-test
  exit 1
fi

# Try to access the web interface
echo "Testing web interface..."
HTTP_STATUS=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8000/)
if [ "$HTTP_STATUS" -eq 200 ]; then
  echo "Web interface is accessible"
else
  echo "Web interface is not accessible (HTTP status: $HTTP_STATUS)"
  docker logs yt-to-jellyfin-test
  docker stop yt-to-jellyfin-test
  docker rm yt-to-jellyfin-test
  exit 1
fi

# Clean up
echo "Cleaning up..."
docker stop yt-to-jellyfin-test
docker rm yt-to-jellyfin-test

# Optional: remove test directories
# rm -rf ./test-media ./test-config

echo "All Docker tests passed successfully!"