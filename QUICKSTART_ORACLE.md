# 🚀 Quick Start: Automated Oracle Cloud Deployment

## What You'll Do

1. **Create Oracle Cloud account** (10 min) - Manual
2. **Create VM instance** (5 min) - Manual  
3. **Run automated script** (15 min) - Automatic

**Total Time: ~30 minutes**

---

## Step-by-Step Instructions

### STEP 1: Create Oracle Cloud Account

1. Go to: https://www.oracle.com/cloud/free/
2. Click "Start for free"
3. Fill in your details and verify email
4. Add credit card (for verification only - won't be charged)
5. Wait for account to be ready

### STEP 2: Create VM Instance

1. **In Oracle Cloud Console:**
   - Click ☰ → Compute → Instances → "Create Instance"

2. **Configure:**
   - Name: `gtt-dashboard`
   - Image: Ubuntu 22.04
   - Shape: Ampere (VM.Standard.A1.Flex)
     - OCPUs: 2, Memory: 12GB
   - ✅ Check "Assign a public IPv4 address"
   - SSH Keys: "Generate a key pair for me"
   - **Download and save the SSH keys!**

3. **Add Firewall Rule:**
   - Go to: Networking → Virtual Cloud Networks → Your VCN → Security Lists
   - Add Ingress Rule:
     - Source: `0.0.0.0/0`
     - Protocol: TCP
     - Port: `5002`

4. **Copy your Public IP address**

### STEP 3: Connect to Server

**On Windows PowerShell:**

```powershell
# Setup SSH key
mkdir $HOME\.ssh -ErrorAction SilentlyContinue
Move-Item "Downloads\ssh-key-*.key" "$HOME\.ssh\oracle-key.key"
icacls "$HOME\.ssh\oracle-key.key" /inheritance:r
icacls "$HOME\.ssh\oracle-key.key" /grant:r "$($env:USERNAME):(R)"

# Connect (replace YOUR_IP with your actual IP)
ssh -i $HOME\.ssh\oracle-key.key ubuntu@YOUR_IP
```

### STEP 4: Run Automated Script

**On the server, run:**

```bash
# Download script
wget https://raw.githubusercontent.com/jeswinjoy93/Kite-Swing-Trading-Analytics/main/deploy_oracle.sh

# Make executable
chmod +x deploy_oracle.sh

# Run it
sudo bash deploy_oracle.sh
```

**Enter your Kite credentials when prompted:**
- API Key
- API Secret
- User ID
- Password
- TOTP Secret

**Wait 10-15 minutes for completion.**

### STEP 5: Access Dashboard

Open browser: `http://YOUR_IP:5002`

**Done! Your dashboard is running 24/7 for FREE!** 🎉

---

## 📋 What You Need Ready

- ✅ Email address
- ✅ Credit/Debit card (verification only)
- ✅ Phone number
- ✅ Kite API credentials (api_key, api_secret, user_id, password, totp_secret)

---

## 🔧 Useful Commands

```bash
# Check status
sudo systemctl status gtt-dashboard

# View logs
sudo journalctl -u gtt-dashboard -f

# Restart
sudo systemctl restart gtt-dashboard
```

---

## ❓ Need Help?

- **Detailed guide**: See [AUTOMATED_DEPLOYMENT.md](file:///c:/Users/Teresa%20Pious/Downloads/KiteConnect/AUTOMATED_DEPLOYMENT.md)
- **Manual setup**: See [ORACLE_CLOUD_SETUP.md](file:///c:/Users/Teresa%20Pious/Downloads/KiteConnect/ORACLE_CLOUD_SETUP.md)
- **Troubleshooting**: See [DEPLOYMENT.md](file:///c:/Users/Teresa%20Pious/Downloads/KiteConnect/DEPLOYMENT.md)
