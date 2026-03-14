#!/bin/bash
# OPNsense Security Dashboard - VPS Deployment Script

set -e

echo "🚀 Deploying OPNsense Security Dashboard to VPS..."

# Check if .env exists
if [ ! -f .env ]; then
    echo "⚠️  Creating .env file from template..."
    cp .env.example .env
    echo "❌ Please edit .env with your OPNsense credentials and Tailscale auth key"
    echo "   Then run this script again."
    exit 1
fi

# Copy dashboard files
echo "📁 Copying dashboard files..."
if [ ! -d "dashboard" ]; then
    echo "❌ Dashboard directory not found!"
    echo "   Please copy your dashboard files to ./dashboard/"
    exit 1
fi

# Pull latest images
echo "📦 Pulling Docker images..."
docker-compose pull

# Build backend
echo "🔨 Building backend..."
docker-compose build backend

# Start services
echo "🚀 Starting services..."
docker-compose up -d

# Wait for services to start
echo "⏳ Waiting for services to start..."
sleep 5

# Check status
echo "📊 Checking service status..."
docker-compose ps

# Test backend
echo "🧪 Testing backend..."
curl -s http://localhost:5000/health | jq '.' || echo "Backend not responding yet..."

echo ""
echo "✅ Deployment complete!"
echo ""
echo "📊 Dashboard URL: http://$(curl -s ifconfig.me)/opnsense-security/"
echo "🔧 Backend API: http://$(curl -s ifconfig.me)/api"
echo ""
echo "📝 Useful commands:"
echo "   docker-compose logs -f          # View logs"
echo "   docker-compose restart          # Restart all services"
echo "   docker-compose down             # Stop all services"
echo ""
echo "🔒 Next steps:"
echo "   1. Configure SSL with Let's Encrypt (optional)"
echo "   2. Set up domain name (optional)"
echo "   3. Configure Tailscale for secure OPNsense access"
