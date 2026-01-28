from datetime import datetime
from config import create_nix_folder, save_config, get_default_config
from core import detector


def run(verbose=False, show_banner=True):
    """Run initialization command with visual feedback.

    Args:
        verbose: If True, show detailed output (default: False)
        show_banner: If True, show the nix banner during initialization (default: True)
    """
    from utils.output import set_quiet_mode, muted, print_indexing_banner, Spinner

    # Check API key first
    from llm.client import get_api_key
    if not get_api_key():
        print("Error: API key not configured.")
        print("Run: nix config <your_groq_api_key>")
        print("Get your key at: https://console.groq.com/keys")
        return False

    # Check if Spring Boot project
    try:
        is_springboot, version = detector.is_springboot_project()
    except Exception as e:
        print(f"Error: {str(e)}")
        return False

    if not is_springboot:
        build_file, _ = detector.find_build_file()
        if build_file:
            print("Error: Could not detect Spring Boot in your build file.")
            print("Make sure your pom.xml or build.gradle has Spring Boot dependencies.")
        else:
            print("Error: No pom.xml or build.gradle found.")
            print("Make sure you're in a Spring Boot project directory.")
        return False

    # Count Java files
    java_file_count = detector.count_java_files()

    # Show banner and indexing message for Spring Boot projects
    if show_banner:
        print_indexing_banner()

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

    # Start spinner for indexing
    spinner = Spinner(f"Indexing {java_file_count} Java files...")
    spinner.start()

    # Build code index silently
    from indexer.index_builder import IndexBuilder
    from indexer.index_storage import IndexStorage

    # Suppress all output during indexing
    set_quiet_mode(True)

    storage = IndexStorage()
    is_first_init = storage.load_index_data() is None

    try:
        builder = IndexBuilder()
        builder.build_index(force=is_first_init)
    except Exception:
        pass  # Continue even if index fails

    # Update spinner message for context building
    spinner.update_message("Building codebase context...")

    # Build codebase context silently
    try:
        from indexer.context_builder import ContextBuilder
        from tools.endpoint_analyzer import analyze_endpoints
        from tools.entity_analyzer import analyze_entities
        from tools.config_analyzer import analyze_configuration
        from tools.dependency_analyzer import analyze_dependencies

        index = builder.get_index()

        endpoints_data = []
        entities_data = []
        cfg_data = None
        deps_data = None

        try:
            spinner.update_message("Analyzing endpoints...")
            ep_result = analyze_endpoints()
            if not ep_result.get("error"):
                endpoints_data = ep_result.get("endpoints", [])

            spinner.update_message("Analyzing entities...")
            ent_result = analyze_entities()
            if not ent_result.get("error"):
                entities_data = ent_result.get("entities", [])

            spinner.update_message("Analyzing configuration...")
            cfg_data = analyze_configuration()
            deps_data = analyze_dependencies()
        except Exception:
            pass

        spinner.update_message("Finalizing index...")
        context_builder = ContextBuilder()
        context_builder.build_full_context(
            classes=index.get("classes", []) if index else [],
            methods=index.get("methods", []) if index else [],
            endpoints=endpoints_data,
            entities=entities_data,
            config=cfg_data,
            dependencies=deps_data,
            method_summaries=[],
            show_progress=False  # Silent
        )
    except Exception:
        pass

    set_quiet_mode(False)

    # Stop spinner and show completion message
    from utils.output import success
    spinner.stop(success(f"✓ Spring Boot {version} • {java_file_count} files indexed"))

    return True