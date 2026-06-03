"""
Interactive LLM Provider Setup

Prompts user to select provider and configure API keys if needed.
"""

import os
import sys
from pathlib import Path

# Add project root to path
PROJECT_ROOT = Path(__file__).parent.parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from dotenv import load_dotenv, set_key

# Load existing .env
ENV_FILE = PROJECT_ROOT / ".env"
load_dotenv(ENV_FILE)

# Provider configurations
PROVIDERS = {
    "1": ("OPENAI", "OpenAI", "OPENAI_API_KEY"),
    "2": ("ANTHROPIC", "Anthropic Claude API", "ANTHROPIC_API_KEY"),
    "3": ("GEMINI", "Google Gemini", "GEMINI_API_KEY"),
    "4": ("GROQ", "Groq", "GROQ_API_KEY"),
    "5": ("TOGETHER", "Together AI", "TOGETHER_API_KEY"),
    "6": ("GROK", "xAI Grok", "GROK_API_KEY"),
    "7": ("OLLAMA", "Ollama (Local)", None),
    "8": ("LMSTUDIO", "LM Studio (Local)", None),
    "9": ("CUSTOM", "Custom OpenAI-compatible", "CUSTOM_BASE_URL"),
    "10": ("ZAI", "Z.AI GLM Coding Plan", "Z_AI_API_KEY"),
}


def print_banner():
    """Print startup banner."""
    print()
    print("=" * 50)
    print("  Fire Emblem AI - LLM Provider Setup")
    print("=" * 50)
    print()


def get_current_provider():
    """Get currently configured provider from environment."""
    return os.getenv("LLM_PROVIDER", "").upper()


def check_api_key(key_name: str) -> bool:
    """Check if an API key is set and not a placeholder."""
    value = os.getenv(key_name, "")
    if not value:
        return False
    # Check for common placeholder values
    placeholders = ["your_", "xxx", "sk-xxx", "placeholder", "enter_"]
    return not any(p in value.lower() for p in placeholders)


def prompt_for_api_key(provider: str, key_name: str) -> str | None:
    """Prompt user to enter an API key."""
    print(f"\n{provider} requires an API key.")
    print(f"Environment variable: {key_name}")
    print()

    try:
        key = input(f"Enter your {key_name} (or press Enter to cancel): ").strip()
        if not key:
            return None
        return key
    except (KeyboardInterrupt, EOFError):
        print("\nCancelled.")
        return None


def save_to_env(key: str, value: str):
    """Save a key-value pair to .env file."""
    # Create .env from example if it doesn't exist
    if not ENV_FILE.exists():
        example = PROJECT_ROOT / ".env.example"
        if example.exists():
            ENV_FILE.write_text(example.read_text())
        else:
            ENV_FILE.touch()

    set_key(str(ENV_FILE), key, value)
    os.environ[key] = value
    print(f"Saved {key} to .env")


def setup_custom_provider() -> bool:
    """Setup custom OpenAI-compatible endpoint."""
    print("\nCustom provider requires a base URL.")

    base_url = os.getenv("CUSTOM_BASE_URL", "")
    if base_url and "localhost" not in base_url.lower():
        print(f"Current: {base_url}")
        try:
            use_existing = input("Use existing URL? [Y/n]: ").strip().lower()
            if not use_existing or use_existing == 'y':
                return True
        except (KeyboardInterrupt, EOFError):
            return False

    try:
        url = input("Enter base URL (e.g., http://localhost:8080/v1): ").strip()
        if not url:
            return False

        save_to_env("CUSTOM_BASE_URL", url)

        # Optional API key
        api_key = input("Enter API key (press Enter if not required): ").strip()
        if api_key:
            save_to_env("CUSTOM_API_KEY", api_key)

        # Model name
        model = input("Enter model name [gpt-4o-mini]: ").strip() or "gpt-4o-mini"
        save_to_env("CUSTOM_MODEL", model)

        return True
    except (KeyboardInterrupt, EOFError):
        return False


def setup_zai_provider() -> bool:
    """Setup Z.AI GLM coding plan with vision configuration."""
    print("\nZ.AI GLM provides both LLM and vision capabilities.")
    print("This setup will configure both components for optimal performance.")

    # Check for Node.js requirement for MCP vision
    import shutil
    has_node = shutil.which("node") is not None
    has_npm = shutil.which("npm") is not None

    if not has_node or not has_npm:
        print("\n⚠️  Warning: Node.js and npm are required for Z.AI MCP vision server")
        if not has_node:
            print("  - Node.js not found. Please install Node.js from https://nodejs.org")
        if not has_npm:
            print("  - npm not found. Please install npm")
        print()
        try:
            continue_setup = input("Continue anyway? LLM will work, but vision will be disabled [y/N]: ").strip().lower()
            if continue_setup != 'y':
                return False
        except (KeyboardInterrupt, EOFError):
            return False

    # Get existing configuration
    current_model = os.getenv("Z_AI_MODEL", "glm-4.6")
    current_vision = os.getenv("VISION_PROVIDER", "GLM-MCP")

    print(f"\nCurrent configuration:")
    print(f"  - Model: {current_model}")
    print(f"  - Vision: {current_vision}")
    print()

    try:
        # Model configuration
        model = input(f"Enter Z.AI model [glm-4.6]: ").strip() or "glm-4.6"
        save_to_env("Z_AI_MODEL", model)

        # Vision configuration
        if has_node and has_npm:
            print("\nVision Configuration:")
            print("  Z.AI MCP vision server provides advanced image analysis")
            print("  Uses @z_ai/mcp-server package (auto-installed)")

            use_vision = input("Enable Z.AI MCP vision? [Y/n]: ").strip().lower()
            if not use_vision or use_vision == 'y':
                save_to_env("VISION_PROVIDER", "GLM-MCP")
                print("  ✅ Z.AI MCP vision enabled")
            else:
                save_to_env("VISION_PROVIDER", "OPENAI")  # Fallback to OpenAI
                print("  ℹ️  Vision disabled - you can configure other vision providers manually")

        print(f"\n✅ Z.AI GLM configured successfully!")
        print(f"   - Model: {model}")
        if has_node and has_npm:
            vision_provider = os.getenv("VISION_PROVIDER", "")
            if vision_provider == "GLM-MCP":
                print(f"   - Vision: Z.AI MCP (automatic setup)")
            else:
                print(f"   - Vision: Disabled")
        else:
            print(f"   - Vision: Not available (missing Node.js/npm)")

        return True

    except (KeyboardInterrupt, EOFError):
        return False


def interactive_setup() -> str | None:
    """Run interactive provider selection and setup.

    Returns the selected provider name, or None if cancelled.
    """
    print_banner()

    # Check if provider is already configured
    current = get_current_provider()
    if current and current in [p[0] for p in PROVIDERS.values()]:
        print(f"Current provider: {current}")
        try:
            change = input("Change provider? [y/N]: ").strip().lower()
            if change != 'y':
                # Verify credentials for current provider
                for key, (name, desc, api_key) in PROVIDERS.items():
                    if name == current:
                        if api_key and not check_api_key(api_key):
                            print(f"\nWarning: {api_key} not configured!")
                            new_key = prompt_for_api_key(name, api_key)
                            if new_key:
                                save_to_env(api_key, new_key)
                        break
                return current
        except (KeyboardInterrupt, EOFError):
            return current

    # Show provider menu
    print("Select your LLM provider:\n")
    for key, (name, desc, _) in PROVIDERS.items():
        marker = " *" if name == current else ""
        print(f"  {key:>2}. {desc}{marker}")

    print()
    print("  0. Exit")
    print()

    try:
        choice = input("Enter choice [1]: ").strip() or "1"
    except (KeyboardInterrupt, EOFError):
        print("\nCancelled.")
        return None

    if choice == "0":
        return None

    if choice not in PROVIDERS:
        print(f"Invalid choice: {choice}")
        return None

    provider, desc, api_key_name = PROVIDERS[choice]
    print(f"\nSelected: {desc}")

    # Handle special providers
    if provider == "CUSTOM":
        if not setup_custom_provider():
            return None
    elif provider == "ZAI":
        if not setup_zai_provider():
            return None
    elif api_key_name:
        # Check if API key exists
        if not check_api_key(api_key_name):
            key = prompt_for_api_key(provider, api_key_name)
            if not key:
                print("API key required. Setup cancelled.")
                return None
            save_to_env(api_key_name, key)

    # Save provider selection
    save_to_env("LLM_PROVIDER", provider)

    print(f"\n{provider} configured successfully!")
    return provider


def main():
    """Entry point for interactive setup."""
    try:
        provider = interactive_setup()
        if provider:
            print(f"\nReady to start with {provider}")
            # Write provider to temp file for shell scripts to read
            result_file = PROJECT_ROOT / ".llm_provider_result"
            result_file.write_text(provider)
            sys.exit(0)
        else:
            print("\nSetup cancelled.")
            sys.exit(1)
    except Exception as e:
        print(f"\nError: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
