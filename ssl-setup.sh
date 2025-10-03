#!/bin/bash

# SSL Certificate Setup Script for Let's Encrypt
# Usage: ./ssl-setup.sh [domain] [email]

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

# Parse arguments
DOMAIN=${1:-""}
EMAIL=${2:-""}

if [[ -z "$DOMAIN" ]]; then
    read -p "Enter your domain name: " DOMAIN
fi

if [[ -z "$EMAIL" ]]; then
    read -p "Enter your email for SSL certificate: " EMAIL
fi

log_info "Setting up SSL certificate for domain: $DOMAIN"

# Check if running on a server with public IP
log_info "Checking if domain points to this server..."
SERVER_IP=$(curl -s ifconfig.me)
DOMAIN_IP=$(dig +short $DOMAIN | tail -n1)

if [[ "$SERVER_IP" != "$DOMAIN_IP" ]]; then
    log_warn "Domain $DOMAIN does not point to this server ($SERVER_IP vs $DOMAIN_IP)"
    log_warn "Please update your DNS records to point to this server's IP: $SERVER_IP"
    read -p "Continue anyway? (y/N): " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Install certbot if not present
if ! command -v certbot &> /dev/null; then
    log_info "Installing certbot..."
    if command -v apt-get &> /dev/null; then
        sudo apt-get update
        sudo apt-get install -y certbot
    elif command -v yum &> /dev/null; then
        sudo yum install -y certbot
    elif command -v dnf &> /dev/null; then
        sudo dnf install -y certbot
    else
        log_error "Could not install certbot. Please install it manually."
        exit 1
    fi
fi

# Stop nginx if running to free port 80
if docker ps | grep -q nginx; then
    log_info "Stopping nginx container to free port 80..."
    docker stop tg_nginx || true
fi

# Get SSL certificate
log_info "Obtaining SSL certificate from Let's Encrypt..."
sudo certbot certonly --standalone \
    --non-interactive \
    --agree-tos \
    --email "$EMAIL" \
    -d "$DOMAIN"

# Create ssl directory if it doesn't exist
mkdir -p nginx/ssl

# Copy certificates
log_info "Copying certificates to nginx/ssl directory..."
sudo cp "/etc/letsencrypt/live/$DOMAIN/fullchain.pem" nginx/ssl/
sudo cp "/etc/letsencrypt/live/$DOMAIN/privkey.pem" nginx/ssl/

# Change ownership
sudo chown $(whoami):$(whoami) nginx/ssl/*.pem

# Set proper permissions
chmod 644 nginx/ssl/fullchain.pem
chmod 600 nginx/ssl/privkey.pem

log_info "SSL certificates installed successfully!"

# Create renewal script
log_info "Creating certificate renewal script..."
cat > renew-ssl.sh << EOF
#!/bin/bash
# SSL Certificate Renewal Script

set -e

log_info() {
    echo -e "\033[0;32m[INFO]\033[0m \$1"
}

log_info "Renewing SSL certificate for $DOMAIN..."

# Stop nginx
docker stop tg_nginx || true

# Renew certificate
sudo certbot renew --standalone

# Copy renewed certificates
sudo cp "/etc/letsencrypt/live/$DOMAIN/fullchain.pem" nginx/ssl/
sudo cp "/etc/letsencrypt/live/$DOMAIN/privkey.pem" nginx/ssl/
sudo chown \$(whoami):\$(whoami) nginx/ssl/*.pem
chmod 644 nginx/ssl/fullchain.pem
chmod 600 nginx/ssl/privkey.pem

# Restart nginx
docker start tg_nginx

log_info "SSL certificate renewed successfully!"
EOF

chmod +x renew-ssl.sh

# Add to crontab for automatic renewal
log_info "Setting up automatic certificate renewal..."
(crontab -l 2>/dev/null; echo "0 3 * * 0 cd $(pwd) && ./renew-ssl.sh >> logs/ssl-renewal.log 2>&1") | crontab -

log_info "SSL setup completed successfully!"
log_info "Certificate will be automatically renewed every Sunday at 3 AM"
log_info "You can now run the deployment script: ./deploy.sh $DOMAIN $EMAIL"