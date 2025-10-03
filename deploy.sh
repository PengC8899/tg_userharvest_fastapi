#!/bin/bash

# Telegram User Harvest - Production Deployment Script
# Usage: ./deploy.sh [domain] [email]

set -e

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Functions
log_info() {
    echo -e "${GREEN}[INFO]${NC} $1"
}

log_warn() {
    echo -e "${YELLOW}[WARN]${NC} $1"
}

log_error() {
    echo -e "${RED}[ERROR]${NC} $1"
}

# Check if running as root
if [[ $EUID -eq 0 ]]; then
   log_error "This script should not be run as root for security reasons"
   exit 1
fi

# Parse arguments
DOMAIN=${1:-""}
EMAIL=${2:-""}

if [[ -z "$DOMAIN" ]]; then
    read -p "Enter your domain name: " DOMAIN
fi

if [[ -z "$EMAIL" ]]; then
    read -p "Enter your email for SSL certificate: " EMAIL
fi

log_info "Starting deployment for domain: $DOMAIN"

# Check if Docker is installed
if ! command -v docker &> /dev/null; then
    log_error "Docker is not installed. Please install Docker first."
    exit 1
fi

# Check if Docker Compose is installed
if ! command -v docker-compose &> /dev/null; then
    log_error "Docker Compose is not installed. Please install Docker Compose first."
    exit 1
fi

# Create necessary directories
log_info "Creating necessary directories..."
mkdir -p data logs nginx/ssl

# Check if .env.prod exists
if [[ ! -f ".env.prod" ]]; then
    log_error ".env.prod file not found. Please create it from .env.prod template."
    exit 1
fi

# Update domain in nginx config
log_info "Updating Nginx configuration with domain: $DOMAIN"
sed -i.bak "s/your-domain.com/$DOMAIN/g" nginx/nginx.conf

# Update domain in .env.prod
sed -i.bak "s/DOMAIN=your-domain.com/DOMAIN=$DOMAIN/g" .env.prod
sed -i.bak "s/EMAIL=your-email@example.com/EMAIL=$EMAIL/g" .env.prod

# Generate JWT secret if not set
if grep -q "your_super_secret_jwt_key_here_change_this_in_production" .env.prod; then
    log_info "Generating JWT secret key..."
    JWT_SECRET=$(openssl rand -hex 32)
    sed -i.bak "s/JWT_SECRET_KEY=your_super_secret_jwt_key_here_change_this_in_production/JWT_SECRET_KEY=$JWT_SECRET/g" .env.prod
fi

# Check if SSL certificates exist
if [[ ! -f "nginx/ssl/fullchain.pem" ]] || [[ ! -f "nginx/ssl/privkey.pem" ]]; then
    log_warn "SSL certificates not found. You need to obtain SSL certificates."
    log_info "You can use Let's Encrypt with certbot:"
    log_info "1. Install certbot: sudo apt-get install certbot"
    log_info "2. Get certificate: sudo certbot certonly --standalone -d $DOMAIN --email $EMAIL"
    log_info "3. Copy certificates to nginx/ssl/ directory"
    log_info "   sudo cp /etc/letsencrypt/live/$DOMAIN/fullchain.pem nginx/ssl/"
    log_info "   sudo cp /etc/letsencrypt/live/$DOMAIN/privkey.pem nginx/ssl/"
    log_info "   sudo chown \$(whoami):\$(whoami) nginx/ssl/*.pem"
    
    read -p "Do you want to continue without SSL certificates? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        log_info "Please obtain SSL certificates and run the script again."
        exit 1
    fi
    
    # Create self-signed certificates for testing
    log_warn "Creating self-signed certificates for testing..."
    openssl req -x509 -nodes -days 365 -newkey rsa:2048 \
        -keyout nginx/ssl/privkey.pem \
        -out nginx/ssl/fullchain.pem \
        -subj "/C=US/ST=State/L=City/O=Organization/CN=$DOMAIN"
fi

# Build and start services
log_info "Building Docker images..."
docker-compose -f docker-compose.full.yml --env-file .env.prod build

log_info "Starting all services (app + monitoring)..."
docker-compose -f docker-compose.full.yml --env-file .env.prod up -d

# Wait for services to be ready
log_info "Waiting for services to be ready..."
sleep 10

# Check if services are running
if docker-compose -f docker-compose.full.yml ps | grep -q "Up"; then
    log_info "Services are running successfully!"
    log_info "Application is available at: https://$DOMAIN"
    log_info "Health check: https://$DOMAIN/health"
    log_info "Grafana monitoring: http://$DOMAIN:3000 (admin/admin)"
    log_info "Prometheus: http://$DOMAIN:9090"
else
    log_error "Some services failed to start. Check logs with:"
    log_error "docker-compose -f docker-compose.full.yml logs"
    exit 1
fi

# Show useful commands
log_info "Useful commands:"
log_info "  View logs: docker-compose -f docker-compose.full.yml logs -f"
log_info "  Stop services: docker-compose -f docker-compose.full.yml down"
log_info "  Restart services: docker-compose -f docker-compose.full.yml restart"
log_info "  Update application: git pull && docker-compose -f docker-compose.full.yml up -d --build"

log_info "Deployment completed successfully!"