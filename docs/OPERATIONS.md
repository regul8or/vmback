# Operations Manual

Complete guide for deploying and operating vmback in production.

## Table of Contents

- [Prerequisites](#prerequisites)
- [Installation](#installation)
- [Deployment Scenarios](#deployment-scenarios)
- [Scheduled Backups](#scheduled-backups)
- [Backup Operations](#backup-operations)
- [Monitoring and Maintenance](#monitoring-and-maintenance)
- [Disaster Recovery](#disaster-recovery)
- [Troubleshooting](#troubleshooting)
- [Performance Tuning](#performance-tuning)

## Prerequisites

### System Requirements

**Minimum:**
- Python 3.7 or higher
- 2 GB RAM
- Network connectivity to XCP-ng host
- Sufficient storage for backups

**Recommended:**
- Python 3.9+
- 4 GB RAM
- Dedicated network interface for backup traffic
- Fast storage (SSD, NFS, iSCSI)

### XCP-ng/XenServer Requirements

- XCP-ng 8.2+ or XenServer 8.0+
- Network access to pool master
- Valid user credentials with backup permissions

### Software Dependencies

#### Python Packages

```bash
pip install -r requirements.txt
```

Required packages:
- PyYAML >= 5.1
- python-dotenv >= 0.19.0
- XenAPI >= 1.2
- requests >= 2.25.0
- urllib3 >= 1.26.0
- tqdm >= 4.60.0 (optional, for progress bars)

#### XenAPI Installation

**Option 1: PyPI (recommended)**
```bash
pip install XenAPI
```

**Option 2: From XenServer SDK**

1. Download SDK from [xenserver.com/downloads](https://www.xenserver.com/downloads)
2. Extract the archive
3. Install Python bindings:
   ```bash
   cd XenServerSDK/XenServerPython
   python setup.py install
   ```

#### xe CLI (Optional, for legacy mode)

**NOT included in XCP-ng Center!**

1. Download XenCenter from [xenserver.com/downloads](https://www.xenserver.com/downloads)
2. Install XenCenter on Windows
3. Add xe CLI to system PATH:
   - Default location: `C:\Program Files (x86)\Citrix\XenCenter`
   - Add to PATH environment variable

**Linux alternative:**
```bash
# Install xe CLI from XCP-ng repos
yum install xe-cli
```

## Installation

### Standard Installation

```bash
# Clone repository
git clone https://github.com/yourusername/vmback.git
cd vmback

# Install dependencies
pip install -r requirements.txt

# Verify installation
python -m vmback --help
```

### Virtual Environment (Recommended)

```bash
# Create virtual environment
python3 -m venv venv

# Activate (Linux/macOS)
source venv/bin/activate

# Activate (Windows)
venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt
```

### System-Wide Installation

```bash
# Install package
pip install .

# Or in development mode
pip install -e .

# Verify
vmback --help
```

## Deployment Scenarios

### Home Lab

**Characteristics:**
- Single server or small pool
- USB or local disk storage
- On-demand or daily backups
- Interactive monitoring

**Configuration:**
```yaml
credentials:
  username: root
  password: homelab-pass

env:
  backup-path: 'X:\backup\vm'
  log-path: 'X:\backup\log'

export:
  method: 'http'

resilience:
  log:
    on_error: 'warn'      # USB might sleep
  backup:
    on_error: 'warn'      # Try all VMs
  hooks:
    on_error: 'continue'  # Don't fail on hook errors

pools:
  - id: Home
    hosts: [ 192.168.1.49 ]
    scope: [ 'metadata', 'vm' ]

vms:
  - vm-uuid: 'all'
```

**Deployment:**
- Manual runs when needed
- Simple Task Scheduler (Windows) or cron (Linux)
- Logs reviewed manually

### Small Business / Branch Office

**Characteristics:**
- 5-20 VMs
- NAS or local storage
- Daily automated backups
- Email notifications

**Configuration:**
```yaml
credentials-file: /etc/vmback/credentials.yaml

env:
  backup-path: /mnt/nas/backup/vm
  log-path: /var/log/vmback

export:
  method: 'http'
  http:
    chunk_size: 8388608

resilience:
  backup:
    on_error: 'warn'      # Try all VMs

pools:
  - id: Office
    hosts: [ 10.0.1.100 ]
    scope: [ 'metadata', 'vm' ]

after:
  job:
    - 'mail -s "Backup Complete" admin@company.com < /var/log/vmback/latest.log'
```

**Deployment:**
- Systemd timer (Linux) or Task Scheduler (Windows)
- Daily at 2 AM
- Email notifications on completion

### Enterprise Production

**Characteristics:**
- Multiple pools, 50+ VMs
- Dedicated backup infrastructure
- 10GbE network
- Tiered storage with deduplication
- Integration with monitoring systems

**Configuration:**
```yaml
credentials-file: /etc/vmback/credentials.yaml

env:
  backup-path: /mnt/iscsi/backup
  log-path: /var/log/vmback

export:
  method: 'http'
  http:
    scheme: 'https'
    verify_ssl: true
    chunk_size: 16777216    # 16MB for 10GbE

resilience:
  backup:
    on_error: 'fail'        # Stop on error in production

pools:
  - id: Prod-Pool-1
    hosts: [ 10.10.1.100 ]
    scope: [ 'metadata', 'vdi' ]
  
  - id: Prod-Pool-2
    hosts: [ 10.10.2.100 ]
    scope: [ 'metadata', 'vdi' ]

vdi:
  - vm-uuid: 'all'

after:
  job:
    # Deduplicate with borg
    - 'borg create /mnt/borg::vmback-{y}{m}{d} /mnt/iscsi/backup'
    # Send metrics to monitoring
    - 'curl -X POST https://monitoring.company.com/metrics -d @metrics.json'
```

**Deployment:**
- Dedicated backup server
- Systemd service with multiple timers
- Integration with monitoring (Prometheus, Grafana)
- Automated testing of restores

## Scheduled Backups

### Linux - Systemd

**Service file:** `/etc/systemd/system/vmback@.service`

```ini
[Unit]
Description=VM Backup (%i)
After=network-online.target

[Service]
Type=oneshot
User=backup
Group=backup
WorkingDirectory=/opt/vmback
ExecStart=/usr/bin/python3 -m vmback -c /etc/vmback/%i.yaml backup
StandardOutput=journal
StandardError=journal
SyslogIdentifier=vmback-%i

# Security hardening
NoNewPrivileges=true
PrivateTmp=true
ProtectSystem=strict
ProtectHome=true
ReadWritePaths=/mnt/backup /var/log/vmback

[Install]
WantedBy=multi-user.target
```

**Timer file:** `/etc/systemd/system/vmback@.timer`

```ini
[Unit]
Description=VM Backup Timer (%i)

[Timer]
OnCalendar=daily
OnCalendar=02:00
Persistent=true
RandomizedDelaySec=300

[Install]
WantedBy=timers.target
```

**Deployment:**

```bash
# Install files
sudo cp vmback@.service /etc/systemd/system/
sudo cp vmback@.timer /etc/systemd/system/

# Create configuration
sudo mkdir -p /etc/vmback
sudo cp config.yaml /etc/vmback/production.yaml

# Enable and start
sudo systemctl enable vmback@production.timer
sudo systemctl start vmback@production.timer

# Check status
sudo systemctl status vmback@production.timer
sudo systemctl list-timers
```

**Multiple schedules:**

```bash
# Daily full backup
sudo cp daily.yaml /etc/vmback/daily.yaml
sudo systemctl enable vmback@daily.timer
sudo systemctl start vmback@daily.timer

# Hourly incremental
sudo cp hourly.yaml /etc/vmback/hourly.yaml
sudo systemctl enable vmback@hourly.timer
sudo systemctl start vmback@hourly.timer
```

### Linux - Cron

```bash
# Edit crontab
crontab -e

# Daily at 2 AM
0 2 * * * /usr/bin/python3 -m vmback -c /etc/vmback/config.yaml backup >> /var/log/vmback/cron.log 2>&1

# Weekly full backup (Sunday 3 AM)
0 3 * * 0 /usr/bin/python3 -m vmback -c /etc/vmback/weekly.yaml backup >> /var/log/vmback/weekly.log 2>&1
```

### Windows - Task Scheduler

**PowerShell script:** `C:\Backup\run-vmback.ps1`

```powershell
# Set paths
$vmbackPath = "C:\Backup\vmback"
$configPath = "C:\Backup\config.yaml"
$logPath = "C:\Backup\logs"

# Change to vmback directory
Set-Location $vmbackPath

# Run backup
python -m vmback -c $configPath backup

# Check exit code
if ($LASTEXITCODE -ne 0) {
    # Send email notification on failure
    Send-MailMessage -To "admin@company.com" `
                     -From "backup@company.com" `
                     -Subject "Backup Failed" `
                     -Body "vmback exited with code $LASTEXITCODE" `
                     -SmtpServer "smtp.company.com"
    exit $LASTEXITCODE
}
```

**Create scheduled task:**

```powershell
# Create task action
$action = New-ScheduledTaskAction `
    -Execute "powershell.exe" `
    -Argument "-ExecutionPolicy Bypass -File C:\Backup\run-vmback.ps1"

# Create trigger (daily at 2 AM)
$trigger = New-ScheduledTaskTrigger -Daily -At "02:00AM"

# Create task settings
$settings = New-ScheduledTaskSettingsSet `
    -StartWhenAvailable `
    -RunOnlyIfNetworkAvailable `
    -DontStopIfGoingOnBatteries

# Register task
Register-ScheduledTask `
    -TaskName "VMBackup-Daily" `
    -Action $action `
    -Trigger $trigger `
    -Settings $settings `
    -User "SYSTEM" `
    -RunLevel Highest
```

**GUI method:**

1. Open Task Scheduler
2. Create Basic Task
3. Name: "VMBackup-Daily"
4. Trigger: Daily at 2:00 AM
5. Action: Start a program
   - Program: `powershell.exe`
   - Arguments: `-ExecutionPolicy Bypass -File C:\Backup\run-vmback.ps1`
6. Settings:
   - ✓ Run whether user is logged on or not
   - ✓ Run with highest privileges
   - ✓ Start task as soon as possible after scheduled start is missed

## Backup Operations

### Interactive Backup

```bash
# Run backup with verbose output
python -m vmback -v -c config.yaml backup

# List VMs before backing up
python -m vmback -c config.yaml vm

# List VDIs
python -m vmback -c config.yaml vdi
```

### Automated Backup

```bash
# Run in service mode (no TTY)
python -m vmback -c /etc/vmback/config.yaml backup

# Output goes to:
# - Log file: /var/log/vmback/vmback-YYYYMMDD-HHMMSS.log
# - Stdout (WARNING+): for systemd journal
```

### Selective Backup

**Single VM:**
```yaml
vms:
  - vm-uuid: '3b2b64fb-b3ab-613e-a8a0-e89450c27e05'
```

**Specific pattern:**
```yaml
vms:
  - vm-uuid: 'all'
    include:
      - '^Production.*'
```

### Testing Configuration

```bash
# Validate configuration
python -m vmback -c config.yaml vm

# Dry run (list only, don't backup)
python -m vmback -c config.yaml vm > vm-list.txt
cat vm-list.txt
```

## Monitoring and Maintenance

### Log Management

**Log files:**
- Location: `{log-path}/vmback-YYYYMMDD-HHMMSS.log`
- Format: Timestamped, leveled messages
- Rotation: One file per run

**Log rotation script:**

```bash
#!/bin/bash
# /etc/cron.daily/vmback-logrotate

LOG_DIR="/var/log/vmback"
KEEP_DAYS=30

# Delete old logs
find "$LOG_DIR" -name "vmback-*.log" -mtime +$KEEP_DAYS -delete

# Compress logs older than 7 days
find "$LOG_DIR" -name "vmback-*.log" -mtime +7 -exec gzip {} \;
```

### Monitoring Integration

**Systemd journal:**
```bash
# View vmback logs
journalctl -u vmback@production.service

# Follow logs
journalctl -u vmback@production.service -f

# Today's logs
journalctl -u vmback@production.service --since today
```

**Syslog integration:**
```yaml
after:
  job:
    - 'logger -t vmback "Backup completed: $? exit code"'
```

**Metrics export:**
```yaml
after:
  job:
    - 'python /opt/vmback/export-metrics.py > /var/lib/prometheus/vmback.prom'
```

### Health Checks

**Check last backup:**
```bash
#!/bin/bash
# Check if backup ran in last 25 hours

BACKUP_DIR="/mnt/backup/vm"
ALERT_EMAIL="admin@company.com"

LATEST=$(find "$BACKUP_DIR" -name "*.xva" -mtime -1 | head -1)

if [ -z "$LATEST" ]; then
    echo "No backup in last 24 hours!" | mail -s "BACKUP ALERT" $ALERT_EMAIL
    exit 1
fi

echo "Latest backup: $LATEST"
```

**Verify backup integrity:**
```bash
#!/bin/bash
# Verify XVA files are valid

for xva in /mnt/backup/vm/*.xva; do
    if ! tar -tzf "$xva" > /dev/null 2>&1; then
        echo "CORRUPT: $xva"
        exit 1
    fi
done

echo "All backups verified"
```

### Backup Rotation

**Grandfather-Father-Son (GFS):**

```yaml
after:
  job:
    # Keep daily backups for 7 days
    - 'find /mnt/backup/vm -name "*.xva" -mtime +7 -not -name "*-weekly-*" -not -name "*-monthly-*" -delete'
    
    # Weekly backups (Sundays)
    - 'if [ $(date +%u) -eq 7 ]; then cp /mnt/backup/vm/*.xva /mnt/backup/weekly/; fi'
    
    # Monthly backups (1st of month)
    - 'if [ $(date +%d) -eq 01 ]; then cp /mnt/backup/vm/*.xva /mnt/backup/monthly/; fi'
```

**Tiered retention:**
```bash
#!/bin/bash
# /opt/vmback/rotate-backups.sh

BACKUP_DIR="/mnt/backup/vm"

# Keep last 7 daily backups
find "$BACKUP_DIR/daily" -name "*.xva" -mtime +7 -delete

# Keep 4 weekly backups
find "$BACKUP_DIR/weekly" -name "*.xva" -mtime +28 -delete

# Keep 12 monthly backups
find "$BACKUP_DIR/monthly" -name "*.xva" -mtime +365 -delete
```

## Disaster Recovery

### Restore Procedures

**Full VM restore:**

```bash
# Using XenCenter GUI
1. File → Import
2. Select .xva file
3. Choose destination SR
4. Wait for import to complete

# Using xe CLI
xe vm-import filename=/path/to/backup.xva
```

**Individual VDI restore:**

```bash
# Import VHD
xe vdi-import filename=/path/to/backup.vhd sr-uuid=<SR-UUID>

# Attach to VM
xe vbd-create vm-uuid=<VM-UUID> vdi-uuid=<VDI-UUID> device=xvda
```

**Pool metadata restore:**

```bash
# Restore pool configuration
xe pool-restore-database file-name=/path/to/pool.xml
```

### Testing Restores

**Regular restore testing schedule:**

```yaml
# Monthly restore test configuration
pools:
  - id: Test-Restore
    hosts: [ 192.168.100.100 ]  # Test pool
    scope: [ 'vm' ]

vms:
  - vm-uuid: '3b2b64fb-b3ab-613e-a8a0-e89450c27e05'
    vm-name: 'Production-DB'

after:
  vm:
    # Import to test pool
    - 'xe vm-import filename="{vm_name}.xva" sr-uuid=<test-sr-uuid> preserve=false'
    # Start VM
    - 'xe vm-start vm="{vm_name}-restored"'
    # Wait 5 minutes
    - 'sleep 300'
    # Verify VM is running
    - 'xe vm-list name-label="{vm_name}-restored" power-state=running'
    # Cleanup
    - 'xe vm-shutdown vm="{vm_name}-restored" force=true'
    - 'xe vm-uninstall vm="{vm_name}-restored" force=true'
```

### Off-Site Backups

**Rsync to remote site:**
```yaml
after:
  job:
    - 'rsync -avz --delete /mnt/backup/vm/ backup@remote.site:/backup/vm/'
```

**Cloud storage (S3):**
```yaml
after:
  job:
    - 'aws s3 sync /mnt/backup/vm/ s3://company-backups/vm/ --delete'
```

**Encrypted transfer:**
```yaml
after:
  job:
    - 'gpg --encrypt --recipient backup@company.com /mnt/backup/vm/*.xva'
    - 'rsync -avz /mnt/backup/vm/*.xva.gpg backup@remote:/encrypted/'
```

## Troubleshooting

### Common Issues

**1. Connection Refused**
```
Error: Could not connect to 192.168.1.100
```

**Solutions:**
- Verify network connectivity: `ping 192.168.1.100`
- Check firewall rules
- Verify credentials
- Ensure XAPI service is running on host

**2. Disk Space**
```
Error: No space left on device
```

**Solutions:**
- Check available space: `df -h /mnt/backup`
- Implement backup rotation
- Compress old backups
- Use VDI export instead of full VM for better deduplication

**3. VDI_IN_USE Errors**
```
ERROR - XenAPI error removing snapshot: ['VDI_IN_USE', ...]
```

**Normal behavior** - vmback retries automatically (3 attempts, 5s delay)

If persistent:
- Increase export timeout
- Check for stuck XenAPI tasks
- Verify no other operations using the VDI

**4. Orphaned Snapshots**
```
WARNING - ORPHANED SNAPSHOT: Manual cleanup may be required!
```

**Prevention:**
- vmback automatically retries
- Increase timeout for large VMs
- Check network stability

**Manual cleanup:**
```bash
# List all snapshots
xe snapshot-list

# Destroy orphaned snapshot
xe snapshot-uninstall uuid=<snapshot-uuid> force=true
```

**5. Progress Bar Errors**
```
ERROR - Unexpected error during download: bool() undefined when iterable == total == None
```

**Fixed in v2.2.3** - falls back to log-based progress

If still occurring:
- Update to latest version
- Check tqdm version: `pip show tqdm`

### Debug Mode

```bash
# Enable debug logging
python -m vmback -c config.yaml backup

# With debug level in config
logging:
  level: DEBUG

# Check what's happening
tail -f /var/log/vmback/vmback-*.log
```

### Performance Issues

**Slow backups:**

1. **Use HTTP export** (2.2x faster than xe CLI)
2. **Increase chunk size** for 10GbE networks
3. **Check network bandwidth:**
   ```bash
   iperf3 -c 192.168.1.100
   ```
4. **Monitor XCP-ng host resources:**
   ```bash
   xe host-cpu-info uuid=<host-uuid>
   xe host-param-list uuid=<host-uuid>
   ```

**Network saturation:**
```yaml
export:
  http:
    chunk_size: 4194304  # Reduce to 4MB
```

## Performance Tuning

### Network Optimization

**1GbE Network:**
```yaml
export:
  method: 'http'
  http:
    chunk_size: 8388608   # 8MB
```

**10GbE Network:**
```yaml
export:
  method: 'http'
  http:
    chunk_size: 16777216  # 16MB
```

**Slow network:**
```yaml
export:
  method: 'http'
  http:
    chunk_size: 4194304   # 4MB
    timeout: 7200         # 2 hours
```

### Storage Optimization

**NFS Storage:**
```yaml
# Use larger chunks
export:
  http:
    chunk_size: 16777216
```

**USB Storage:**
```yaml
# Handle sleep scenarios
resilience:
  log:
    on_error: 'warn'
  backup:
    on_error: 'warn'
```

**iSCSI Storage (10GbE):**
```yaml
# Optimize for speed
export:
  http:
    chunk_size: 33554432  # 32MB
```

### Parallel Backups

**Multiple pools in parallel:**
```bash
# Start multiple vmback instances
python -m vmback -c pool1.yaml backup &
python -m vmback -c pool2.yaml backup &
wait
```

**Systemd parallel execution:**
```bash
# Create multiple timer instances
systemctl start vmback@pool1.service &
systemctl start vmback@pool2.service &
```

### Resource Management

**Linux nice/ionice:**
```bash
# Lower priority
nice -n 19 ionice -c 3 python -m vmback -c config.yaml backup
```

**Systemd resource limits:**
```ini
[Service]
CPUQuota=50%
MemoryMax=2G
IOWeight=10
```

---

For additional support:
- [Configuration Manual](CONFIGURATION.md)
- [Technical Analysis](TECHNICAL_ANALYSIS.md)
- [GitHub Issues](https://github.com/yourusername/vmback/issues)
