import json
import os
from config import get_nix_path


def save_data(filename, data):
    """Save data to .nix folder"""
    try:
        filepath = os.path.join(get_nix_path(), filename)
        with open(filepath, 'w') as f:
            json.dump(data, f, indent=2)
        return True
    except Exception as e:
        raise Exception(f"Failed to save {filename}: {str(e)}")


def load_data(filename):
    """Load data from .nix folder"""
    try:
        filepath = os.path.join(get_nix_path(), filename)
        if not os.path.exists(filepath):
            return None

        with open(filepath, 'r') as f:
            return json.load(f)
    except Exception:
        return None