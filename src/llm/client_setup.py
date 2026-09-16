# client_setup.py
import argparse
import os
import logging
from openai import OpenAI, APIError
from dotenv import load_dotenv
import httpx
from dataclasses import dataclass
from typing import Optional, List, Iterator, Any

logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
log = logging.getLogger('llm_client_setup')


# Adapter to make Anthropic client look like OpenAI client
@dataclass
class OpenAIMessage:
    content: str
    role: str = "assistant"

@dataclass
class OpenAIChoice:
    message: OpenAIMessage
    finish_reason: str = "stop"
    index: int = 0

@dataclass
class OpenAIResponse:
    choices: List[OpenAIChoice]
    model: str = ""
    id: str = ""

@dataclass
class OpenAIChunkDelta:
    content: Optional[str] = None
    role: Optional[str] = None

@dataclass
class OpenAIChunkChoice:
    delta: OpenAIChunkDelta
    finish_reason: Optional[str] = None
    index: int = 0

@dataclass
class OpenAIChunk:
    choices: List[OpenAIChunkChoice]
    model: str = ""
    id: str = ""


class AnthropicOpenAIAdapter:
    """Wraps Anthropic client to provide OpenAI-compatible interface."""

    def __init__(self, anthropic_client):
        self.client = anthropic_client
        self.chat = self  # For client.chat.completions.create()
        self.completions = self
        self.models = self

    def create(self, model: str, messages: list, stream: bool = False,
               max_tokens: int = 4096, temperature: float = 0.7,
               max_completion_tokens: int = None, reasoning_effort: str = None,
               **kwargs) -> Any:
        """Convert OpenAI-style call to Anthropic Messages API."""

        # Use max_completion_tokens if provided (OpenAI o-series style)
        if max_completion_tokens:
            max_tokens = max_completion_tokens

        # Convert messages format
        system_prompt = None
        anthropic_messages = []

        for msg in messages:
            role = msg.get("role", "user")
            content = msg.get("content", "")

            if role == "system":
                system_prompt = content if isinstance(content, str) else str(content)
            else:
                # Handle multimodal content (images)
                if isinstance(content, list):
                    anthropic_content = []
                    for item in content:
                        if item.get("type") == "text":
                            anthropic_content.append({"type": "text", "text": item.get("text", "")})
                        elif item.get("type") == "image_url":
                            # Convert OpenAI image format to Anthropic
                            url = item.get("image_url", {}).get("url", "")
                            if url.startswith("data:"):
                                # Base64 encoded image
                                media_type = url.split(";")[0].split(":")[1]
                                data = url.split(",")[1]
                                anthropic_content.append({
                                    "type": "image",
                                    "source": {
                                        "type": "base64",
                                        "media_type": media_type,
                                        "data": data
                                    }
                                })
                    content = anthropic_content
                else:
                    content = [{"type": "text", "text": str(content)}]

                anthropic_messages.append({
                    "role": "user" if role == "user" else "assistant",
                    "content": content
                })

        # Build request kwargs
        request_kwargs = {
            "model": model,
            "messages": anthropic_messages,
            "max_tokens": max_tokens,
        }

        if system_prompt:
            request_kwargs["system"] = system_prompt

        # Only set temperature if not using extended thinking
        if reasoning_effort:
            # Extended thinking mode - use budget_tokens
            thinking_tokens = {"low": 1024, "medium": 4096, "high": 16384}.get(reasoning_effort, 4096)
            request_kwargs["thinking"] = {
                "type": "enabled",
                "budget_tokens": thinking_tokens
            }
        else:
            request_kwargs["temperature"] = temperature

        if stream:
            return self._stream_response(request_kwargs)
        else:
            return self._sync_response(request_kwargs)

    def _sync_response(self, kwargs) -> OpenAIResponse:
        """Make synchronous API call."""
        response = self.client.messages.create(**kwargs)

        # Extract text and thinking from response
        thinking_content = ""
        text_content = ""
        for block in response.content:
            if hasattr(block, "text"):
                text_content += block.text
            elif hasattr(block, "thinking"):
                thinking_content += block.thinking

        # Prepend thinking with <think> tags so UI can display it
        if thinking_content:
            content = f"<think>{thinking_content}</think>\n{text_content}"
        else:
            content = text_content

        return OpenAIResponse(
            choices=[OpenAIChoice(
                message=OpenAIMessage(content=content),
                finish_reason=response.stop_reason or "stop"
            )],
            model=response.model,
            id=response.id
        )

    def _stream_response(self, kwargs) -> Iterator[OpenAIChunk]:
        """Make streaming API call."""
        with self.client.messages.stream(**kwargs) as stream:
            for event in stream:
                if hasattr(event, "type"):
                    if event.type == "content_block_delta":
                        if hasattr(event.delta, "text"):
                            yield OpenAIChunk(
                                choices=[OpenAIChunkChoice(
                                    delta=OpenAIChunkDelta(content=event.delta.text)
                                )]
                            )
                    elif event.type == "message_stop":
                        yield OpenAIChunk(
                            choices=[OpenAIChunkChoice(
                                delta=OpenAIChunkDelta(),
                                finish_reason="stop"
                            )]
                        )

    def list(self):
        """Mock models.list() for compatibility."""
        @dataclass
        class ModelData:
            id: str
            owned_by: str = "anthropic"

        @dataclass
        class ModelList:
            data: List[ModelData]

        return ModelList(data=[
            ModelData(id="claude-sonnet-4-5-20250929"),
            ModelData(id="claude-3-5-sonnet-20241022"),
            ModelData(id="claude-3-opus-20240229"),
        ])

class ZAIOpenAIAdapter:
    """Wraps OpenAI client to filter out unsupported parameters for Z.AI API."""

    def __init__(self, openai_client):
        self.client = openai_client
        self.chat = self  # For client.chat.completions.create()
        self.completions = self
        self.models = self
        # Expose base_url for compatibility
        self.base_url = getattr(openai_client, 'base_url', 'https://api.z.ai/api/coding/paas/v4')

    def create(self, model: str, messages: list, stream: bool = False,
               max_tokens: int = 4096, temperature: float = 0.7,
               max_completion_tokens: int = None, reasoning_effort: str = None,
               **kwargs) -> Any:
        """Filter out unsupported parameters and make OpenAI-style call to Z.AI API."""

        # Use max_completion_tokens if provided (OpenAI o-series style)
        if max_completion_tokens:
            max_tokens = max_completion_tokens

        # Comprehensive parameter filtering for Z.AI API compatibility
        ZAI_SUPPORTED_PARAMS = {
            # Parameters that are allowed to pass through to ZAI
            'n', 'top_p', 'frequency_penalty', 'presence_penalty',
            'stop', 'logit_bias', 'user', 'stream',

            # CRITICAL: Filter out OpenAI-specific parameters causing 400 errors
            'reasoning_effort',           # OpenAI o-series - PRIMARY CULPRIT
            'max_completion_tokens',      # OpenAI o-series specific
            'response_format',            # OpenAI structured output
            'seed',                       # OpenAI deterministic output
            'tools',                      # OpenAI function calling
            'tool_choice',                # OpenAI function calling
            'parallel_tool_calls',        # OpenAI function calling
            'logprobs',                   # OpenAI token probabilities
            'top_logprobs',              # OpenAI token probabilities
            'service_tier',               # OpenAI tier selection
            'prediction',                 # OpenAI prediction API
            'preview',                    # OpenAI preview features
            'modalities',                 # OpenAI multimodal
            'audio',                      # OpenAI audio parameters
            'voice',                      # OpenAI voice parameters
        }

        # Log ALL incoming parameters for debugging
        log.debug(f"ZAI adapter received kwargs: {list(kwargs.keys())}")

        # Filter out OpenAI-specific parameters that Z.AI doesn't support
        filtered_kwargs = {k: v for k, v in kwargs.items() if k in ZAI_SUPPORTED_PARAMS}

        # Enhanced logging for filtered parameters
        filtered_params = set(kwargs.keys()) - set(filtered_kwargs.keys())
        if filtered_params:
            log.info(f"ZAI adapter filtering out unsupported parameters: {filtered_params}")
            # CRITICAL: Log each filtered parameter with values for debugging
            for param in filtered_params:
                try:
                    param_value = kwargs[param]
                    log.debug(f"ZAI adapter: FILTERED '{param}': {type(param_value).__name__} = {param_value}")
                except Exception as e:
                    log.debug(f"ZAI adapter: FILTERED '{param}': (unable to serialize value: {e})")

        # Log final parameters being sent to ZAI
        log.debug(f"ZAI adapter final parameters to ZAI API: {list(filtered_kwargs.keys())}")

        # Make the API call with filtered parameters
        try:
            response = self.client.chat.completions.create(
                model=model,
                messages=messages,
                stream=stream,  # Pass stream directly
                max_tokens=max_tokens,
                temperature=temperature,
                **filtered_kwargs  # Only pass filtered additional parameters
            )

            if stream:
                return self._stream_response(response)
            else:
                return response

        except Exception as e:
            log.error(f"Z.AI API call failed: {e}")
            raise

    def _stream_response(self, response):
        """Handle streaming response from Z.AI API."""
        try:
            for chunk in response:
                # Convert to OpenAI chunk format
                yield chunk
        except Exception as e:
            log.error(f"Z.AI streaming failed: {e}")
            raise

    def list(self):
        """Mock models.list() for compatibility."""
        @dataclass
        class ModelData:
            id: str
            owned_by: str = "zai"

        @dataclass
        class ModelList:
            data: List[ModelData]

        return ModelList(data=[
            ModelData(id="glm-4.6"),
            ModelData(id="glm-4"),
            ModelData(id="glm-3-turbo"),
        ])

# Import centralized feature configuration (prefer src path; fallback to legacy)
try:
    from src.game.feature_config import (
        MINIMAP_ENABLED, MINIMAP_2D_ENABLED, REASONING_ENABLED,
        MAX_TOKENS, VISION_MAX_TOKENS, USE_VISION_MODEL,
        DEFAULT_LLM_TIMEOUT, DEFAULT_VISION_TIMEOUT
    )
except Exception:
    try:
        from feature_config import (
            MINIMAP_ENABLED, MINIMAP_2D_ENABLED, REASONING_ENABLED,
            MAX_TOKENS, VISION_MAX_TOKENS, USE_VISION_MODEL,
            DEFAULT_LLM_TIMEOUT, DEFAULT_VISION_TIMEOUT
        )
    except Exception:
        log.warning("feature_config not found, using local defaults")
        MINIMAP_ENABLED = False
        MINIMAP_2D_ENABLED = False
        REASONING_ENABLED = True
        MAX_TOKENS = 1024
        VISION_MAX_TOKENS = 300
        USE_VISION_MODEL = True
        DEFAULT_LLM_TIMEOUT = 120
        DEFAULT_VISION_TIMEOUT = 30

# --- Configuration Defaults ---
DEFAULT_MODE = "ANTHROPIC" # OPENAI, GEMINI, OLLAMA, LMSTUDIO, GROQ, TOGETHER, GROK, ANTHROPIC
DEFAULT_OPENAI_MODEL = "o3"
DEFAULT_GEMINI_MODEL = "gemini-2.5-flash-preview-05-20"
DEFAULT_OLLAMA_MODEL = "gemma3:27b-it-q4_K_M"
DEFAULT_LMSTUDIO_MODEL = "google/gemma-3-27b"
DEFAULT_GROQ_MODEL = "meta-llama/llama-4-maverick-17b-128e-instruct"
DEFAULT_TOGETHER_MODEL = "Qwen/Qwen2.5-VL-72B-Instruct"
DEFAULT_GROK_MODEL = "grok-3-mini"
DEFAULT_ANTHROPIC_MODEL = "claude-sonnet-4-20250514"
DEFAULT_CUSTOM_MODEL = "gpt-4o-mini"  # Default model for custom OpenAI-compatible endpoints
DEFAULT_ZAI_MODEL = "glm-4.6"  # Default model for Z.AI GLM
DEFAULT_MINIMAX_MODEL = "MiniMax-M2.5"  # MiniMax Code Plus / Token Plan
DEFAULT_MINIMAX_BASE_URL = "https://api.minimax.io/v1"

DEFAULT_MODEL_BY_MODE = {
    "OPENAI": DEFAULT_OPENAI_MODEL,
    "GEMINI": DEFAULT_GEMINI_MODEL,
    "OLLAMA": DEFAULT_OLLAMA_MODEL,
    "LMSTUDIO": DEFAULT_LMSTUDIO_MODEL,
    "GROQ": DEFAULT_GROQ_MODEL,
    "TOGETHER": DEFAULT_TOGETHER_MODEL,
    "GROK": DEFAULT_GROK_MODEL,
    "ANTHROPIC": DEFAULT_ANTHROPIC_MODEL,
    "CUSTOM": DEFAULT_CUSTOM_MODEL,
    "ZAI": DEFAULT_ZAI_MODEL,
    "MINIMAX": DEFAULT_MINIMAX_MODEL,
}

MODES = list(DEFAULT_MODEL_BY_MODE.keys())

REASONING_EFFORT = os.getenv("FE_REASONING_EFFORT", os.getenv("REASONING_EFFORT", "high")).lower()  # "low", "medium", or "high"
ONE_IMAGE_PER_PROMPT = False # Set to False to allow multiple images per prompt (Often performs better with single image)

# Legacy configuration variables for backward compatibility
# These now come from feature_config.py but we keep them here for modules that import directly
MINIMAP_2D = MINIMAP_2D_ENABLED  # Alias for compatibility
SYSTEM_PROMPT_UNSUPPORTED = False # Instead it will be injected into messages. (NOT IMPLEMENTED YET)
TEMPERATURE = 0.7 # Default temperature for model responses
IMAGE_DETAIL = os.getenv("FE_IMAGE_DETAIL", "high").lower()  # "low" or "high" (GBA 240x160 needs "high" to read text)
USES_MAX_COMPLETION_TOKENS = True # Some models (OAI o3) require setting max_completion_tokens instead of max_tokens
USES_DEFAULT_TEMPERATURE = True # Some models (OAI o3) don't support temperature, so we use a default value (1)

# Use timeouts from feature_config if available
try:
    from feature_config import DEFAULT_LLM_TIMEOUT
    TIMEOUT = httpx.Timeout(DEFAULT_LLM_TIMEOUT, read=DEFAULT_LLM_TIMEOUT, write=10.0, connect=10.0)
except (ImportError, NameError):
    TIMEOUT = httpx.Timeout(15.0, read=15.0, write=10.0, connect=10.0) 

load_dotenv() # Load variables from .env file


def get_config(env_var: str, default_value: str) -> str:
    """Gets configuration from environment variable or returns default."""
    value = os.getenv(env_var, default_value)
    source = 'Env Var' if os.getenv(env_var) else 'Default'
    # Avoid logging sensitive keys like API keys directly
    if "API_KEY" not in env_var:
         log.info(f"Config '{env_var}': {value} (Source: {source})")
    else:
         # Log API keys securely (presence only)
         log.info(f"Config '{env_var}': {'Present' if value else 'Not Set'} (Source: {source})")
    return value

# helper function for selecting AI model
def parse_mode_arg(modes, default_mode=DEFAULT_MODE):
    # First check for LLM_PROVIDER environment variable
    mode = os.getenv('LLM_PROVIDER', '').upper()

    # If LLM_PROVIDER is set and valid, use it
    if mode in modes:
        print(f"LLM mode from LLM_PROVIDER environment variable: {mode}")
        return mode

    # Otherwise check command line arguments
    parser = argparse.ArgumentParser(description="Parse LLM mode argument", add_help=False)

    parser.add_argument(
        '--mode',
        choices=modes,
        help='LLM mode to use (choose from the supported modes)'
    )

    # Use parse_known_args to ignore other arguments
    args, _ = parser.parse_known_args()
    mode = args.mode

    if not mode:
        print("\nNo LLM mode specified via command line.")
        print("Please choose the LLM mode from the list below:")
        for i, m in enumerate(modes, start=1):
            print(f"  {i}. {m}")
        choice = input("Enter the number of your choice: ").strip()

        try:
            choice_num = int(choice)
            if 1 <= choice_num <= len(modes):
                mode = modes[choice_num - 1]
                print(f"Great! You selected: {mode}")
            else:
                print(f"Invalid choice. Defaulting to '{default_mode}'.")
                mode = default_mode
        except ValueError:
            print(f"Invalid input. Defaulting to '{default_mode}'.")
            mode = default_mode
    else:
        print(f"LLM mode specified via command line: {mode}")

    return mode

def setup_vision_model() -> tuple[OpenAI | None, str | None]:
    """Setup optional vision model for image processing when main model doesn't support it."""
    # Check if vision model is enabled in feature config
    if not USE_VISION_MODEL:
        log.info("Vision model disabled in feature configuration")
        return None, None

    # Check for GLM-MCP vision provider
    vision_provider = os.getenv("VISION_PROVIDER", "").upper()

    if vision_provider == "GLM-MCP":
        # Initialize GLM MCP vision client
        try:
            from src.llm.zai_mcp_client import ZAIMCPClient
            api_key = os.getenv("Z_AI_API_KEY")  # Use Z_AI_API_KEY as per Z.AI documentation
            if not api_key:
                log.error("Z_AI_API_KEY required for GLM-MCP vision provider")
                return None, None

            mcp_client = ZAIMCPClient(api_key=api_key, mode="ZAI")  # Z_AI_MODE=ZAI as per documentation
            log.info("GLM-MCP Vision client initialized")
            return mcp_client, "glm-mcp-vision"
        except Exception as e:
            log.error(f"Failed to initialize GLM-MCP vision: {e}", exc_info=True)
            return None, None

    # Traditional OpenAI-compatible vision models
    vision_base_url = os.getenv("VISION_BASE_URL")
    vision_model = os.getenv("VISION_MODEL")
    vision_api_key = os.getenv("VISION_API_KEY")

    if not vision_base_url or not vision_model:
        return None, None

    if not vision_api_key:
        vision_api_key = "dummy-key"
        log.warning("VISION_API_KEY not found, using placeholder key.")

    try:
        vision_client = OpenAI(
            base_url=vision_base_url,
            api_key=vision_api_key,
            timeout=TIMEOUT
        )
        log.info(f"Vision model configured: {vision_model} at {vision_base_url}")
        return vision_client, vision_model
    except Exception as e:
        log.error(f"Failed to initialize vision model: {e}")
        return None, None

def setup_llm_client() -> tuple[OpenAI | None, str | None, str | None]:
    MODE = parse_mode_arg(MODES)

    client = None
    model = None
    supports_reasoning = False

    log.info(f"--- Initializing LLM Client (Mode: {MODE}) ---")

    if MODE == "OPENAI":
        # OpenAI requires a real API key from environment
        api_key = os.getenv("OPENAI_API_KEY")
        if not api_key:
            log.error("MODE is OPENAI but OPENAI_API_KEY not found in environment variables.")
            return None, None, False
        try:
            client = OpenAI(api_key=api_key, timeout=TIMEOUT)
            model = get_config("OPENAI_MODEL", DEFAULT_OPENAI_MODEL)
            supports_reasoning = True
            log.info(f"Using OpenAI Mode. Model: {model}")
        except Exception as e:
            log.error(f"Failed to initialize OpenAI client: {e}", exc_info=True)
            return None, None, False

    elif MODE == "GEMINI":
        # Gemini requires a real API key from environment
        api_key = os.getenv("GEMINI_API_KEY")
        if not api_key:
            log.error("MODE is GEMINI but GEMINI_API_KEY not found in environment variables.")
            return None, None, False
        try:
            client = OpenAI(
                api_key=api_key,
                base_url="https://generativelanguage.googleapis.com/v1beta/openai/",
                timeout=TIMEOUT
            )
            model = get_config("GEMINI_MODEL", DEFAULT_GEMINI_MODEL)
            supports_reasoning = True
            log.info(f"Using Gemini Mode (via OpenAI client). Model: {model}")
        except Exception as e:
            log.error(f"Failed to initialize Gemini client (via OpenAI compat): {e}", exc_info=True)
            return None, None, False

    elif MODE == "OLLAMA":
        ollama_base_url = get_config("OLLAMA_BASE_URL", 'http://localhost:11434/v1')
        try:
            client = OpenAI(
                base_url=ollama_base_url,
                api_key='ollama', # Hardcoded placeholder key for Ollama
            )
            model = get_config("OLLAMA_MODEL", DEFAULT_OLLAMA_MODEL)
            log.info(f"Using Ollama Mode. Base URL: {ollama_base_url}, Model: {model} (API Key: Placeholder)")
        except Exception as e:
            log.error(f"Failed to initialize Ollama client: {e}", exc_info=True)
            return None, None, False

    elif MODE == "LMSTUDIO":
        lmstudio_base_url = get_config("LMSTUDIO_BASE_URL", 'http://localhost:1234/v1')
        try:
            client = OpenAI(
                base_url=lmstudio_base_url,
                api_key='lmstudio', # Hardcoded placeholder key for LMStudio
            )
            model = get_config("LMSTUDIO_MODEL", DEFAULT_LMSTUDIO_MODEL)
            log.info(f"Using LMStudio Mode. Base URL: {lmstudio_base_url}, Model: {model} (API Key: Placeholder)")
        except Exception as e:
            log.error(f"Failed to initialize LMStudio client: {e}", exc_info=True)
            return None, None, False
        
    elif MODE == "GROQ":
        api_key = os.getenv("GROQ_API_KEY")
        if not api_key:
            log.error("MODE is GROQ but GROQ_API_KEY not found in environment variables.")
            return None, None, False
        try:
            client = OpenAI(
                base_url="https://api.groq.com/openai/v1",
                api_key=api_key,
                timeout=TIMEOUT
            )
            model = get_config("GROQ_MODEL", DEFAULT_GROQ_MODEL)
            log.info(f"Using Groq Mode (via OpenAI client). Model: {model}")
        except Exception as e:
            log.error(f"Failed to initialize Groq client: {e}", exc_info=True)
            return None, None, False
    
    elif MODE == "GROK":
        api_key = os.getenv("GROK_API_KEY")
        if not api_key:
            log.error("MODE is GROK but GROK_API_KEY not found in environment variables.")
            return None, None, False
        try:
            client = OpenAI(
                base_url="https://api.x.ai/v1",
                api_key=api_key,
                timeout=TIMEOUT
            )
            supports_reasoning = True # Grok supports reasoning
            model = get_config("GROK_MODEL", DEFAULT_GROK_MODEL)
            log.info(f"Using Grok Mode (via OpenAI client). Model: {model}")
        except Exception as e:
            log.error(f"Failed to initialize Grok client: {e}", exc_info=True)
            return None, None, False
        
    elif MODE == "ANTHROPIC":
        api_key = os.getenv("ANTHROPIC_API_KEY")
        if not api_key:
            log.error("MODE is ANTHROPIC but ANTHROPIC_API_KEY not found in environment variables.")
            return None, None, False
        try:
            client = OpenAI(
                base_url="https://api.anthropic.com/v1/",
                api_key=api_key,
                timeout=TIMEOUT
            )
            supports_reasoning = True
            model = get_config("ANTHROPIC_MODEL", DEFAULT_ANTHROPIC_MODEL)
            log.info(f"Using ANTHROPIC Mode (via OpenAI client). Model: {model}")
        except Exception as e:
            log.error(f"Failed to initialize ANTHROPIC client: {e}", exc_info=True)
            return None, None, False

    elif MODE == "TOGETHER":
        api_key = os.getenv("TOGETHER_API_KEY")
        if not api_key:
            log.error("MODE is TOGETHER but TOGETHER_API_KEY not found in environment variables.")
            return None, None, False
        try:
            client = OpenAI(
                base_url="https://api.together.xyz/v1",
                api_key=api_key,
                timeout=TIMEOUT
            )
            model = get_config("TOGETHER_MODEL", DEFAULT_TOGETHER_MODEL)
            log.info(f"Using Together Mode (via OpenAI client). Model: {model}")
        except Exception as e:
            log.error(f"Failed to initialize Together client: {e}", exc_info=True)
            return None, None, False        


    elif MODE == "MINIMAX":
        # MiniMax Code Plus / Token Plan (OpenAI-compatible)
        # Docs: https://platform.minimax.io/docs/token-plan/quickstart
        api_key = os.getenv("MINIMAX_API_KEY") or os.getenv("MINIMAX_TOKEN_PLAN_KEY")
        if not api_key:
            log.error("MODE is MINIMAX but MINIMAX_API_KEY not found in environment variables.")
            return None, None, False
        base_url = get_config("MINIMAX_BASE_URL", DEFAULT_MINIMAX_BASE_URL)
        try:
            # Support longer timeouts for agentic turns
            mm_timeout = os.getenv("MINIMAX_TIMEOUT") or os.getenv("CUSTOM_TIMEOUT")
            if mm_timeout:
                try:
                    timeout_val = float(mm_timeout)
                    timeout_obj = httpx.Timeout(timeout_val, read=timeout_val, write=10.0, connect=10.0)
                except ValueError:
                    timeout_obj = TIMEOUT
            else:
                timeout_obj = TIMEOUT

            client = OpenAI(
                base_url=base_url,
                api_key=api_key,
                timeout=timeout_obj,
            )
            model = get_config("MINIMAX_MODEL", DEFAULT_MINIMAX_MODEL)
            # Do NOT set supports_reasoning: that path injects OpenAI reasoning_effort.
            # MiniMax thinking is handled via extra_body reasoning_split in the driver.
            supports_reasoning = False
            log.info(f"Using MINIMAX Mode (OpenAI-compatible Token Plan). Base URL: {base_url}, Model: {model}")
        except Exception as e:
            log.error(f"Failed to initialize MINIMAX client: {e}", exc_info=True)
            return None, None, False

    elif MODE == "CUSTOM":
        # Custom OpenAI-compatible API endpoint
        base_url = os.getenv("CUSTOM_BASE_URL")
        api_key = os.getenv("CUSTOM_API_KEY")
        
        if not base_url:
            log.error("MODE is CUSTOM but CUSTOM_BASE_URL not found in environment variables.")
            return None, None, False
        
        # API key is optional for some custom endpoints
        if not api_key:
            api_key = "dummy-key"  # Some endpoints don't require a real key
            log.warning("CUSTOM_API_KEY not found, using placeholder key. Set CUSTOM_API_KEY if authentication is required.")
        
        try:
            # Support custom timeout if specified
            custom_timeout = os.getenv("CUSTOM_TIMEOUT")
            if custom_timeout:
                try:
                    timeout_val = float(custom_timeout)
                    custom_timeout_obj = httpx.Timeout(timeout_val, read=timeout_val, write=10.0, connect=10.0)
                except ValueError:
                    log.warning(f"Invalid CUSTOM_TIMEOUT value: {custom_timeout}, using default")
                    custom_timeout_obj = TIMEOUT
            else:
                custom_timeout_obj = TIMEOUT
            
            client = OpenAI(
                base_url=base_url,
                api_key=api_key,
                timeout=custom_timeout_obj
            )
            model = get_config("CUSTOM_MODEL", DEFAULT_CUSTOM_MODEL)
            
            # Check if custom endpoint supports reasoning
            custom_reasoning = os.getenv("CUSTOM_SUPPORTS_REASONING", "false").lower() == "true"
            if custom_reasoning:
                supports_reasoning = True
                log.info(f"Custom endpoint supports reasoning (CUSTOM_SUPPORTS_REASONING=true)")
            
            log.info(f"Using CUSTOM Mode (OpenAI-compatible). Base URL: {base_url}, Model: {model}")
        except Exception as e:
            log.error(f"Failed to initialize CUSTOM client: {e}", exc_info=True)
            return None, None, False

    elif MODE == "ZAI":
        # Z.AI GLM requires API key from environment (use Z_AI_API_KEY for consistency)
        api_key = os.getenv("Z_AI_API_KEY")
        if not api_key:
            log.error("MODE is ZAI but Z_AI_API_KEY not found in environment variables.")
            return None, None, False
        try:
            # Create base OpenAI client
            raw_client = OpenAI(
                base_url="https://api.z.ai/api/coding/paas/v4",
                api_key=api_key,
                timeout=TIMEOUT
            )
            # Wrap with ZAI adapter to filter unsupported parameters
            client = ZAIOpenAIAdapter(raw_client)
            supports_reasoning = False  # Disable reasoning_effort parameter for ZAI compatibility
            model = get_config("Z_AI_MODEL", DEFAULT_ZAI_MODEL)  # Use Z_AI_MODEL for consistency
            log.info(f"Using ZAI GLM Mode with adapter. Model: {model}")
        except Exception as e:
            log.error(f"Failed to initialize ZAI client: {e}", exc_info=True)
            return None, None, False

    else:
        log.error(f"Invalid MODE selected: {MODE}. Set MODE environment variable correctly (e.g., OPENAI, GEMINI, OLLAMA, LMSTUDIO, ZAI).")
        return None, None, False

    if client and model:
        try:
            log.info(f"Attempting to verify connection to {MODE} service...")
            models_list = client.models.list()
            log.info(f"Successfully connected to {MODE} service (Base URL: {client.base_url}). Found {len(models_list.data)} models.")
        except APIError as e:
            log.error(f"APIError verifying connection to {MODE}: {e}. Check URL/Permissions/Service Status.")
        except Exception as e:
            log.warning(f"Unexpected error verifying {MODE} connection: {e}. Proceeding cautiously.")

    log.info(f"LLM Client setup complete. Image Detail: {IMAGE_DETAIL}")
    print(f"Client: {client}, model: {model}, supports_reasoning: {supports_reasoning}")
    return client, model, supports_reasoning


def provider_request_extras() -> dict:
    """Extra OpenAI-compatible request fields for the active provider."""
    provider = (os.getenv("LLM_PROVIDER") or os.getenv("MODE") or "").upper()
    if provider == "MINIMAX":
        # Keeps chain-of-thought out of message.content
        return {"extra_body": {"reasoning_split": True}}
    return {}
