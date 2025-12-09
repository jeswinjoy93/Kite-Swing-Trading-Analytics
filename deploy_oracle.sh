#!/bin/bash

################################################################################
# GTT Trading Dashboard - Automated Deployment Script for Oracle Cloud
# This script automates the deployment process after you've created your VM
################################################################################

set -e  # Exit on any error

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

# Function to print colored output
print_step() {
    echo -e "${BLUE}==>${NC} ${GREEN}$1${NC}"
}

print_info() {
    echo -e "${YELLOW}ℹ${NC} $1"
}

print_success() {
    echo -e "${GREEN}✓${NC} $1"
}

print_error() {
    echo -e "${RED}✗${NC} $1"
}

# Welcome message
clear
echo -e "${GREEN}"
echo "╔════════════════════════════════════════════════════════════╗"
echo "║   GTT Trading Dashboard - Automated Deployment Script     ║"
echo "║              Oracle Cloud Free Tier Setup                 ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo -e "${NC}"
echo ""

# Check if running as root or with sudo
if [ "$EUID" -ne 0 ]; then 
    print_error "Please run this script with sudo:"
    echo "  sudo bash deploy_oracle.sh"
    exit 1
fi

print_info "This script will:"
echo "  1. Update system packages"
echo "  2. Install Python, Git, and dependencies"
echo "  3. Install Google Chrome and ChromeDriver"
echo "  4. Clone your GitHub repository"
echo "  5. Install Python packages"
echo "  6. Configure firewall rules"
echo "  7. Set up systemd service for auto-start"
echo ""
read -p "Press Enter to continue or Ctrl+C to cancel..."

################################################################################
# STEP 1: Update System
################################################################################
print_step "Step 1/8: Updating system packages..."
apt update -y
apt upgrade -y
print_success "System updated successfully"

################################################################################
# STEP 2: Install System Dependencies
################################################################################
print_step "Step 2/8: Installing system dependencies..."
apt install -y \
    python3-pip \
    python3-venv \
    git \
    unzip \
    screen \
    wget \
    curl \
    net-tools \
    htop \
    iptables-persistent

print_success "System dependencies installed"

################################################################################
# STEP 3: Install Google Chrome
################################################################################
print_step "Step 3/8: Installing Google Chrome..."
if ! command -v google-chrome &> /dev/null; then
    wget -q https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb
    apt install -y ./google-chrome-stable_current_amd64.deb
    rm google-chrome-stable_current_amd64.deb
    print_success "Google Chrome installed: $(google-chrome --version)"
else
    print_success "Google Chrome already installed: $(google-chrome --version)"
fi

################################################################################
# STEP 4: Clone Repository
################################################################################
print_step "Step 4/8: Cloning GitHub repository..."
cd /home/ubuntu

if [ -d "Kite-Swing-Trading-Analytics" ]; then
    print_info "Repository already exists. Pulling latest changes..."
    cd Kite-Swing-Trading-Analytics
    sudo -u ubuntu git pull origin main
else
    print_info "Cloning repository..."
    sudo -u ubuntu git clone https://github.com/jeswinjoy93/Kite-Swing-Trading-Analytics.git
    cd Kite-Swing-Trading-Analytics
fi

print_success "Repository ready"

################################################################################
# STEP 5: Install Python Dependencies
################################################################################
print_step "Step 5/8: Installing Python dependencies..."
sudo -u ubuntu pip3 install -r requirements.txt
sudo -u ubuntu pip3 install gunicorn chromedriver-autoinstaller
print_success "Python packages installed"

################################################################################
# STEP 6: Configure Credentials
################################################################################
print_step "Step 6/8: Configuring credentials..."

if [ ! -f "config.py" ]; then
    print_info "config.py not found. Creating from template..."
    
    echo -e "${YELLOW}"
    echo "════════════════════════════════════════════════════════════"
    echo "  Please enter your Kite Connect API credentials"
    echo "════════════════════════════════════════════════════════════"
    echo -e "${NC}"
    
    read -p "API Key: " api_key
    read -p "API Secret: " api_secret
    read -p "User ID: " user_id
    read -sp "Password: " password
    echo ""
    read -p "TOTP Secret: " totp_secret
    
    cat > config.py << EOF
api_key = "$api_key"
api_secret = "$api_secret"
user_id = "$user_id"
password = "$password"
totp_secret = "$totp_secret"
EOF
    
    chown ubuntu:ubuntu config.py
    chmod 600 config.py
    print_success "Credentials configured"
else
    print_success "config.py already exists"
fi

################################################################################
# STEP 7: Configure Firewall
################################################################################
print_step "Step 7/8: Configuring firewall..."

# Configure iptables
iptables -I INPUT 6 -m state --state NEW -p tcp --dport 5002 -j ACCEPT
netfilter-persistent save

# Configure UFW (if enabled)
if command -v ufw &> /dev/null; then
    ufw allow 5002/tcp
fi

print_success "Firewall configured for port 5002"

################################################################################
# STEP 8: Set Up Systemd Service
################################################################################
print_step "Step 8/8: Setting up systemd service..."

cat > /etc/systemd/system/gtt-dashboard.service << 'EOF'
[Unit]
Description=GTT Trading Dashboard
After=network.target

[Service]
Type=simple
User=ubuntu
WorkingDirectory=/home/ubuntu/Kite-Swing-Trading-Analytics
ExecStart=/usr/bin/python3 /home/ubuntu/Kite-Swing-Trading-Analytics/gtt_api_server.py
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF

# Reload systemd
systemctl daemon-reload

# Enable service to start on boot
systemctl enable gtt-dashboard

# Start the service
systemctl start gtt-dashboard

print_success "Systemd service configured and started"

################################################################################
# FINAL STEPS
################################################################################
echo ""
echo -e "${GREEN}"
echo "╔════════════════════════════════════════════════════════════╗"
echo "║            🎉 Deployment Completed Successfully! 🎉       ║"
echo "╚════════════════════════════════════════════════════════════╝"
echo -e "${NC}"
echo ""

# Get public IP
PUBLIC_IP=$(curl -s ifconfig.me)

echo -e "${GREEN}Your GTT Trading Dashboard is now running!${NC}"
echo ""
echo "📊 Dashboard URL: ${BLUE}http://$PUBLIC_IP:5002${NC}"
echo ""
echo "🔧 Useful Commands:"
echo "  • Check status:  ${YELLOW}sudo systemctl status gtt-dashboard${NC}"
echo "  • View logs:     ${YELLOW}sudo journalctl -u gtt-dashboard -f${NC}"
echo "  • Restart:       ${YELLOW}sudo systemctl restart gtt-dashboard${NC}"
echo "  • Stop:          ${YELLOW}sudo systemctl stop gtt-dashboard${NC}"
echo ""
echo "📝 Next Steps:"
echo "  1. Open your browser"
echo "  2. Go to: http://$PUBLIC_IP:5002"
echo "  3. Your dashboard should be running!"
echo ""
echo "⚠️  Important Reminders:"
echo "  • Make sure Oracle Cloud Security List allows port 5002"
echo "  • The service will auto-start on server reboot"
echo "  • Logs are available via: sudo journalctl -u gtt-dashboard"
echo ""

# Check service status
sleep 3
if systemctl is-active --quiet gtt-dashboard; then
    print_success "Service is running successfully!"
else
    print_error "Service failed to start. Check logs with: sudo journalctl -u gtt-dashboard -n 50"
fi

echo ""
echo -e "${BLUE}════════════════════════════════════════════════════════════${NC}"
echo ""
