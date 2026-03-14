#!/bin/bash

# Vaultrix Sandbox Initialization Script
# This script prepares the environment for running Vaultrix

set -e

echo "🔐 Vaultrix Sandbox Initialization"
echo "===================================="
echo ""

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    echo "❌ Docker is not installed."
    echo "Please install Docker from: https://docs.docker.com/get-docker/"
    exit 1
fi

echo "✓ Docker is installed"

# Check if Docker daemon is running
if ! docker info &> /dev/null; then
    echo "❌ Docker daemon is not running."
    echo "Please start Docker and try again."
    exit 1
fi

echo "✓ Docker daemon is running"

# Pull the base image
echo ""
echo "📦 Pulling base sandbox image..."
docker pull python:3.11-slim

echo ""
echo "✓ Base image pulled successfully"

# Create workspace directory
echo ""
echo "📁 Creating workspace directory..."
mkdir -p ~/.vaultrix/workspaces
echo "✓ Workspace directory created at ~/.vaultrix/workspaces"

# Create config directory
mkdir -p ~/.vaultrix/config
echo "✓ Config directory created at ~/.vaultrix/config"

echo ""
echo "✅ Vaultrix sandbox environment initialized successfully!"
echo ""
echo "Next steps:"
echo "  1. Install Vaultrix: pip install -e ."
echo "  2. Run Vaultrix: vaultrix start"
echo ""
