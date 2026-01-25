"""
Utility functions for VM Backup
"""

import subprocess
import logging
import re
from datetime import datetime
from typing import Dict, Any, Optional


logger = logging.getLogger(__name__)


def run_shell_command(cmd: str, log_cmd: str = None) -> int:
    """
    Run a shell command and log output
    
    Args:
        cmd: Command to run (actual command with real credentials)
        log_cmd: Command to log (with credentials redacted). If None, uses cmd.
        
    Returns:
        Return code (0 = success)
    """
    # Use redacted version for logging, or actual command if no redaction needed
    logged_command = log_cmd if log_cmd is not None else cmd
    
    logger.info(f"Executing: {logged_command}")
    
    try:
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            shell=True,
            universal_newlines=True
        )
        
        for line in process.stdout:
            line = line.rstrip()
            if line:
                logger.debug(f"  {line}")
        
        errcode = process.wait()
        
        if errcode == 0:
            logger.debug(f"Command completed successfully (exit code: {errcode})")
        else:
            logger.error(f"Command failed with exit code: {errcode}")
        
        return errcode
        
    except Exception as e:
        logger.error(f"Error executing command: {e}")
        return -1


def redact_credentials(cmd: str, username: str = None, password: str = None) -> str:
    """
    Redact username and password from command for safe logging
    
    Args:
        cmd: Command string containing credentials
        username: Username to redact (optional, will use pattern matching if not provided)
        password: Password to redact (optional, will use pattern matching if not provided)
        
    Returns:
        Command string with credentials replaced by [REDACTED]
    """
    redacted = cmd
    
    # Redact password (more important!)
    if password:
        # Replace the actual password
        redacted = redacted.replace(password, '[REDACTED]')
    else:
        # Pattern-based: -pw <password> or -password <password>
        import re
        redacted = re.sub(r'(-pw\s+|--password[=\s]+)\S+', r'\1[REDACTED]', redacted)
    
    # Redact username (less sensitive but still good practice)
    if username:
        # Replace the actual username
        redacted = redacted.replace(username, '[REDACTED]')
    else:
        # Pattern-based: -u <username> or -username <username>
        import re
        redacted = re.sub(r'(-u\s+|--username[=\s]+)\S+', r'\1[REDACTED]', redacted)
    
    return redacted


def str_format(template: str, **kwargs) -> str:
    """
    Format a string template with keyword arguments
    
    Args:
        template: String template with {placeholders}
        **kwargs: Values to substitute
        
    Returns:
        Formatted string
    """
    return template.format(**kwargs)


def get_ymd() -> Dict[str, int]:
    """
    Get current year, month, day
    
    Returns:
        Dictionary with 'y', 'm', 'd' keys
    """
    now = datetime.now()
    return {
        'y': now.year,
        'm': now.month,
        'd': now.day
    }


def check_conf_parameter(node: Dict[str, Any], param: str) -> bool:
    """
    Check if a configuration parameter exists
    
    Args:
        node: Configuration node to check
        param: Parameter name
        
    Returns:
        True if parameter exists, False otherwise
    """
    if node is None or param not in node:
        logger.error(f"Missing required config parameter: {param}")
        return False
    return True


def format_bytes(size: int) -> str:
    """
    Format bytes into human-readable string
    
    Args:
        size: Size in bytes
        
    Returns:
        Formatted string (e.g., "1.5 GB")
    """
    for unit in ['B', 'KB', 'MB', 'GB', 'TB']:
        if size < 1024.0:
            return f"{size:.1f} {unit}"
        size /= 1024.0
    return f"{size:.1f} PB"


def format_duration(seconds: float) -> str:
    """
    Format duration in seconds to human-readable string
    
    Args:
        seconds: Duration in seconds
        
    Returns:
        Formatted string (e.g., "1h 23m 45s")
    """
    hours, remainder = divmod(int(seconds), 3600)
    minutes, secs = divmod(remainder, 60)
    
    parts = []
    if hours > 0:
        parts.append(f"{hours}h")
    if minutes > 0:
        parts.append(f"{minutes}m")
    parts.append(f"{secs}s")
    
    return " ".join(parts)


def run_hook_commands(
    hook_type: str,
    stage: str,
    conf: Dict[str, Any],
    context: Optional[Dict[str, Any]] = None
):
    """
    Unified hook runner for all before/after hooks
    
    Args:
        hook_type: 'before' or 'after'
        stage: 'job', 'metadata', 'vm', or 'vdi'
        conf: Full configuration
        context: Optional context dict with variables for template substitution
                (e.g., vm_name, vm_uuid, pool_name, pool_uuid, device)
    """
    # Check if hooks are configured
    if hook_type not in conf or stage not in conf[hook_type] or not conf[hook_type][stage]:
        return
    
    logger.info(f"Running {hook_type}-{stage} commands")
    
    # Get hook error policy
    hook_on_error = conf.get('resilience', {}).get('hooks', {}).get('on_error', 'warn')
    
    # Get current date for templates
    now = get_ymd()
    
    # Build template variables
    template_vars = {
        'y': now['y'],
        'm': now['m'],
        'd': now['d']
    }
    
    # Add context variables if provided
    if context:
        # Add entity-specific variables
        if 'vm_name' in context:
            template_vars['vm_name'] = context['vm_name']
            template_vars['vm_name_escaped'] = re.escape(context['vm_name'])
        if 'vm_uuid' in context:
            template_vars['vm_uuid'] = context['vm_uuid']
        if 'pool_name' in context:
            template_vars['pool_name'] = context['pool_name']
            template_vars['pool_name_escaped'] = re.escape(context['pool_name'])
        if 'pool_uuid' in context:
            template_vars['pool_uuid'] = context['pool_uuid']
        if 'device' in context:
            template_vars['device'] = context['device']
    
    # Execute each hook command
    for cmd_template in conf[hook_type][stage]:
        try:
            cmd = str_format(cmd_template, **template_vars)
            exit_code = run_shell_command(cmd)
            
            if exit_code != 0:
                error_msg = f"{hook_type.capitalize()}-{stage} hook failed with exit code {exit_code}: {cmd}"
                
                if hook_on_error == 'fail':
                    logger.error(error_msg)
                    logger.error("Hook error policy is 'fail', stopping")
                    raise RuntimeError(error_msg)
                elif hook_on_error == 'warn':
                    logger.warning(error_msg)
                    logger.warning("Hook error policy is 'warn', continuing")
                
        except Exception as e:
            error_msg = f"Error running {hook_type}-{stage} hook: {e}"
            
            if hook_on_error == 'fail':
                logger.error(error_msg)
                raise
            elif hook_on_error == 'warn':
                logger.warning(error_msg)
                logger.warning("Hook error policy is 'warn', continuing")
            else:  # 'continue'
                logger.debug(error_msg)
