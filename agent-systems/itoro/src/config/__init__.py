"""
Configuration package for Anarcho Capital's trading system
Built with love by Anarcho Capital 🚀
"""

# Import everything from the main config.py file
import importlib.util
from pathlib import Path

# Load the main config.py module
config_file = Path(__file__).parent.parent / "config.py"
spec = importlib.util.spec_from_file_location("config_module", config_file)
if spec and spec.loader:
    config_module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(config_module)
    
    # Copy all attributes to make them available when importing from src.config
    for name in dir(config_module):
        if not name.startswith('_'):
            globals()[name] = getattr(config_module, name)

# Also load defi_config.py
defi_config_file = Path(__file__).parent / "defi_config.py"
defi_spec = importlib.util.spec_from_file_location("defi_config_module", defi_config_file)
if defi_spec and defi_spec.loader:
    defi_config_module = importlib.util.module_from_spec(defi_spec)
    defi_spec.loader.exec_module(defi_config_module)
    
    # Copy all attributes from defi_config to make them available
    for name in dir(defi_config_module):
        if not name.startswith('_'):
            globals()[name] = getattr(defi_config_module, name)
