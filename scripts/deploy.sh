#!/bin/bash
set -e

# Vaultrix Deployment Script
# This script builds and deploys Vaultrix to production

echo "🔐 Vaultrix Deployment Script"
echo "==============================="
echo ""

# Configuration
ENVIRONMENT="${ENVIRONMENT:-production}"
VERSION="${VERSION:-latest}"
REGISTRY="${DOCKER_REGISTRY:-}"

echo "Environment: $ENVIRONMENT"
echo "Version: $VERSION"
echo ""

# Check prerequisites
echo "📋 Checking prerequisites..."

if ! command -v docker &> /dev/null; then
    echo "❌ Docker is not installed"
    exit 1
fi
echo "✓ Docker is installed"

if ! docker info &> /dev/null; then
    echo "❌ Docker daemon is not running"
    exit 1
fi
echo "✓ Docker daemon is running"

# Build the Docker image
echo ""
echo "🔨 Building Docker image..."
docker build -t vaultrix:${VERSION} .

if [ -n "$REGISTRY" ]; then
    echo ""
    echo "📦 Tagging image for registry..."
    docker tag vaultrix:${VERSION} ${REGISTRY}/vaultrix:${VERSION}
    docker tag vaultrix:${VERSION} ${REGISTRY}/vaultrix:latest
fi

# Run tests
echo ""
echo "🧪 Running tests..."
docker run --rm vaultrix:${VERSION} python -m pytest tests/ -v || {
    echo "❌ Tests failed!"
    exit 1
}
echo "✓ All tests passed"

# Push to registry (if configured)
if [ -n "$REGISTRY" ]; then
    echo ""
    echo "📤 Pushing to registry..."
    docker push ${REGISTRY}/vaultrix:${VERSION}
    docker push ${REGISTRY}/vaultrix:latest
    echo "✓ Images pushed to registry"
fi

# Deploy with docker-compose
echo ""
echo "🚀 Deploying Vaultrix..."
docker-compose down || true
docker-compose up -d

# Wait for service to be healthy
echo ""
echo "⏳ Waiting for service to be healthy..."
sleep 5

if docker-compose ps | grep -q "Up"; then
    echo "✅ Vaultrix deployed successfully!"
    echo ""
    echo "Service status:"
    docker-compose ps
    echo ""
    echo "To view logs: docker-compose logs -f vaultrix"
    echo "To stop: docker-compose down"
else
    echo "❌ Deployment failed!"
    docker-compose logs
    exit 1
fi
