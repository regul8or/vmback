# vmback - XCP-ng VM Backup Utility

A robust, production-ready backup solution for XCP-ng virtual machines and virtual disk images.

[![Python 3.7+](https://img.shields.io/badge/python-3.7+-blue.svg)](https://www.python.org/downloads/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## Features

- **Multiple Export Methods**
  - **HTTP Export** (recommended): Direct XenAPI calls - 2.2x faster than xe CLI
  - **xe CLI Export** (legacy): Traditional command-line interface
  
- **Flexible Backup Modes**
  - Full VM backups (`.xva` files)
  - Individual VDI backups (`.vhd` files)
  - Pool metadata exports
  - VM metadata exports
  
- **Production-Ready Resilience**
  - Configurable error handling policies (continue/warn/fail)
  - Automatic retry with exponential backoff
  - USB disk sleep detection and handling
  - Graceful interrupt handling (Ctrl+C)
  - Comprehensive snapshot cleanup (prevents orphans)
  
- **Advanced Features**
  - Real-time progress tracking with tqdm
  - Before/after hook system for custom workflows
  - VM filtering (include/exclude patterns)
  - Postpone policies for running VMs
  - Structured logging (interactive/service modes)
  - Multi-pool support

## Performance

HTTP export method delivers significant performance improvements:

| Export Method | Average Speed | vs xe CLI |
|---------------|---------------|-----------|
| xe CLI        | ~23.5 MB/s   | baseline  |
| HTTP          | ~52.5 MB/s   | **2.2x faster** |

*Tested on 1GbE network with various VM sizes (18-42 GB)*

## Quick Start

### Installation

1. **Install Python dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

2. **Install XenAPI (choose one):**
   
   **Option A: From PyPI (recommended)**
   ```bash
   pip install XenAPI
   ```
   
   **Option B: From XenServer SDK**
   - Download from [xenserver.com/downloads](https://www.xenserver.com/downloads)
   - Install the Python bindings from the SDK

3. **For xe CLI support (optional):**
   - Download XenCenter from [xenserver.com/downloads](https://www.xenserver.com/downloads)
   - xe CLI is included with XenCenter (not XCP-ng Center)
   - Add xe to your system PATH

### Basic Usage

1. **Create configuration file:**
   ```bash
   cp examples/home-lab.yaml my-config.yaml
   # Edit my-config.yaml with your settings
   ```

2. **List available VMs:**
   ```bash
   python -m vmback -c my-config.yaml vm
   ```

3. **Run backup:**
   ```bash
   python -m vmback -c my-config.yaml backup
   ```

## Configuration

### Minimal Configuration

```yaml
# Credentials
credentials:
  username: root
  password: your-password

# Environment
env:
  backup-path: /backup/vm
  log-path: /var/log/vmback

# Pools to backup
pools:
  - id: Production
    hosts: [ 192.168.1.100 ]
    scope: [ 'metadata', 'vm' ]

# VMs to backup (optional - defaults to all VMs)
vms:
  - vm-uuid: 'all'  # Backup all VMs in pool
```

### HTTP Export (Recommended)

```yaml
export:
  method: 'http'
  http:
    scheme: 'http'        # or 'https' for production
    verify_ssl: false     # set true with valid certificates
    timeout: 3600         # 1 hour timeout
    chunk_size: 8388608   # 8MB chunks (16MB for 10GbE)
```

### VDI Backup

```yaml
pools:
  - id: Production
    hosts: [ 192.168.1.100 ]
    scope: [ 'metadata', 'vdi' ]

vdi:
  - vm-uuid: '3b2b64fb-b3ab-613e-a8a0-e89450c27e05'
    vm-name: 'Database Server'
    # Optional: specify devices, or backup all disks
    device: [ 'xvda', 'xvdb' ]
```

### Resilience Configuration

```yaml
resilience:
  log:
    on_error: 'warn'      # Log to console if file write fails
  backup:
    on_error: 'warn'      # Try all VMs even if some fail
  hooks:
    on_error: 'continue'  # Don't stop on hook failures
```

### Hooks

Run custom commands before/after operations:

```yaml
before:
  job:
    - 'echo "Backup started at $(date)"'
  vm:
    - 'echo "Backing up {vm_name}"'
  vdi:
    - 'echo "Processing {vm_name} device {device}"'

after:
  job:
    - 'xcopy /y *.xml backup\'
    - 'forfiles /p backup /m *.* /d -30 /c "cmd /c del @path"'
```

**Available variables:**
- Job hooks: `{y}`, `{m}`, `{d}`
- Metadata hooks: `{pool_name}`, `{pool_uuid}`, `{y}`, `{m}`, `{d}`
- VM hooks: `{vm_name}`, `{vm_uuid}`, `{y}`, `{m}`, `{d}`
- VDI hooks: `{vm_name}`, `{vm_uuid}`, `{device}`, `{y}`, `{m}`, `{d}`

## Documentation

- [Configuration Manual](docs/CONFIGURATION.md) - Complete configuration reference
- [Operations Manual](docs/OPERATIONS.md) - Deployment and usage guide
- [Migration Guide](docs/MIGRATION_GUIDE.md) - Upgrading from xe CLI to HTTP
- [Technical Analysis](docs/TECHNICAL_ANALYSIS.md) - Architecture and design decisions

## Deployment

### Systemd Service (Linux)

```bash
# Install service file
sudo cp vmback/vmback@.service /etc/systemd/system/
sudo cp vmback/vmback@.timer /etc/systemd/system/

# Enable and start timer
sudo systemctl enable vmback@daily.timer
sudo systemctl start vmback@daily.timer
```

### Task Scheduler (Windows)

```powershell
# Create scheduled task
$action = New-ScheduledTaskAction -Execute "python" -Argument "-m vmback -c C:\backup\config.yaml backup"
$trigger = New-ScheduledTaskTrigger -Daily -At "02:00AM"
Register-ScheduledTask -TaskName "VMBackup" -Action $action -Trigger $trigger
```

## Requirements

- Python 3.7+
- XenAPI Python bindings
- XCP-ng 8.2+ or XenServer 8.0+
- Network access to XCP-ng host

### Python Dependencies

```
PyYAML>=5.1
python-dotenv>=0.19.0
XenAPI>=1.2
requests>=2.25.0
urllib3>=1.26.0
tqdm>=4.60.0  # optional, for progress bars
```

## Attributions

### Original Inspiration

This project was inspired by and builds upon [NAUbackup/VmBackup](https://github.com/NAUbackup/VmBackup), a Python-based XenServer backup solution. The original project provided the foundation for VM backup workflows and xe CLI integration.

### AI-Assisted Development

This project was developed with significant assistance from Claude (Anthropic), an AI assistant, which helped with:
- Architecture design and code refactoring
- HTTP export implementation
- Error handling and resilience patterns
- Documentation and testing strategies
- Performance optimization

The human developer (regul8or) provided:
- Domain expertise in XCP-ng/XenServer environments
- Production requirements and use cases
- Testing and validation across home lab and enterprise deployments
- Project vision and design decisions

### XenAPI and Tools

- XenAPI: Citrix Systems, Inc.
- XenServer/XCP-ng: Citrix and the XCP-ng Project
- xe CLI: Available via XenCenter (not XCP-ng Center)

## License

MIT License - see [LICENSE](LICENSE) file for details.

## Contributing

Contributions are welcome! Please:

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## Support

- **Issues**: [GitHub Issues](https://github.com/yourusername/vmback/issues)
- **Discussions**: [GitHub Discussions](https://github.com/yourusername/vmback/discussions)

## Changelog

See [CHANGELOG.md](docs/CHANGELOG.md) for version history and release notes.

## Project Status

**Current Version:** 2.2.3

- ✅ Production-ready
- ✅ Actively maintained
- ✅ Tested in home lab and enterprise environments
- ✅ Comprehensive documentation

---

**Note:** Replace `yourusername` with your actual GitHub username before publishing.
