"""
Configuration loader for VM Backup
Loads YAML configuration and credentials from separate files or .env
"""

import yaml
import logging
from pathlib import Path
from typing import Dict, Any, Optional
from dotenv import dotenv_values

logger = logging.getLogger(__name__)


class ConfigError(Exception):
    """Configuration error exception"""
    pass


class Config:
    """Configuration manager for vmback"""
    
    def __init__(self, config_path: str = 'config.yaml'):
        """
        Initialize configuration
        
        Args:
            config_path: Path to YAML config file
            
        Raises:
            ConfigError: If config file not found or invalid
        """
        self._config = self._load_config(config_path)
        self._load_credentials()
        self._validate_config()
    
    def _load_config(self, config_path: str) -> Dict[str, Any]:
        """Load YAML configuration file"""
        path = Path(config_path)
        
        if not path.exists():
            raise ConfigError(f"Config file not found: {config_path}")
        
        try:
            with open(path, 'r') as f:
                config = yaml.safe_load(f)
        except yaml.YAMLError as e:
            raise ConfigError(f"Invalid YAML in config file: {e}")
        
        if not config:
            raise ConfigError("Config file is empty")
        
        return config
    
    def _load_credentials(self):
        """
        Load credentials from .env file or credentials.yaml
        Maintains backward compatibility with existing .env approach
        """
        username = None
        password = None
        
        # First try .env file (backward compatibility)
        env_path = Path('.env')
        if env_path.exists():
            env = dotenv_values('.env')
            username = env.get('XEN_USERNAME')
            password = env.get('XEN_PASSWORD')
        
        # Then try credentials.yaml (new approach)
        creds_path = None
        if 'env' in self._config and 'credentials_file' in self._config['env']:
            creds_path = self._config['env']['credentials_file']
        else:
            # Look for credentials.yaml in same directory as config
            creds_path = 'credentials.yaml'
        
        creds_file = Path(creds_path)
        if creds_file.exists():
            # Check permissions (should be 600 for security)
            file_mode = creds_file.stat().st_mode & 0o777
            if file_mode not in [0o600, 0o400]:  # Allow read-only too
                import logging
                logging.warning(
                    f"Credentials file has potentially insecure permissions: {oct(file_mode)} "
                    f"(recommended: 600). Fix with: chmod 600 {creds_path}"
                )
            
            try:
                with open(creds_file, 'r') as f:
                    credentials = yaml.safe_load(f)
                
                if credentials and 'xen' in credentials:
                    username = credentials['xen'].get('username', username)
                    password = credentials['xen'].get('password', password)
            except yaml.YAMLError as e:
                raise ConfigError(f"Invalid YAML in credentials file: {e}")
        
        if not username or not password:
            raise ConfigError(
                "XEN credentials not found. "
                "Please provide either:\n"
                "  1. .env file with XEN_USERNAME and XEN_PASSWORD, or\n"
                "  2. credentials.yaml file with xen.username and xen.password"
            )
        
        # Store credentials in config
        self._config['auth'] = {
            'username': username,
            'password': password
        }
    
    def _validate_config(self):
        """Validate required configuration sections"""
        # Required top-level sections
        if 'pools' not in self._config:
            raise ConfigError("Missing required config section: pools")
        
        if 'env' not in self._config:
            raise ConfigError("Missing required config section: env")
        
        # Resilience configuration (optional, set defaults)
        if 'resilience' not in self._config:
            self._config['resilience'] = {}
        
        resilience = self._config['resilience']
        
        # Set default error handling policies
        if 'log' not in resilience:
            resilience['log'] = {}
        resilience['log'].setdefault('on_error', 'continue')
        
        if 'backup' not in resilience:
            resilience['backup'] = {}
        resilience['backup'].setdefault('on_error', 'fail')
        
        if 'hooks' not in resilience:
            resilience['hooks'] = {}
        resilience['hooks'].setdefault('on_error', 'warn')
        
        if 'network' not in resilience:
            resilience['network'] = {}
        resilience['network'].setdefault('max_retries', 3)
        resilience['network'].setdefault('retry_delay', 5)
        resilience['network'].setdefault('backoff_multiplier', 2.0)
        resilience['network'].setdefault('max_delay', 60)
        
        # Validate error handling values
        valid_on_error = ['continue', 'warn', 'fail']
        for component in ['log', 'backup', 'hooks']:
            on_error = resilience[component]['on_error']
            if on_error not in valid_on_error:
                raise ConfigError(
                    f"Invalid resilience.{component}.on_error: {on_error}. "
                    f"Must be one of: {valid_on_error}"
                )
        
        # Export configuration (new in v2.1.0)
        if 'export' not in self._config:
            # Backward compatibility: if no export section, use legacy xe
            if 'xe' not in self._config:
                raise ConfigError("Missing required config section: xe (or export for new format)")
            
            # Create export section from legacy xe config
            logger.info("Using legacy 'xe' configuration format (backward compatible)")
            self._config['export'] = {
                'method': 'xe',
                'xe': self._config['xe']
            }
        else:
            # New export format
            export_config = self._config['export']
            method = export_config.get('method', 'xe')
            
            if method == 'xe':
                # Need xe commands
                if 'xe' not in export_config and 'xe' not in self._config:
                    raise ConfigError("Export method 'xe' requires 'xe' command configuration")
                
                # Use xe config from export section or top-level
                if 'xe' not in export_config:
                    export_config['xe'] = self._config['xe']
                
                # Validate xe commands
                xe_config = export_config['xe']
                xe_required = ['pool-dump-database', 'vdi-export', 'vm-export']
                for field in xe_required:
                    if field not in xe_config:
                        raise ConfigError(f"Missing required xe command: {field}")
            
            elif method == 'http':
                # HTTP method configuration is optional (has defaults)
                if 'http' not in export_config:
                    export_config['http'] = {}
                
                # Set defaults for HTTP config
                http_config = export_config['http']
                http_config.setdefault('scheme', 'http')
                http_config.setdefault('verify_ssl', False)
                http_config.setdefault('timeout', 3600)
                http_config.setdefault('chunk_size', 8388608)
            
            else:
                raise ConfigError(f"Invalid export method: {method}. Must be 'xe' or 'http'")
        
        # Validate env section
        env_required = ['backup-path', 'pool-metadata-template', 
                       'vdi-template', 'vm-metadata-template', 'vm-template']
        for field in env_required:
            if field not in self._config['env']:
                raise ConfigError(f"Missing required env config: {field}")
        
        # Validate each pool
        for idx, pool in enumerate(self._config['pools']):
            if 'hosts' not in pool or not pool['hosts']:
                raise ConfigError(f"Pool {idx}: missing or empty 'hosts' list")
            if 'scope' not in pool:
                raise ConfigError(f"Pool {idx}: missing 'scope'")
            
            # Validate scope values
            valid_scopes = {'metadata', 'vm', 'vdi'}
            for scope_item in pool['scope']:
                if scope_item not in valid_scopes:
                    raise ConfigError(
                        f"Pool {idx}: invalid scope '{scope_item}'. "
                        f"Valid values: {', '.join(sorted(valid_scopes))}"
                    )
    
    def __getitem__(self, key):
        """Allow dict-like access: config['key']"""
        return self._config[key]
    
    def __contains__(self, key):
        """Allow 'key in config' checks"""
        return key in self._config
    
    def get(self, key, default=None):
        """Get config value with default"""
        return self._config.get(key, default)
    
    def add(self, key, value):
        """Add/update config value (for backward compatibility)"""
        self._config[key] = value


def load_config(config_path: str = 'config.yaml') -> Config:
    """
    Load and validate configuration
    
    Args:
        config_path: Path to YAML config file
        
    Returns:
        Config object
        
    Raises:
        ConfigError: If config file not found or invalid
    """
    return Config(config_path)
