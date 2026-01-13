from datetime import datetime
from config import load_config, save_config
from core import detector


def run():
    """Run status command"""
    config = load_config()

    if not config:
        print("Error: Could not load nix configuration.")
        print("Try reinitializing with a fresh setup.")
        return False

    # Display current status
    print(f"Project: {config['project_name']}")
    print(f"Spring Boot Version: {config['springboot_version']}")
    print(f"Initialized: {format_datetime(config['initialized_at'])}")
    print(f"Java files tracked: {config['total_files']}")

    # Check if file count changed
    current_count = detector.count_java_files()

    if current_count != config['total_files']:
        print(f"\nProject structure changed: Now {current_count} Java files (was {config['total_files']})")
        print("Run 'nix refresh' to update project index")
    else:
        print("\nProject structure unchanged.")

    # Update last checked time
    config['last_checked'] = datetime.now().isoformat()
    save_config(config)

    print("\nAvailable commands:")
    print("  nix analyze - Analyze your code")
    print("  nix refresh - Update project index")

    return True


def format_datetime(iso_string):
    """Format ISO datetime string to readable format"""
    try:
        dt = datetime.fromisoformat(iso_string)
        return dt.strftime("%Y-%m-%d %H:%M:%S")
    except:
        return iso_string