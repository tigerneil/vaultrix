#!/bin/bash
set -e

# Quick deployment script for Vaultrix
# For testing and development purposes

echo "🔐 Vaultrix - Quick Deploy"
echo "==========================="
echo ""

# Check Docker
if ! command -v docker &> /dev/null; then
    echo "❌ Docker is not installed. Please install Docker first."
    echo "Visit: https://docs.docker.com/get-docker/"
    exit 1
fi

if ! docker info &> /dev/null; then
    echo "❌ Docker daemon is not running. Please start Docker."
    exit 1
fi

echo "✓ Docker is ready"
echo ""

# Ask deployment type
echo "Select deployment method:"
echo "  1) Local Docker (single container)"
echo "  2) Docker Compose (recommended)"
echo "  3) Build only (no deployment)"
echo ""
read -p "Enter choice [1-3]: " choice

case $choice in
    1)
        echo ""
        echo "📦 Building Docker image..."
        docker build -t vaultrix:latest . --quiet || {
            echo "❌ Build failed!"
            exit 1
        }
        echo "✓ Image built successfully"

        echo ""
        echo "🚀 Starting Vaultrix container..."

        # Stop existing container if running
        docker stop vaultrix 2>/dev/null || true
        docker rm vaultrix 2>/dev/null || true

        # Create workspace directory
        mkdir -p workspace

        # Run container
        docker run -d \
            --name vaultrix \
            -v /var/run/docker.sock:/var/run/docker.sock \
            -v "$(pwd)/workspace:/workspace" \
            -e VAULTRIX_ENV=development \
            -e VAULTRIX_LOG_LEVEL=INFO \
            vaultrix:latest \
            tail -f /dev/null

        echo "✓ Container started"
        echo ""
        echo "📊 Container status:"
        docker ps | grep vaultrix || echo "Container not found!"
        echo ""
        echo "💡 Useful commands:"
        echo "  View logs:    docker logs -f vaultrix"
        echo "  Execute cmd:  docker exec vaultrix vaultrix info"
        echo "  Stop:         docker stop vaultrix"
        echo "  Remove:       docker rm vaultrix"
        ;;

    2)
        echo ""
        echo "📦 Building with Docker Compose..."
        docker-compose build || {
            echo "❌ Build failed!"
            exit 1
        }
        echo "✓ Build successful"

        echo ""
        echo "🚀 Starting services..."
        docker-compose up -d

        echo ""
        echo "⏳ Waiting for services..."
        sleep 3

        echo ""
        echo "📊 Service status:"
        docker-compose ps

        echo ""
        echo "💡 Useful commands:"
        echo "  View logs:    docker-compose logs -f"
        echo "  Restart:      docker-compose restart"
        echo "  Stop:         docker-compose down"
        echo "  Rebuild:      docker-compose up -d --build"
        ;;

    3)
        echo ""
        echo "📦 Building Docker image..."
        docker build -t vaultrix:latest .
        echo ""
        echo "✓ Build complete!"
        echo ""
        echo "Image: vaultrix:latest"
        docker images | grep vaultrix
        ;;

    *)
        echo "Invalid choice. Exiting."
        exit 1
        ;;
esac

echo ""
echo "✅ Deployment complete!"
echo ""
echo "📚 Next steps:"
echo "  • Review docs/DEPLOYMENT.md for production deployment"
echo "  • Check docs/QUICKSTART.md for usage examples"
echo "  • Visit https://vaultrix.dev for documentation"
echo ""
