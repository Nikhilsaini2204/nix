from datetime import datetime
from config import create_nix_folder, save_config, get_default_config
from core import detector


def run():
    """Run initialization command"""
    print("Initializing nix...")

    # Check API key first
    from llm.client import get_api_key
    if not get_api_key():
        print("Error: API key not configured.")
        print("Run: nix config <your_groq_api_key>")
        print("Get your key at: https://console.groq.com/keys")
        return False

    # Check if Spring Boot project
    print("Checking if this is a Spring Boot project...")
    try:
        is_springboot, version = detector.is_springboot_project()
    except Exception as e:
        print(f"Error: {str(e)}")
        return False

    if not is_springboot:
        # Check if there's a build file at all
        build_file, _ = detector.find_build_file()
        if build_file:
            print("Error: Could not detect Spring Boot in your build file.")
            print("Make sure your pom.xml or build.gradle has Spring Boot dependencies.")
        else:
            print("Error: No pom.xml or build.gradle found.")
            print("Make sure you're in a Spring Boot project directory.")
        return False

    print(f"Detected Spring Boot {version}")

    # Count Java files
    print("Scanning project structure...")
    java_file_count = detector.count_java_files()

    # Create .nix folder
    try:
        create_nix_folder()
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
    print("Nix initialized successfully.")
    print(f"Project contains {java_file_count} Java files.")
    print("\nNext steps:")
    print("  Run 'nix analyze' to analyze your code")
    print("  Run 'nix status' to check project status")

    return True