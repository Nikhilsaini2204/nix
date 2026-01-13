from datetime import datetime
from config import create_niks_folder, save_config, get_default_config
from core import detector


def run():
    """Run initialization command"""
    print("Initializing niks...")

    # Check if Spring Boot project
    print("Checking if this is a Spring Boot project...")
    is_springboot, version = detector.is_springboot_project()

    if not is_springboot:
        print("Error: This does not appear to be a Spring Boot project.")
        print("Make sure you're in a directory with pom.xml or build.gradle.")
        return False

    print(f"Detected Spring Boot {version}")

    # Count Java files
    print("Scanning project structure...")
    java_file_count = detector.count_java_files()

    # Create .niks folder
    try:
        create_niks_folder()
    except Exception as e:
        print(f"Error: {str(e)}")
        return False

    # Prepare config data
    config_data = get_default_config()
    config_data["springboot_version"] = version
    config_data["initialized_at"] = datetime.now().isoformat()
    config_data["total_files"] = java_file_count
    config_data["last_checked"] = datetime.now().isoformat()

    # Save config
    try:
        save_config(config_data)
    except Exception as e:
        print(f"Error: {str(e)}")
        return False

    # Success message
    print("Niks initialized successfully.")
    print(f"Project contains {java_file_count} Java files.")
    print("\nNext steps:")
    print("  Run 'niks analyze' to analyze your code")
    print("  Run 'niks status' to check project status")

    return True