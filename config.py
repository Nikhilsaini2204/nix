import os
import json

# Constants
NIX_FOLDER = ".nix"
CONFIG_FILE = "config.json"
GITIGNORE_FILE = ".gitignore"


def get_project_root():
    """Get current project directory"""
    return os.getcwd()


def get_nix_path():
    """Get full path to .nix folder"""
    return os.path.join(get_project_root(), NIX_FOLDER)


def get_config_path():
    """Get full path to config.json"""
    return os.path.join(get_nix_path(), CONFIG_FILE)


def nix_exists():
    """Check if .nix folder exists"""
    return os.path.exists(get_nix_path())


def create_nix_folder():
    """Create .nix directory and .gitignore"""
    try:
        nix_path = get_nix_path()
        os.makedirs(nix_path, exist_ok=True)

        # Create .gitignore to ignore all contents
        gitignore_path = os.path.join(nix_path, GITIGNORE_FILE)
        with open(gitignore_path, 'w') as f:
            f.write("*\n")

        return True
    except Exception as e:
        raise Exception(f"Failed to create .nix folder: {str(e)}")


def load_config():
    """Load config.json and return as dictionary"""
    try:
        config_path = get_config_path()
        if not os.path.exists(config_path):
            return None

        with open(config_path, 'r') as f:
            return json.load(f)
    except json.JSONDecodeError:
        return None
    except Exception:
        return None


def save_config(data):
    """Save dictionary to config.json"""
    try:
        config_path = get_config_path()
        with open(config_path, 'w') as f:
            json.dump(data, f, indent=2)
        return True
    except Exception as e:
        raise Exception(f"Failed to save config: {str(e)}")


def get_default_config():
    """Return default config structure"""
    return {
        "project_name": os.path.basename(get_project_root()),
        "springboot_version": "",
        "initialized_at": "",
        "total_files": 0,
        "last_checked": ""
    }