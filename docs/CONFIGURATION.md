# Configuration Manual

Complete reference for vmback configuration options.

## Table of Contents

- [Configuration File Structure](#configuration-file-structure)
- [Credentials](#credentials)
- [Environment Settings](#environment-settings)
- [Pool Configuration](#pool-configuration)
- [VM Selection](#vm-selection)
- [VDI Configuration](#vdi-configuration)
- [Export Methods](#export-methods)
- [Resilience Configuration](#resilience-configuration)
- [Hooks System](#hooks-system)
- [Logging Configuration](#logging-configuration)
- [Complete Examples](#complete-examples)

## Configuration File Structure

vmback uses YAML configuration files. The basic structure:

```yaml
# Authentication credentials
credentials:
  username: root
  password: password

# Environment paths
env:
  backup-path: /path/to/backups
  log-path: /path/to/logs

# Export method configuration
export:
  method: http
  http: { ... }

# Resilience policies
resilience:
  log: { ... }
  backup: { ... }
  hooks: { ... }

# Pools to backup
pools:
  - id: PoolName
    hosts: [ ... ]
    scope: [ ... ]

# VM backup configuration
vms:
  - vm-uuid: ...

# VDI backup configuration (optional)
vdi:
  - vm-uuid: ...

# Hook commands
before:
  job: [ ... ]
  metadata: [ ... ]
  vm: [ ... ]
  vdi: [ ... ]

after:
  job: [ ... ]
  metadata: [ ... ]
  vm: [ ... ]
  vdi: [ ... ]

# Logging configuration
logging:
  level: INFO
```

## Credentials

### Basic Authentication

```yaml
credentials:
  username: root
  password: your-password-here
```

### Using Environment Variables

Create a `.env` file:

```env
XAPI_USERNAME=root
XAPI_PASSWORD=your-password-here
```

Reference in config:

```yaml
credentials:
  username: ${XAPI_USERNAME}
  password: ${XAPI_PASSWORD}
```

### Using Separate Credentials File

Create `credentials.yaml`:

```yaml
username: root
password: your-password-here
```

Reference in main config:

```yaml
credentials-file: credentials.yaml
```

**Security Note:** Never commit credentials files to version control. Add them to `.gitignore`.

## Environment Settings

```yaml
env:
  backup-path: /backup/vm      # Where to store backups
  log-path: /var/log/vmback    # Where to store logs
```

### Path Requirements

- **backup-path**: Must be writable, sufficient space for VM/VDI exports
- **log-path**: Must be writable for log files

### Platform-Specific Paths

**Linux:**
```yaml
env:
  backup-path: /mnt/backup/vm
  log-path: /var/log/vmback
```

**Windows:**
```yaml
env:
  backup-path: 'X:\backup\vm'
  log-path: 'X:\backup\log'
```

## Pool Configuration

### Basic Pool

```yaml
pools:
  - id: Production              # Unique identifier
    hosts: [ 192.168.1.100 ]    # Pool master IP(s)
    scope: [ 'metadata', 'vm' ] # What to backup
```

### Scope Options

- `metadata`: Pool metadata (pool configuration, network settings)
- `vm`: Full VM exports
- `vdi`: Individual VDI exports

**Common combinations:**

```yaml
# Full backup (most common)
scope: [ 'metadata', 'vm' ]

# VDI-only backup (for deduplication)
scope: [ 'metadata', 'vdi' ]

# Everything
scope: [ 'metadata', 'vm', 'vdi' ]

# Metadata only
scope: [ 'metadata' ]
```

### Multiple Pools

```yaml
pools:
  - id: Production
    hosts: [ 192.168.1.100 ]
    scope: [ 'metadata', 'vm' ]
  
  - id: Development
    hosts: [ 192.168.2.100 ]
    scope: [ 'metadata', 'vm' ]
  
  - id: Offsite
    hosts: [ 10.10.1.100 ]
    scope: [ 'metadata', 'vm' ]
```

### Pool-Specific Credentials

```yaml
pools:
  - id: Production
    hosts: [ 192.168.1.100 ]
    scope: [ 'metadata', 'vm' ]
    username: backup-user        # Override default
    password: different-password # Override default
```

## VM Selection

### Backup All VMs

```yaml
vms:
  - vm-uuid: 'all'
```

### Backup Specific VMs

```yaml
vms:
  - vm-uuid: '3b2b64fb-b3ab-613e-a8a0-e89450c27e05'
    vm-name: 'Web Server'       # Optional, for logging
  
  - vm-uuid: 'ae310646-a4d5-6f16-789f-b9768836f349'
    vm-name: 'Database Server'
```

### Include/Exclude Patterns

```yaml
vms:
  - vm-uuid: 'all'
    include:
      - '^Production.*'         # Regex: VMs starting with "Production"
      - '.*Server$'             # Regex: VMs ending with "Server"
    exclude:
      - '.*Template.*'          # Regex: Skip templates
      - '^Test.*'               # Regex: Skip test VMs
```

### Postpone Running VMs

```yaml
vms:
  - vm-uuid: 'all'
    postpone: true              # Skip running VMs
```

**Use case:** Backup only powered-off VMs to ensure consistency.

## VDI Configuration

### Backup All VDI for a VM

```yaml
vdi:
  - vm-uuid: '3b2b64fb-b3ab-613e-a8a0-e89450c27e05'
    vm-name: 'Database Server'
    # Omit 'device' to backup all disks
```

### Backup Specific Devices

```yaml
vdi:
  - vm-uuid: '3b2b64fb-b3ab-613e-a8a0-e89450c27e05'
    vm-name: 'Database Server'
    device: [ 'xvda', 'xvdb' ]  # Only these devices
```

### Multiple VMs

```yaml
vdi:
  - vm-uuid: '3b2b64fb-b3ab-613e-a8a0-e89450c27e05'
    vm-name: 'Database Server'
    device: [ 'xvda' ]
  
  - vm-uuid: 'ae310646-a4d5-6f16-789f-b9768836f349'
    vm-name: 'Web Server'
    # All disks for this VM
```

**Note:** VDI backups are not atomic across multiple disks. For consistency, stop the VM or use VM export instead.

## Export Methods

### HTTP Export (Recommended)

```yaml
export:
  method: 'http'
  http:
    scheme: 'http'              # or 'https'
    verify_ssl: false           # true for valid certificates
    timeout: 3600               # seconds (1 hour)
    chunk_size: 8388608         # bytes (8MB)
```

**Performance tuning:**

```yaml
# For 1GbE networks
export:
  method: 'http'
  http:
    chunk_size: 8388608         # 8MB

# For 10GbE networks
export:
  method: 'http'
  http:
    chunk_size: 16777216        # 16MB
```

### xe CLI Export (Legacy)

```yaml
export:
  method: 'xe'
```

**Requirements:**
- xe CLI must be in system PATH
- Available via XenCenter download (not XCP-ng Center)

## Resilience Configuration

### Error Handling Policies

```yaml
resilience:
  log:
    on_error: 'warn'            # continue | warn | fail
  backup:
    on_error: 'warn'            # continue | warn | fail
  hooks:
    on_error: 'continue'        # continue | warn | fail
```

**Policy meanings:**

- `continue`: Log error at DEBUG level, continue silently
- `warn`: Log error at WARNING level, continue with warning
- `fail`: Log error at ERROR level, stop immediately

### Common Scenarios

**Production - Maximum reliability:**
```yaml
resilience:
  log:
    on_error: 'warn'            # Log failures, don't stop
  backup:
    on_error: 'fail'            # Stop on first backup failure
  hooks:
    on_error: 'warn'            # Warn on hook failures
```

**Best effort - Try everything:**
```yaml
resilience:
  log:
    on_error: 'warn'
  backup:
    on_error: 'warn'            # Try all VMs even if some fail
  hooks:
    on_error: 'continue'        # Ignore hook failures
```

**USB disk scenario:**
```yaml
resilience:
  log:
    on_error: 'warn'            # Disk might sleep
  backup:
    on_error: 'warn'            # Try all VMs
  hooks:
    on_error: 'continue'        # xcopy might fail
```

## Hooks System

### Hook Types

- `job`: Once per backup run
- `metadata`: Per pool metadata export
- `vm`: Per VM backup
- `vdi`: Per VDI/device backup

### Hook Timing

- `before`: Run before operation
- `after`: Run after successful operation

### Available Variables

**Job hooks:**
```yaml
before:
  job:
    - 'echo "Backup started {y}-{m}-{d}"'
```
Variables: `{y}`, `{m}`, `{d}`

**Metadata hooks:**
```yaml
before:
  metadata:
    - 'echo "Exporting {pool_name} metadata"'
```
Variables: `{pool_name}`, `{pool_uuid}`, `{y}`, `{m}`, `{d}`

**VM hooks:**
```yaml
before:
  vm:
    - 'echo "Backing up {vm_name}"'
```
Variables: `{vm_name}`, `{vm_uuid}`, `{y}`, `{m}`, `{d}`

**VDI hooks:**
```yaml
before:
  vdi:
    - 'echo "Processing {vm_name} device {device}"'
```
Variables: `{vm_name}`, `{vm_uuid}`, `{device}`, `{y}`, `{m}`, `{d}`

### Practical Examples

**Backup rotation (Windows):**
```yaml
after:
  job:
    # Copy metadata to backup folder
    - 'xcopy /y *.xml backup\'
    # Delete files older than 30 days
    - 'forfiles /p backup /m *.* /d -30 /c "cmd /c del @path"'
```

**Backup rotation (Linux):**
```yaml
after:
  job:
    - 'cp *.xml backup/'
    - 'find backup -type f -mtime +30 -delete'
```

**Notifications:**
```yaml
after:
  vm:
    - 'curl -X POST https://api.example.com/notify -d "VM {vm_name} backed up"'
```

**Pre-backup snapshots:**
```yaml
before:
  vm:
    - 'xe vm-snapshot uuid={vm_uuid} new-name-label="pre-backup-{y}{m}{d}"'
```

### Escaped Characters

Use `{vm_name_escaped}` for shell-safe names:

```yaml
after:
  vm:
    - 'echo {vm_name_escaped} > "status/{vm_name_escaped}.txt"'
```

## Logging Configuration

```yaml
logging:
  level: INFO                   # DEBUG | INFO | WARNING | ERROR
```

### Log Levels

- `DEBUG`: Verbose output, all operations
- `INFO`: Standard output, key operations (default)
- `WARNING`: Warnings and errors only
- `ERROR`: Errors only

### Log Files

Logs are automatically written to:
- `{log-path}/vmback-YYYYMMDD-HHMMSS.log` (per run)

### Interactive vs Service Mode

**Interactive (TTY detected):**
- Logs to console AND file
- Progress bars displayed
- Simplified format

**Service mode (no TTY):**
- Logs to file (configured level)
- Logs to stdout/journal (WARNING+)
- Full format with timestamps

## Complete Examples

### Home Lab Configuration

```yaml
credentials:
  username: root
  password: homelab-password

env:
  backup-path: 'X:\vm'
  log-path: 'X:\log'

export:
  method: 'http'
  http:
    scheme: 'http'
    verify_ssl: false
    timeout: 3600
    chunk_size: 8388608

resilience:
  log:
    on_error: 'warn'
  backup:
    on_error: 'warn'
  hooks:
    on_error: 'continue'

pools:
  - id: Home
    hosts: [ 192.168.1.49 ]
    scope: [ 'metadata', 'vm' ]

vms:
  - vm-uuid: 'all'
    exclude:
      - '.*Template.*'
    postpone: false

before:
  job:
    - 'echo "Starting backup at %date%"'

after:
  job:
    - 'xcopy /y *.xml backup\'
    - 'forfiles /p backup /m *.* /d -30 /c "cmd /c del @path"'

logging:
  level: INFO
```

### Enterprise Production Configuration

```yaml
credentials-file: /etc/vmback/credentials.yaml

env:
  backup-path: /backup/vm
  log-path: /var/log/vmback

export:
  method: 'http'
  http:
    scheme: 'https'
    verify_ssl: true
    timeout: 7200
    chunk_size: 16777216        # 16MB for 10GbE

resilience:
  log:
    on_error: 'warn'
  backup:
    on_error: 'fail'            # Stop on failure in production
  hooks:
    on_error: 'warn'

pools:
  - id: Production
    hosts: [ 10.10.1.100 ]
    scope: [ 'metadata', 'vdi' ] # VDI for deduplication

vdi:
  - vm-uuid: '3b2b64fb-b3ab-613e-a8a0-e89450c27e05'
    vm-name: 'Database Primary'
  - vm-uuid: 'ae310646-a4d5-6f16-789f-b9768836f349'
    vm-name: 'Web Frontend'

before:
  job:
    - 'logger -t vmback "Starting backup run"'
  vdi:
    - 'logger -t vmback "Backing up {vm_name} device {device}"'

after:
  job:
    - 'rsync -av *.xml /backup/archive/'
    - 'find /backup/vm -type f -mtime +7 -delete'
    - 'logger -t vmback "Backup completed"'

logging:
  level: INFO
```

### VDI-Only with Multiple Pools

```yaml
credentials:
  username: backup-user
  password: secure-password

env:
  backup-path: /mnt/iscsi/backup
  log-path: /var/log/vmback

export:
  method: 'http'
  http:
    chunk_size: 16777216

pools:
  - id: Prod-Pool-1
    hosts: [ 10.10.1.100 ]
    scope: [ 'metadata', 'vdi' ]
  
  - id: Prod-Pool-2
    hosts: [ 10.10.2.100 ]
    scope: [ 'metadata', 'vdi' ]

vdi:
  - vm-uuid: '3b2b64fb-b3ab-613e-a8a0-e89450c27e05'
    vm-name: 'DB-Prod-1'
    device: [ 'xvda' ]          # Data disk only
  
  - vm-uuid: 'ae310646-a4d5-6f16-789f-b9768836f349'
    vm-name: 'DB-Prod-2'
    device: [ 'xvda' ]

after:
  vdi:
    # Deduplicate with borg backup
    - 'borg create /mnt/borg::vmback-{y}{m}{d} {vm_name}*.vhd'

logging:
  level: DEBUG                  # Verbose for troubleshooting
```

## Configuration Validation

vmback validates configuration on startup:

- Required fields present
- Valid scope values
- Reachable paths
- Proper YAML syntax

**Common validation errors:**

```
Configuration error: Pool 0: invalid scope 'vdi''. Valid values: metadata, vdi, vm
```
Fix: Check for typos in scope list

```
Configuration error: Pool 0: missing 'scope'
```
Fix: Add scope to pool configuration

## Environment Variables

All configuration values can reference environment variables:

```yaml
credentials:
  username: ${BACKUP_USER}
  password: ${BACKUP_PASSWORD}

env:
  backup-path: ${BACKUP_ROOT}/vm
  log-path: ${LOG_ROOT}
```

Set in `.env` file:
```env
BACKUP_USER=root
BACKUP_PASSWORD=secret
BACKUP_ROOT=/mnt/backup
LOG_ROOT=/var/log/vmback
```

## Best Practices

1. **Store credentials separately** - Use credentials-file or .env
2. **Use HTTP export** - 2.2x faster than xe CLI
3. **Set appropriate chunk sizes** - 8MB for 1GbE, 16MB for 10GbE
4. **Configure resilience** - Match policies to your environment
5. **Use hooks for rotation** - Automate old backup cleanup
6. **Test recovery** - Regularly verify backups can be restored
7. **Monitor logs** - Check for warnings and errors
8. **Version control configs** - Track configuration changes (without credentials)

## Troubleshooting

### "Configuration error: Pool 0: invalid scope"
Check scope syntax - must be valid YAML list with proper quotes

### "Could not connect to host"
Verify network connectivity, credentials, and host address

### "VDI_IN_USE errors"
Normal during snapshot cleanup - vmback retries automatically

### "ORPHANED SNAPSHOT warnings"
Check XenAPI session timeout, may need to increase export timeout

### Hooks not running
Check resilience.hooks.on_error setting and hook syntax

---

For additional help, see:
- [Operations Manual](OPERATIONS.md)
- [Technical Analysis](TECHNICAL_ANALYSIS.md)
- [GitHub Issues](https://github.com/yourusername/vmback/issues)
