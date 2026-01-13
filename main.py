#!/usr/bin/env python3
import os
import sys

# Add nix directory to path so imports work from anywhere
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from commands import init, status
from llm.client import get_api_key, save_api_key


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

        # Check for API key
        api_key = get_api_key()
        if not api_key:
            print("Error: API key not configured.")
            print("Run: nix config <your_groq_api_key>")
            sys.exit(1)

        # Check if .nix folder exists
        from config import nix_exists

        if nix_exists():
            # Already initialized, show status
            status.run()
        else:
            # First time, run initialization
            init.run()

    except KeyboardInterrupt:
        print("\nOperation cancelled by user.")
        sys.exit(130)
    except Exception as e:
        print(f"Error: {str(e)}")
        sys.exit(1)


if __name__ == "__main__":
    main()