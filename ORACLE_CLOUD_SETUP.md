# Oracle Cloud Free Tier - Complete Setup Guide

This is a detailed, step-by-step guide to deploy your GTT Trading Dashboard on Oracle Cloud's **Always Free Tier** - completely FREE forever!

---

## 📋 What You'll Get (FREE Forever)

- **4 ARM-based vCPUs** (Ampere A1 processors)
- **24GB RAM** (can be split across multiple VMs)
- **200GB Block Storage**
- **10TB/month Outbound Data Transfer**
- **No credit card charges** - truly free!

---

## 🚀 Step-by-Step Setup

### Part 1: Create Oracle Cloud Account

#### Step 1.1: Sign Up
1. Visit [https://www.oracle.com/cloud/free/](https://www.oracle.com/cloud/free/)
2. Click **"Start for free"** button
3. Fill in your details:
   - **Email address** (use a valid email)
   - **Country/Territory** (select India)
   - Click **"Verify my email"**

#### Step 1.2: Email Verification
1. Check your email inbox
2. Click the verification link from Oracle
3. You'll be redirected back to continue signup

#### Step 1.3: Complete Account Details
1. **Account Information**:
   - Cloud Account Name (choose a unique name, e.g., `teresa-trading`)
   - Home Region (choose **India South (Hyderabad)** for best performance)
   
2. **Personal Information**:
   - First Name, Last Name
   - Address details
   - Mobile number

3. **Payment Verification** (Required but won't be charged):
   - Add credit/debit card details
   - Oracle will verify with a small temporary hold (₹2)
   - This will be refunded immediately
   - **Important**: You won't be charged unless you manually upgrade to paid

4. Click **"Complete Sign-Up"**

#### Step 1.4: Wait for Account Provisioning
- Account creation takes 2-5 minutes
- You'll receive an email when ready
- You'll be automatically logged into Oracle Cloud Console

---

### Part 2: Create Your Free VM Instance

#### Step 2.1: Navigate to Compute Instances
1. In Oracle Cloud Console, click the **☰ hamburger menu** (top left)
2. Go to **Compute** → **Instances**
3. Click **"Create Instance"** button

#### Step 2.2: Configure Instance Basics
1. **Name**: `gtt-trading-dashboard`
2. **Compartment**: Leave as default (root compartment)
3. **Placement**: Leave as default (Availability Domain AD-1)

#### Step 2.3: Choose Image and Shape (IMPORTANT!)

**Image Selection:**
1. Click **"Change Image"**
2. Select **"Canonical Ubuntu"**
3. Choose **"22.04"** (or latest LTS version)
4. Click **"Select Image"**

**Shape Selection (Critical for Free Tier):**
1. Click **"Change Shape"**
2. Select **"Ampere"** (ARM-based processors)
3. Choose **"VM.Standard.A1.Flex"**
4. Configure resources:
   - **Number of OCPUs**: `2` (or up to 4 if you want maximum)
   - **Amount of memory (GB)**: `12` (or up to 24 if using 4 OCPUs)
   
   > [!TIP]
   > Free tier allows total of 4 OCPUs and 24GB RAM. You can use all for one VM or split across multiple VMs.

5. Click **"Select Shape"**

#### Step 2.4: Configure Networking

**Primary VNIC Information:**
1. **Create new virtual cloud network**: Leave checked
2. **Create new public subnet**: Leave checked
3. **Assign a public IPv4 address**: **MUST be checked** ✓

> [!IMPORTANT]
> Make sure "Assign a public IPv4 address" is checked, or you won't be able to access your dashboard!

#### Step 2.5: Add SSH Keys

**Option A: Generate New SSH Key Pair (Recommended for beginners)**
1. Select **"Generate a key pair for me"**
2. Click **"Save Private Key"** - downloads `ssh-key-XXXX.key`
3. Click **"Save Public Key"** - downloads `ssh-key-XXXX.key.pub`
4. **IMPORTANT**: Save these files securely! You'll need the private key to connect.

**Option B: Use Your Own SSH Key (If you already have one)**
1. Select **"Upload public key files (.pub)"**
2. Click **"Choose Files"** and select your `.pub` file
3. Or paste your public key directly

#### Step 2.6: Configure Boot Volume
1. Leave default settings:
   - **Boot volume size**: 47 GB (default)
   - **Use in-transit encryption**: Checked

#### Step 2.7: Create the Instance
1. Review all settings
2. Click **"Create"** button
3. Wait 2-3 minutes for provisioning
4. Status will change from "PROVISIONING" → "RUNNING" (orange → green)

#### Step 2.8: Note Your Public IP Address
1. Once instance is running, you'll see **"Public IP address"**
2. **Copy this IP address** - you'll need it to connect
3. Example: `150.136.XX.XXX`

---

### Part 3: Configure Firewall Rules

Oracle Cloud has TWO firewalls you need to configure:

#### Step 3.1: Configure Oracle Cloud Security List

1. On your instance page, under **"Instance Details"**
2. Click on **"Subnet"** link (under Primary VNIC)
3. Click on **"Default Security List"** link
4. Click **"Add Ingress Rules"** button

**Add Rule for Port 5002:**
- **Source Type**: `CIDR`
- **Source CIDR**: `0.0.0.0/0` (allows access from anywhere)
- **IP Protocol**: `TCP`
- **Source Port Range**: Leave empty
- **Destination Port Range**: `5002`
- **Description**: `GTT Dashboard Access`
- Click **"Add Ingress Rules"**

**Add Rule for SSH (if not already present):**
- **Source CIDR**: `0.0.0.0/0`
- **IP Protocol**: `TCP`
- **Destination Port Range**: `22`
- **Description**: `SSH Access`
- Click **"Add Ingress Rules"**

#### Step 3.2: Configure Ubuntu Firewall (iptables)

You'll do this after connecting to the server in the next step.

---

### Part 4: Connect to Your Server

#### Step 4.1: Prepare SSH Key (Windows)

1. Open **PowerShell**
2. Move your private key to a safe location:
   ```powershell
   # Create .ssh directory if it doesn't exist
   mkdir $HOME\.ssh -ErrorAction SilentlyContinue
   
   # Move the key (adjust path to where you downloaded it)
   Move-Item "C:\Users\Teresa Pious\Downloads\ssh-key-*.key" "$HOME\.ssh\oracle-key.key"
   ```

3. Set proper permissions (Windows):
   ```powershell
   # Remove inheritance and set permissions
   icacls "$HOME\.ssh\oracle-key.key" /inheritance:r
   icacls "$HOME\.ssh\oracle-key.key" /grant:r "$($env:USERNAME):(R)"
   ```

#### Step 4.2: Connect via SSH

```powershell
# Connect to your Oracle Cloud instance
ssh -i $HOME\.ssh\oracle-key.key ubuntu@YOUR_PUBLIC_IP

# Example:
# ssh -i $HOME\.ssh\oracle-key.key ubuntu@150.136.XX.XXX
```

**First time connecting:**
- You'll see a message: "The authenticity of host... can't be established"
- Type `yes` and press Enter
- You should now be connected to your Ubuntu server!

#### Step 4.3: Configure Ubuntu Firewall

Once connected, run these commands:

```bash
# Install iptables-persistent for saving firewall rules
sudo apt update
sudo apt install iptables-persistent -y

# Allow port 5002 for your dashboard
sudo iptables -I INPUT 6 -m state --state NEW -p tcp --dport 5002 -j ACCEPT

# Save the rules
sudo netfilter-persistent save

# Verify the rule was added
sudo iptables -L -n | grep 5002
```

---

### Part 5: Install and Deploy Your Application

Now follow the **"Common Setup Steps"** from the main deployment guide:

#### Step 5.1: Install System Dependencies

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

#### Step 5.2: Clone Your Repository

```bash
# Clone from GitHub
git clone https://github.com/jeswinjoy93/Kite-Swing-Trading-Analytics.git
cd Kite-Swing-Trading-Analytics
```

#### Step 5.3: Install Python Dependencies

```bash
# Install required packages
pip3 install -r requirements.txt

# Install additional production packages
pip3 install gunicorn chromedriver-autoinstaller
```

#### Step 5.4: Configure Your Credentials

```bash
# Edit config.py with your Kite credentials
nano config.py
```

Add your credentials:
```python
api_key = "your_api_key"
api_secret = "your_api_secret"
user_id = "your_user_id"
password = "your_password"
totp_secret = "your_totp_secret"
```

Save: `Ctrl+O`, `Enter`, `Ctrl+X`

#### Step 5.5: Update Code for Headless Mode

```bash
# Edit the server file
nano gtt_api_server.py
```

Find line 34 where it says:
```python
driver = webdriver.Chrome()
```

Replace with:
```python
from selenium.webdriver.chrome.options import Options

chrome_options = Options()
chrome_options.add_argument("--headless")
chrome_options.add_argument("--no-sandbox")
chrome_options.add_argument("--disable-dev-shm-usage")
chrome_options.add_argument("--disable-gpu")

driver = webdriver.Chrome(options=chrome_options)
```

**Important**: Add the `from selenium.webdriver.chrome.options import Options` import at the top of the file (around line 11-14 with other imports).

Save: `Ctrl+O`, `Enter`, `Ctrl+X`

#### Step 5.6: Test Run (Optional but Recommended)

```bash
# Quick test to see if everything works
python3 gtt_api_server.py
```

- You should see the server starting
- If you see errors, check the troubleshooting section
- Press `Ctrl+C` to stop the test

#### Step 5.7: Set Up Systemd Service (Production)

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
User=ubuntu
WorkingDirectory=/home/ubuntu/Kite-Swing-Trading-Analytics
ExecStart=/usr/bin/python3 /home/ubuntu/Kite-Swing-Trading-Analytics/gtt_api_server.py
Restart=always
RestartSec=10

[Install]
WantedBy=multi-user.target
```

Save: `Ctrl+O`, `Enter`, `Ctrl+X`

Enable and start the service:
```bash
# Reload systemd
sudo systemctl daemon-reload

# Enable auto-start on boot
sudo systemctl enable gtt-dashboard

# Start the service
sudo systemctl start gtt-dashboard

# Check status
sudo systemctl status gtt-dashboard
```

You should see **"active (running)"** in green!

---

### Part 6: Access Your Dashboard

1. Open your web browser
2. Go to: `http://YOUR_PUBLIC_IP:5002`
3. Example: `http://150.136.XX.XXX:5002`

You should see your GTT Trading Dashboard! 🎉

---

## 🔧 Troubleshooting

### Issue: Can't Connect via SSH

**Solution 1: Check SSH key permissions**
```powershell
# On Windows PowerShell
icacls "$HOME\.ssh\oracle-key.key"
# Should only show your username with Read permissions
```

**Solution 2: Use verbose mode to see errors**
```powershell
ssh -v -i $HOME\.ssh\oracle-key.key ubuntu@YOUR_IP
```

**Solution 3: Verify Security List allows port 22**
- Go to Oracle Cloud Console
- Check Security List has ingress rule for port 22

### Issue: Can't Access Dashboard (Port 5002)

**Check 1: Is the service running?**
```bash
sudo systemctl status gtt-dashboard
```

**Check 2: Is port 5002 open?**
```bash
sudo netstat -tlnp | grep 5002
```

**Check 3: Check Oracle Cloud Security List**
- Verify you added ingress rule for port 5002
- Source CIDR should be `0.0.0.0/0`

**Check 4: Check Ubuntu firewall**
```bash
sudo iptables -L -n | grep 5002
```

### Issue: Chrome/Selenium Errors

**Install chromedriver-autoinstaller:**
```bash
pip3 install chromedriver-autoinstaller
```

Add to top of `gtt_api_server.py`:
```python
import chromedriver_autoinstaller
chromedriver_autoinstaller.install()
```

### Issue: Out of Memory

**Check memory usage:**
```bash
free -h
```

**If using 12GB RAM, consider upgrading to 24GB:**
1. Stop your instance in Oracle Cloud Console
2. Edit instance shape
3. Increase memory to 24GB
4. Start instance

### Issue: Instance Creation Fails (Out of Capacity)

Oracle Cloud free tier ARM instances are popular and sometimes unavailable.

**Solutions:**
1. Try a different Availability Domain (AD-2 or AD-3)
2. Try a different region (but this requires new account)
3. Try at different times of day (early morning often works better)
4. Keep trying - capacity becomes available regularly

---

## 📊 Monitoring Your Application

### View Real-time Logs
```bash
# Follow logs in real-time
sudo journalctl -u gtt-dashboard -f

# View last 50 lines
sudo journalctl -u gtt-dashboard -n 50
```

### Check Resource Usage
```bash
# Install htop
sudo apt install htop -y

# Monitor CPU and memory
htop
```

### Restart Service
```bash
sudo systemctl restart gtt-dashboard
```

### Stop Service
```bash
sudo systemctl stop gtt-dashboard
```

---

## 🔒 Security Best Practices

### 1. Change SSH Port (Optional but Recommended)
```bash
sudo nano /etc/ssh/sshd_config
# Change: Port 22 → Port 2222
sudo systemctl restart sshd
```

Remember to update Oracle Cloud Security List to allow port 2222!

### 2. Disable Password Authentication
```bash
sudo nano /etc/ssh/sshd_config
# Set: PasswordAuthentication no
sudo systemctl restart sshd
```

### 3. Set Up Automatic Security Updates
```bash
sudo apt install unattended-upgrades -y
sudo dpkg-reconfigure -plow unattended-upgrades
```

---

## 💡 Tips & Best Practices

1. **Bookmark your dashboard URL** for easy access
2. **Set up monitoring** to get alerts if the service goes down
3. **Regularly update your code** from GitHub
4. **Check logs weekly** for any authentication issues
5. **Monitor Oracle Cloud credits** (you get $300 for 30 days trial + Always Free)

---

## 🎉 Success Checklist

- ✅ Oracle Cloud account created
- ✅ VM instance running (Ampere A1, Ubuntu 22.04)
- ✅ Security Lists configured (ports 22, 5002)
- ✅ SSH connection working
- ✅ Ubuntu firewall configured
- ✅ Python dependencies installed
- ✅ Chrome installed and working
- ✅ Code updated for headless mode
- ✅ Systemd service running
- ✅ Dashboard accessible at `http://YOUR_IP:5002`

---

## 📞 Need Help?

If you encounter issues:
1. Check the troubleshooting section above
2. Review the main [DEPLOYMENT.md](file:///c:/Users/Teresa%20Pious/Downloads/KiteConnect/DEPLOYMENT.md) guide
3. Check Oracle Cloud documentation
4. Verify all steps were completed in order

**Your dashboard is now running 24/7 for FREE!** 🚀
