# vmback

**Document Last Updated**: 2026-08-02

**Project Status**: Production

Backup XCP-ng Virtual Machines, Virtual Disk Images, and pool metadata to local storage. Designed both for enterprise environments that use Borg Backup for retention and a home lab with external USB or NAS storage.

## How It Works

```
┌──────────────┐     XenAPI HTTP       ┌─────────────────┐
│  XCP-ng Pool │ ◄──────────────────── │  vmback host    │
│              │                       │                 │
│  VMs / VDIs  │ ── export (stream) ─► │  /opt/vmback    │
│  metadata    │                       │  └─> backup dir │
└──────────────┘                       └─────────────────┘
                                               │
                                               ▼ borg2 archival
```

vmback connects to one or more XCP-ng pools over HTTP. It exports pool metadata, VM full-disk images (XVA), and VDI snapshots (VHD). The exporter modules route traffic through either the XenAPI HTTP API (default) or the legacy `xe` CLI tool. After export, shell hooks archive the files to Borg Backup repositories.

## Requirements

- Linux host with Python 3.8 or later
- XCP-ng pool accessible via HTTP API (ports 443 or 80)
- Local backup storage with sufficient space
- borg2 installed on the backup host (optional but recommended)

## Quick Start

1. Run the installer as root: `bash install.sh`
2. Create configuration: `cp /etc/vmback/config.yaml.example /etc/vmback/config.yaml`
3. Edit `/etc/vmback/config.yaml` with pool credentials and VM list
4. Create credentials file: `cp /etc/vmback/credentials.yaml.example /etc/vmback/credentials.yaml`
5. Secure the credentials file: `chmod 600 /etc/vmback/credentials.yaml`
6. Test a backup: `vmback -c /etc/vmback/config.yaml backup`

## Usage

```
vmback <mode> [options]

Modes:
  backup    Run backup for all configured pools
  vm        List VMs in the pool
  vdi       List VDI snapshots in the pool

Options:
  -c, --config PATH   Path to configuration YAML (default: config.yaml)
  -v, --verbose       Enable DEBUG logging
      --version       Show version and exit
```

Example commands:

```bash
# List VMs in the pool
vmback -c /etc/vmback/config.yaml vm

# Run a full backup with debug output
vmback -c /etc/vmback/config.yaml -v backup
```

## Configuration

Configuration lives in `/etc/vmback/` and consists of three file types.

### Main config (`config.yaml`)

Defines pools, VMs to back up, and template patterns for output filenames. Key sections:

- **pools** — XCP-ng pool members and backup scope (metadata, vm, vdi). Each entry contains `id`, `hosts`, `scope`, and an optional `credentials-file`.
- **env** — Global settings. Required fields: `backup-path` (local storage directory), `log-path`, and filename templates for metadata, VMs, and VDIs (`{pool_name}`, `{vm_name}`, `{device}` placeholders).
- **export** — Export method (`http` recommended) with scheme, SSL verification, timeout, and chunk size. Legacy `xe` CLI commands are also configurable.
- **resilience** — Error handling: `on_error` behavior per component (log, backup, hooks), and network retry policy with exponential backoff.
- **hooks** — Shell commands to run before or after each export phase (job, metadata, vm, vdi). Supports Python `.format()` placeholders (`{vm_name}`) and time placeholders (`{y}`, `{m}`, `{d}`).
- **vm** — List of VMs to back up with `vm-uuid` and human-readable `vm-name`. Leave empty to back up all VMs in the pool.
- **vdi** — Override list of specific VDIs to back up. Same format as vm entries.

### Include directive

Use `include: "/etc/vmback/other.yaml"` at the top of a config file to merge sections from another file. The included file replaces matching sections in the main config. Use this to share pool-level settings across day-of-week configs.

The project ships with example configs in `conf/examples/`: `mon` through `sun` for per-day scheduling, plus `supermicro.yaml` as a reusable pool template.

### Credentials (`credentials.yaml`)

YAML file with XCP-ng pool administrator credentials:

```yaml
xen:
  username: admin@example.com
  password: secret
```

Set permissions to `600`. vmback warns if the file grants wider access. Each pool entry may specify its own `credentials-file` to use different auth per pool.

## Repository Structure

```
conf/                          # Configuration files
├── regul8or.yaml              # Sample pool config (Home Lab)
├── supermicro.yaml            # Production pool template (Enterprise)
├── wd.yaml                    # Weekday backup config
├── we.yaml                    # Weekend backup config
└── examples/                  # Per-day schedule examples
    ├── mon.yaml .. sun.yaml
    ├── srv.yaml
    └── ...

docs/                          # Documentation
└── deprecated/                # Archived documents (not in scope)

install.sh                     # Root installer (/opt/vmback, /etc/vmback)

requirements.txt               # Python dependencies (pathlib, prettytable, PyYAML, XenAPI, requests, tqdm)

systemd/                       # Timer-based service units
├── vmback-wd.service          # Weekday backup unit
├── vmback-wd.timer            # Weekday 02:00 cron trigger
├── vmback-we.service          # Weekend backup unit
└── vmback-we.timer            # Weekend 02:00 cron trigger

vmback/                        # Application package
├── __main__.py                # CLI entry point (argparse, v2.3.0)
├── config.py                  # Config loader + YAML include + validator
├── backup.py                  # Backup orchestrator (pool loop, hooks)
├── backup_vm.py               # VM export: snapshot → export → cleanup
├── backup_vdi.py              # VDI export: tight snapshot loop → per-device export
├── list_vm.py                 # VM listing command
├── list_vdi.py                # VDI listing command
├── xapi.py                    # XenAPI session + pool_connect
├── utils.py                   # Template rendering, shell helpers, credential redaction
├── logging_setup.py           # TTY detection, session log rotation
├── resilient_logger.py        # File-error-tolerant logger wrapper
└── exporters/                 # Export backend implementations
    ├── __init__.py            # Re-exports + create_exporter()
    ├── base.py                # Abstract BaseExporter interface
    ├── http_exporter.py       # XenAPI HTTP API (recommended, v2.3.0 default)
    └── xe_exporter.py         # Legacy xe CLI fallback
```

## Attribution

This project was built using AI-assisted development.
Commits with AI contributions are marked appropriately.
