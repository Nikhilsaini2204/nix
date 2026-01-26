#!/usr/bin/env python3
import os
import sys

# Add nix directory to path so imports work from anywhere
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from commands import init, status
from llm.client import get_api_key, save_api_key
from config import cleanup_nix_folder


def main():
    """Main entry point for nix"""
    try:
        # Parse command line arguments
        args = sys.argv[1:]
        command = args[0] if args else None

        # Handle config command: nix config <api_key>
        if command == "config":
            if len(args) < 2:
                print("Usage: nix config <your_groq_api_key>")
                print("Get your key at: https://console.groq.com/keys")
                sys.exit(1)
            save_api_key(args[1])
            print("API key saved successfully!")
            return

        # Handle help command
        if command == "help":
            print_help()
            return

        # Check for API key
        api_key = get_api_key()
        if not api_key:
            print("Error: API key not configured.")
            print("Run: nix config <your_groq_api_key>")
            print("Get your key at: https://console.groq.com/keys")
            sys.exit(1)

        # Check if .nix folder exists
        from config import nix_exists

        # Handle explicit status command
        if command == "status":
            if nix_exists():
                status.run()
            else:
                print("Project not initialized. Run 'nix' first to initialize.")
            return

        # Handle explicit init command
        if command == "init":
            init.run()
            return

        # If args provided, run as single command then start REPL
        if args:
            # Initialize if needed
            if not nix_exists():
                if not init.run():
                    sys.exit(1)

            # Run the command
            user_input = " ".join(args)
            run_natural_language(user_input)
            print()

        # Start interactive REPL
        start_repl()

    except KeyboardInterrupt:
        cleanup_nix_folder()
        print("\nGoodbye!")
        sys.exit(0)
    except Exception as e:
        print(f"Error: {str(e)}")
        sys.exit(1)


def start_repl():
    """Start the interactive REPL."""
    from config import nix_exists

    # Initialize if needed
    if not nix_exists():
        if not init.run():
            print("Failed to initialize. Exiting.")
            sys.exit(1)

    # Register tools once at start
    from tools import register_all_tools
    register_all_tools()

    print_welcome()

    while True:
        try:
            # Get user input
            from utils.output import muted
            user_input = input(f"\n{muted('>')} ").strip()

            # Skip empty input
            if not user_input:
                continue

            # Handle special commands
            if user_input.lower() in ("exit", "quit", "q"):
                cleanup_nix_folder()
                print("Goodbye!")
                break

            if user_input.lower() == "help":
                print_repl_help()
                continue

            if user_input.lower() == "status":
                status.run()
                continue

            if user_input.lower() == "clear":
                os.system("clear" if os.name == "posix" else "cls")
                print_welcome()
                continue

            if user_input.lower() == "new":
                from core.agent import reset_agent
                reset_agent()
                print("Started new conversation.")
                continue

            # Check if input is vague and needs guidance
            from core.capabilities import is_vague_input, show_capabilities_prompt, get_capability_by_choice, get_tool_for_capability

            if is_vague_input(user_input):
                show_capabilities_prompt()
                try:
                    choice = input(f"{muted('>')} ").strip()
                    if not choice:
                        continue

                    capability = get_capability_by_choice(choice)
                    if capability:
                        run_capability(capability)
                    else:
                        # Not a menu choice, treat as natural language
                        run_natural_language(choice, tools_registered=True)
                except KeyboardInterrupt:
                    cleanup_nix_folder()
                    print("\nGoodbye!")
                    break
                continue

            # Process natural language
            run_natural_language(user_input, tools_registered=True)

        except KeyboardInterrupt:
            cleanup_nix_folder()
            print("\nGoodbye!")
            break
        except EOFError:
            cleanup_nix_folder()
            print("\nGoodbye!")
            break


def run_natural_language(user_input, tools_registered=False):
    """
    Process natural language input through the agent.

    Args:
        user_input: Natural language command
        tools_registered: Whether tools are already registered
    """
    from core.agent import run_agent

    if not tools_registered:
        from tools import register_all_tools
        register_all_tools()

    response = run_agent(user_input)

    print()
    print(response)


def run_capability(capability):
    """
    Run a specific capability directly (bypass LLM for tool execution).

    Args:
        capability: Capability dict from capabilities.py
    """
    from core.capabilities import get_tool_for_capability
    from core.tools_registry import execute_tool
    from core.agent import run_agent
    from utils.output import muted, print_step

    tool_names = get_tool_for_capability(capability)

    print()

    results = []
    for tool_name in tool_names:
        result = execute_tool(tool_name, {})
        results.append((tool_name, result))
        print()

    # Build a prompt with the results for the LLM to summarize
    results_text = ""
    for tool_name, result in results:
        results_text += f"\n{tool_name} returned:\n{result}\n"

    summary_prompt = f"I just analyzed a Spring Boot project. Here are the results:\n{results_text}\n\nPlease provide a clear, helpful summary of these findings for the developer."

    response = run_agent(summary_prompt)
    print(response)


def print_welcome():
    """Print welcome message with ASCII banner centered."""
    from utils.output import bold, muted, print_banner, center_text, get_terminal_width
    print_banner()

    # Center the subtitle text
    subtitle = "AI-powered assistant for Spring Boot projects"
    hint = "Type your question or 'help' for options. Ctrl+C to exit."

    width = get_terminal_width()
    subtitle_padding = max(0, (width - len(subtitle)) // 2)
    hint_padding = max(0, (width - len(hint)) // 2)

    print(' ' * subtitle_padding + muted(subtitle))
    print(' ' * hint_padding + muted(hint))
    print()


def print_repl_help():
    """Print REPL help."""
    print()
    print("Commands:")
    print("  help     Show this help")
    print("  status   Show project status")
    print("  new      Start fresh conversation")
    print("  clear    Clear the screen")
    print("  exit     Exit nix")
    print()
    print("Or just type naturally:")
    print("  analyze my dependencies")
    print("  analyze everything")
    print("  what is my project structure")


def print_help():
    """Print CLI help information."""
    print("nix - AI-powered CLI for Spring Boot projects")
    print()
    print("Usage:")
    print("  nix                          Start interactive mode")
    print("  nix <question>               Ask a question and start interactive mode")
    print("  nix config <api_key>         Configure your Groq API key")
    print("  nix status                   Show project status (non-interactive)")
    print("  nix help                     Show this help message")
    print()
    print("Interactive Mode:")
    print("  Once started, nix stays open for continuous conversation.")
    print("  Press Ctrl+C to exit.")
    print()
    print("Examples:")
    print("  nix")
    print("  nix analyze my dependencies")
    print()
    print("Get your API key at: https://console.groq.com/keys")


if __name__ == "__main__":
    main()
