# Cloud Deployment Guide - Cost-Effective Options

This guide shows you how to run your GTT Trading Dashboard 24/7 in the cloud **without breaking the bank**. We'll cover options from **completely FREE** to budget-friendly paid solutions.

---

## 📊 Cost Comparison Table

| Provider | Monthly Cost | RAM | CPU | Storage | Best For | Setup Difficulty |
|----------|--------------|-----|-----|---------|----------|------------------|
| **Oracle Cloud (Free Tier)** | **$0 Forever** | 24GB | 4 vCPU (ARM) | 200GB | Best value! | Medium |
| **Server Host** | $2/month | 2GB | 1 vCPU | 30GB | Ultra budget | Easy |
| **IONOS VPS** | $2/month | 1GB | 1 vCPU | 10GB | Minimal projects | Easy |
| **InterServer** | $3/month | 2GB | 1 vCPU | 30GB SSD | Good balance | Easy |
| **Hostinger** | $4.49/month | 4GB | 1 vCPU | 50GB | Great value | Easy |
| **OVHcloud** | $5.50/month | 2GB | 1 vCPU | 40GB | Reliable | Easy |
| **DigitalOcean** | $6/month | 1GB | 1 vCPU | 25GB | Developer-friendly | Easy |

> [!TIP]
> **Recommended Choice**: Oracle Cloud Free Tier offers the best specs for FREE forever. If you want simplicity, go with **Server Host** ($2/month) or **InterServer** ($3/month).

---

## 🎯 Option 1: Oracle Cloud Free Tier (RECOMMENDED - $0 Forever!)

Oracle Cloud offers an **Always Free** tier that includes:
- **4 ARM-based vCPUs** (Ampere A1)
- **24GB RAM** (can split into multiple VMs)
- **200GB Block Storage**
- **10TB/month Outbound Data Transfer**
- **No credit card charges** - truly free forever!

### Setup Steps for Oracle Cloud

#### 1. Create Oracle Cloud Account
1. Visit [oracle.com/cloud/free](https://www.oracle.com/cloud/free/)
2. Sign up (requires credit card for verification but won't be charged)
3. Choose your home region (closest to you)

#### 2. Create a Free Tier VM
```bash
# In Oracle Cloud Console:
# 1. Go to: Compute → Instances → Create Instance
# 2. Name: gtt-dashboard
# 3. Image: Ubuntu 22.04 (Minimal)
# 4. Shape: Ampere (VM.Standard.A1.Flex)
# 5. OCPUs: 2, Memory: 12GB (or 4 OCPUs, 24GB for single VM)
# 6. Networking: Create new VCN with default settings
# 7. Add SSH Key (generate or upload your public key)
# 8. Click "Create"
```

#### 3. Configure Firewall
```bash
# In Oracle Cloud Console:
# 1. Go to: Networking → Virtual Cloud Networks → Your VCN → Security Lists
# 2. Add Ingress Rule:
#    - Source CIDR: 0.0.0.0/0
#    - Destination Port: 5002
#    - Protocol: TCP

# Also configure Ubuntu firewall on the VM:
ssh ubuntu@<your_vm_ip>
sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport 5002 -j ACCEPT
sudo netfilter-persistent save
```

#### 4. Continue with "Common Setup Steps" below

---

## 💰 Option 2: Budget VPS Providers ($2-6/month)

### Recommended: Server Host ($2/month)
- **Specs**: 2GB RAM, 1 vCPU, 30GB Storage
- **Website**: Check LowEndBox for deals
- **Setup**: Standard Ubuntu VPS

### Alternative: InterServer ($3/month)
- **Specs**: 2GB RAM, 1 vCPU, 30GB SSD
- **Website**: [interserver.net](https://www.interserver.net)
- **Setup**: Standard Ubuntu VPS

### Setup Steps for Budget VPS
1. Purchase VPS with Ubuntu 22.04
2. Receive SSH credentials via email
3. SSH into server: `ssh root@<your_server_ip>`
4. Continue with "Common Setup Steps" below

---

## 🚀 Common Setup Steps (All Providers)

### 1. Connect to Your Server
```bash
# From your Windows PowerShell:
ssh root@<your_server_ip>
# Or: ssh ubuntu@<your_server_ip> (for Oracle Cloud)
```

### 2. Install System Dependencies
```bash
# Update system
sudo apt update && sudo apt upgrade -y

# Install Python and essential tools
sudo apt install python3-pip python3-venv git unzip screen -y

# Install Google Chrome (required for Selenium)
wget https://dl.google.com/linux/direct/google-chrome-stable_current_amd64.deb
sudo apt install ./google-chrome-stable_current_amd64.deb -y

# Verify Chrome installation
google-chrome --version
```

### 3. Clone Your Repository
```bash
# Clone from GitHub
git clone https://github.com/jeswinjoy93/Kite-Swing-Trading-Analytics.git
cd Kite-Swing-Trading-Analytics

# Or upload files using SCP from your Windows machine:
# scp -r "C:\Users\Teresa Pious\Downloads\KiteConnect" root@<server_ip>:/root/
```

### 4. Install Python Dependencies
```bash
# Install required packages
pip3 install -r requirements.txt

# Install additional production packages
pip3 install gunicorn chromedriver-autoinstaller
```

### 5. Configure Your Credentials
```bash
# Edit config.py with your Kite credentials
nano config.py

# Add your credentials:
# api_key = "your_api_key"
# api_secret = "your_api_secret"
# user_id = "your_user_id"
# password = "your_password"
# totp_secret = "your_totp_secret"

# Save: Ctrl+O, Enter, Ctrl+X
```

### 6. Update Code for Headless Mode
```bash
# Edit the server file
nano gtt_api_server.py
```

Find the `initialize_kite_session()` function (around line 32-34) and **replace**:
```python
driver = webdriver.Chrome()
```

**With this:**
```python
from selenium.webdriver.chrome.options import Options

chrome_options = Options()
chrome_options.add_argument("--headless")  # Run without GUI
chrome_options.add_argument("--no-sandbox")
chrome_options.add_argument("--disable-dev-shm-usage")
chrome_options.add_argument("--disable-gpu")

driver = webdriver.Chrome(options=chrome_options)
```

Save the file: `Ctrl+O`, `Enter`, `Ctrl+X`

### 7. Run the Application (Persistent)

#### Option A: Using Screen (Simple)
```bash
# Start a screen session
screen -S dashboard

# Run the server
python3 gtt_api_server.py

# Detach from screen (keeps running)
# Press: Ctrl+A, then D

# To reconnect later:
screen -r dashboard

# To stop the server:
screen -r dashboard
# Then press Ctrl+C
```

#### Option B: Using Systemd (Auto-restart on reboot)
```bash
# Create service file
sudo nano /etc/systemd/system/gtt-dashboard.service
```

Paste this content:
```ini
[Unit]
Description=GTT Trading Dashboard
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=/root/Kite-Swing-Trading-Analytics
ExecStart=/usr/bin/python3 /root/Kite-Swing-Trading-Analytics/gtt_api_server.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Save and enable:
```bash
# Reload systemd
sudo systemctl daemon-reload

# Enable auto-start on boot
sudo systemctl enable gtt-dashboard

# Start the service
sudo systemctl start gtt-dashboard

# Check status
sudo systemctl status gtt-dashboard

# View logs
sudo journalctl -u gtt-dashboard -f
```

### 8. Configure Firewall
```bash
# Allow port 5002
sudo ufw allow 5002/tcp
sudo ufw enable
```

### 9. Access Your Dashboard
Open your browser and visit:
```
http://<your_server_ip>:5002
```

---

## 🔒 Security Best Practices

> [!WARNING]
> Your dashboard is now accessible from the internet. Follow these security steps:

### 1. Change Default SSH Port
```bash
sudo nano /etc/ssh/sshd_config
# Change: Port 22 → Port 2222
sudo systemctl restart sshd
```

### 2. Set Up SSH Key Authentication
```bash
# On your Windows machine (PowerShell):
ssh-keygen -t rsa -b 4096

# Copy public key to server:
scp ~/.ssh/id_rsa.pub root@<server_ip>:/root/.ssh/authorized_keys
```

### 3. Disable Password Authentication
```bash
sudo nano /etc/ssh/sshd_config
# Set: PasswordAuthentication no
sudo systemctl restart sshd
```

### 4. Keep Credentials Secure
```bash
# Ensure config.py is not publicly accessible
chmod 600 config.py

# Never commit config.py to GitHub
# (Already in .gitignore)
```

---

## 🛠️ Troubleshooting

### Issue: Chrome/ChromeDriver Not Found
```bash
# Install chromedriver-autoinstaller
pip3 install chromedriver-autoinstaller

# Add to your code (top of gtt_api_server.py):
import chromedriver_autoinstaller
chromedriver_autoinstaller.install()
```

### Issue: Selenium Fails in Headless Mode
```bash
# Check Chrome version
google-chrome --version

# Test headless mode manually
google-chrome --headless --disable-gpu --dump-dom https://www.google.com
```

### Issue: Port 5002 Not Accessible
```bash
# Check if app is running
sudo netstat -tlnp | grep 5002

# Check firewall
sudo ufw status

# For Oracle Cloud, also check Security Lists in console
```

### Issue: Application Crashes
```bash
# Check logs
sudo journalctl -u gtt-dashboard -n 50

# Check memory usage
free -h

# Restart service
sudo systemctl restart gtt-dashboard
```

### Issue: Kite Authentication Fails
```bash
# Verify credentials in config.py
cat config.py

# Test TOTP generation
python3 -c "import pyotp; print(pyotp.TOTP('your_totp_secret').now())"

# Check if Chrome can access Kite website
curl -I https://kite.zerodha.com
```

---

## 📈 Monitoring & Maintenance

### Check Application Status
```bash
# Using systemd
sudo systemctl status gtt-dashboard

# Using screen
screen -ls
screen -r dashboard
```

### View Logs
```bash
# Real-time logs
sudo journalctl -u gtt-dashboard -f

# Last 100 lines
sudo journalctl -u gtt-dashboard -n 100
```

### Update Your Code
```bash
cd /root/Kite-Swing-Trading-Analytics
git pull origin main
sudo systemctl restart gtt-dashboard
```

### Monitor Resource Usage
```bash
# Check memory and CPU
htop

# Check disk space
df -h
```

---

## 💡 Cost Optimization Tips

1. **Start with Oracle Cloud Free Tier** - It's free forever and has excellent specs
2. **Use ARM instances** - Cheaper and more efficient than x86
3. **Monitor bandwidth usage** - Most providers include enough for this app
4. **Set up auto-shutdown** - If you only need it during market hours (advanced)
5. **Use spot instances** - For even cheaper hosting (AWS/GCP)

---

## 🎉 Next Steps

Once deployed, your dashboard will:
- ✅ Run 24/7 without your laptop
- ✅ Auto-restart on crashes
- ✅ Survive server reboots
- ✅ Be accessible from anywhere

**Access your dashboard at**: `http://<your_server_ip>:5002`

> [!IMPORTANT]
> Remember to keep your Kite API credentials secure and never share your server IP publicly if it contains sensitive trading data.
