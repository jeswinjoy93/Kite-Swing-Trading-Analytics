# Automated Oracle Cloud Deployment Guide

This guide uses an automated script to deploy your GTT Trading Dashboard to Oracle Cloud Free Tier with minimal manual work.

---

## 📋 What You Need to Do Manually

### Part 1: Create Oracle Cloud Account (~10 minutes)
You still need to create the account manually because it requires:
- Your email address
- Credit card verification (won't be charged)
- Personal information

**Follow these steps:**
1. Go to https://www.oracle.com/cloud/free/
2. Click "Start for free"
3. Fill in your details
4. Verify email
5. Complete payment verification
6. Wait for account provisioning

### Part 2: Create VM Instance (~5 minutes)
You need to create the VM manually in Oracle Cloud Console:

1. **Navigate to Instances**
   - Click ☰ menu → Compute → Instances
   - Click "Create Instance"

2. **Configure Instance**
   - **Name**: `gtt-dashboard`
   - **Image**: Click "Change Image" → Select "Canonical Ubuntu" → "22.04"
   - **Shape**: Click "Change Shape" → Select "Ampere" → "VM.Standard.A1.Flex"
     - OCPUs: 2 (or up to 4)
     - Memory: 12GB (or up to 24GB)
   - **Networking**: 
     - ✅ Create new virtual cloud network
     - ✅ Assign a public IPv4 address (IMPORTANT!)
   - **SSH Keys**: Select "Generate a key pair for me"
     - Download both private and public keys
     - Save them securely!

3. **Configure Security List**
   - Go to: Networking → Virtual Cloud Networks → Your VCN → Security Lists
   - Click "Add Ingress Rules"
   - Add rule for port 5002:
     - Source CIDR: `0.0.0.0/0`
     - IP Protocol: `TCP`
     - Destination Port: `5002`
   - Click "Add Ingress Rules"

4. **Note Your Public IP**
   - Once instance is running, copy the Public IP address
   - You'll need this to access your dashboard

---

## 🚀 Part 3: Run Automated Deployment Script

### Step 1: Connect to Your Server

Open PowerShell on Windows and connect via SSH:

```powershell
# Move your SSH key to a safe location
mkdir $HOME\.ssh -ErrorAction SilentlyContinue
Move-Item "C:\Users\Teresa Pious\Downloads\ssh-key-*.key" "$HOME\.ssh\oracle-key.key"

# Set permissions
icacls "$HOME\.ssh\oracle-key.key" /inheritance:r
icacls "$HOME\.ssh\oracle-key.key" /grant:r "$($env:USERNAME):(R)"

# Connect to server (replace YOUR_PUBLIC_IP with your actual IP)
ssh -i $HOME\.ssh\oracle-key.key ubuntu@YOUR_PUBLIC_IP
```

### Step 2: Download and Run the Deployment Script

Once connected to your server, run these commands:

```bash
# Download the deployment script
wget https://raw.githubusercontent.com/jeswinjoy93/Kite-Swing-Trading-Analytics/main/deploy_oracle.sh

# Make it executable
chmod +x deploy_oracle.sh

# Run the script with sudo
sudo bash deploy_oracle.sh
```

### Step 3: Provide Your Credentials

The script will ask for your Kite Connect credentials:
- API Key
- API Secret
- User ID
- Password
- TOTP Secret

**Enter them when prompted.**

### Step 4: Wait for Completion

The script will automatically:
- ✅ Update system packages
- ✅ Install Python, Git, Chrome
- ✅ Clone your repository
- ✅ Install Python dependencies
- ✅ Configure firewall
- ✅ Set up systemd service
- ✅ Start your dashboard

**This takes about 10-15 minutes.**

---

## 🎉 Step 4: Access Your Dashboard

Once the script completes, you'll see:
```
╔════════════════════════════════════════════════════════════╗
║            🎉 Deployment Completed Successfully! 🎉       ║
╚════════════════════════════════════════════════════════════╝

📊 Dashboard URL: http://YOUR_IP:5002
```

**Open your browser and go to that URL!**

---

## 🔧 Useful Commands

After deployment, you can manage your dashboard with these commands:

```bash
# Check if service is running
sudo systemctl status gtt-dashboard

# View real-time logs
sudo journalctl -u gtt-dashboard -f

# Restart the service
sudo systemctl restart gtt-dashboard

# Stop the service
sudo systemctl stop gtt-dashboard

# Start the service
sudo systemctl start gtt-dashboard
```

---

## 🛠️ Troubleshooting

### Issue: Script fails to download
**Solution**: Upload the script manually
```bash
# On your Windows machine
scp -i $HOME\.ssh\oracle-key.key "C:\Users\Teresa Pious\Downloads\KiteConnect\deploy_oracle.sh" ubuntu@YOUR_IP:/home/ubuntu/

# Then on the server
chmod +x deploy_oracle.sh
sudo bash deploy_oracle.sh
```

### Issue: Can't access dashboard at port 5002
**Check Oracle Cloud Security List:**
1. Go to Oracle Cloud Console
2. Networking → Virtual Cloud Networks → Your VCN → Security Lists
3. Verify ingress rule for port 5002 exists

**Check Ubuntu firewall:**
```bash
sudo iptables -L -n | grep 5002
```

### Issue: Service won't start
**Check logs:**
```bash
sudo journalctl -u gtt-dashboard -n 50
```

**Common causes:**
- Missing credentials in config.py
- Chrome not installed properly
- Python dependencies missing

---

## 📊 What the Script Does

The automated script handles:

1. **System Setup**
   - Updates all packages
   - Installs Python 3, pip, git
   - Installs screen, wget, curl, htop

2. **Chrome Installation**
   - Downloads Google Chrome
   - Installs ChromeDriver automatically

3. **Application Setup**
   - Clones your GitHub repository
   - Installs all Python dependencies
   - Creates config.py with your credentials

4. **Firewall Configuration**
   - Opens port 5002 in iptables
   - Saves firewall rules permanently

5. **Service Setup**
   - Creates systemd service file
   - Enables auto-start on boot
   - Starts the dashboard service

---

## ✅ Success Checklist

After running the script, verify:
- ✅ Service is running: `sudo systemctl status gtt-dashboard`
- ✅ Port 5002 is open: `sudo netstat -tlnp | grep 5002`
- ✅ Dashboard accessible: Open `http://YOUR_IP:5002` in browser
- ✅ Auto-start enabled: `sudo systemctl is-enabled gtt-dashboard`

---

## 💡 Time Savings

**Manual Setup**: ~40 minutes  
**Automated Setup**: ~20 minutes (after VM creation)  
**Time Saved**: ~20 minutes! 🎉

---

## 🔐 Security Notes

The script automatically:
- Sets proper file permissions on config.py (600)
- Configures firewall rules
- Sets up the service to run as ubuntu user (not root)

**Additional security (optional):**
- Change SSH port from 22
- Disable password authentication
- Set up fail2ban

---

## 📝 Summary

**You do manually:**
1. Create Oracle Cloud account (10 min)
2. Create VM instance (5 min)
3. Run one command: `sudo bash deploy_oracle.sh` (15 min automated)

**Total time: ~30 minutes** (vs 40+ minutes manual setup)

**Your dashboard will be running 24/7 for FREE!** 🚀
