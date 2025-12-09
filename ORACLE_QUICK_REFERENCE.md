# Oracle Cloud Quick Reference Card

## 🔑 Essential Information

### Your Instance Details
- **Username**: `ubuntu`
- **SSH Command**: `ssh -i $HOME\.ssh\oracle-key.key ubuntu@YOUR_PUBLIC_IP`
- **Dashboard URL**: `http://YOUR_PUBLIC_IP:5002`

---

## ⚡ Quick Commands

### Connect to Server
```powershell
# From Windows PowerShell
ssh -i $HOME\.ssh\oracle-key.key ubuntu@YOUR_PUBLIC_IP
```

### Check Service Status
```bash
sudo systemctl status gtt-dashboard
```

### View Logs
```bash
# Real-time logs
sudo journalctl -u gtt-dashboard -f

# Last 50 lines
sudo journalctl -u gtt-dashboard -n 50
```

### Restart Service
```bash
sudo systemctl restart gtt-dashboard
```

### Update Code from GitHub
```bash
cd ~/Kite-Swing-Trading-Analytics
git pull origin main
sudo systemctl restart gtt-dashboard
```

### Check Memory Usage
```bash
free -h
```

### Check Disk Space
```bash
df -h
```

---

## 🔧 Common Tasks

### Stop the Dashboard
```bash
sudo systemctl stop gtt-dashboard
```

### Start the Dashboard
```bash
sudo systemctl start gtt-dashboard
```

### Disable Auto-start on Boot
```bash
sudo systemctl disable gtt-dashboard
```

### Enable Auto-start on Boot
```bash
sudo systemctl enable gtt-dashboard
```

---

## 🚨 Emergency Commands

### If Dashboard is Not Responding
```bash
# Check if service is running
sudo systemctl status gtt-dashboard

# Restart it
sudo systemctl restart gtt-dashboard

# Check logs for errors
sudo journalctl -u gtt-dashboard -n 100
```

### If Server is Running Out of Memory
```bash
# Check memory
free -h

# Restart the service to free memory
sudo systemctl restart gtt-dashboard
```

### If You Can't Connect via SSH
```powershell
# Use verbose mode to see errors
ssh -v -i $HOME\.ssh\oracle-key.key ubuntu@YOUR_IP
```

---

## 📍 Important Locations

### Application Directory
```bash
/home/ubuntu/Kite-Swing-Trading-Analytics
```

### Configuration File
```bash
/home/ubuntu/Kite-Swing-Trading-Analytics/config.py
```

### Service File
```bash
/etc/systemd/system/gtt-dashboard.service
```

### Log Files
```bash
# View with:
sudo journalctl -u gtt-dashboard
```

---

## 🔐 Security Checklist

- ✅ SSH key authentication enabled
- ✅ Oracle Cloud Security List configured (ports 22, 5002)
- ✅ Ubuntu firewall configured
- ✅ config.py has restricted permissions (600)
- ⬜ Changed SSH port from 22 to custom (optional)
- ⬜ Disabled password authentication (optional)

---

## 📊 Monitoring

### Check if Dashboard is Accessible
```bash
# From the server
curl http://localhost:5002

# Should return HTML content
```

### Check Port 5002 is Open
```bash
sudo netstat -tlnp | grep 5002
```

### Check Firewall Rules
```bash
sudo iptables -L -n | grep 5002
```

---

## 💰 Cost Tracking

- **Monthly Cost**: $0 (Always Free Tier)
- **Resources Used**: 
  - OCPUs: 2-4 (max 4 free)
  - RAM: 12-24GB (max 24GB free)
  - Storage: ~50GB (max 200GB free)

---

## 🔗 Useful Links

- **Oracle Cloud Console**: https://cloud.oracle.com/
- **Your Dashboard**: `http://YOUR_PUBLIC_IP:5002`
- **GitHub Repo**: https://github.com/jeswinjoy93/Kite-Swing-Trading-Analytics

---

## 📝 Notes

- Dashboard runs 24/7 automatically
- Auto-restarts on failure
- Survives server reboots
- Kite session refreshes daily (automatic)

---

**Save this file for quick reference!**
