"""Configuration handling and validation"""

import yaml
from typing import Dict, Any
from pathlib import Path


def load_user_config(config_path: Path) -> Dict[str, Any]:
    """Load user preferences from YAML config file"""
    with open(config_path, "r") as f:
        return yaml.safe_load(f)


def in_price_range(price: float, config: Dict[str, Any]) -> bool:
    """
    Check if price is within user-defined ranges.
    
    Args:
        price: The wine price
        config: User configuration dictionary
    
    Returns:
        True if price is within range, False otherwise
    """
    price_range = config.get("price_range", [None, None])
    if price_range[0] is not None and price < price_range[0]:
        return False
    if price_range[1] is not None and price > price_range[1]:
        return False

    return True
