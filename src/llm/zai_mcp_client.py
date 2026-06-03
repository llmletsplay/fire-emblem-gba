"""
Z.AI MCP Vision Client for Fire Emblem AI
Provides vision capabilities through Z.AI's MCP server for image understanding
"""

import os
import json
import logging
import subprocess
import asyncio
import time
from typing import Optional, Dict, Any, List
from pathlib import Path

log = logging.getLogger('zai_mcp_client')

class ZAIMCPClient:
    """Client for interacting with Z.AI's MCP Vision Server"""

    def __init__(self, api_key: str, mode: str = "ZAI", timeout: int = 30):
        """
        Initialize the Z.AI MCP Client

        Args:
            api_key: Z.AI API key
            mode: MCP mode (should be "ZAI")
            timeout: Timeout for vision analysis operations
        """
        self.api_key = api_key
        self.mode = mode
        self.timeout = timeout  # Add timeout attribute
        self.mcp_process = None
        self.is_connected = False

        # CRITICAL: Vision analysis retry state for robust error handling
        self.vision_failure_count = 0
        self.last_vision_failure_time = 0
        self.vision_backoff_seconds = 60  # Start with 60 seconds backoff
        self.max_vision_backoff_seconds = 300  # Max 5 minutes backoff
        self.vision_temporarily_disabled = False
        self.vision_retry_enabled = True

        log.info(f"Z.AI MCP Client initialized with robust retry mechanism (timeout: {timeout}s)")

        # Start the MCP server synchronously
        self._start_mcp_server_sync()

    async def start_mcp_server(self) -> bool:
        """
        Start the Z.AI MCP vision server

        Returns:
            True if server started successfully, False otherwise
        """
        try:
            # Set up environment variables for MCP server
            env = os.environ.copy()
            env['Z_AI_API_KEY'] = self.api_key
            env['Z_AI_MODE'] = self.mode

            # Start MCP server using npx
            cmd = [
                'npx', '-y', '@z_ai/mcp-server'
            ]

            log.info("Starting Z.AI MCP vision server...")

            # Start the subprocess
            self.mcp_process = await asyncio.create_subprocess_exec(
                *cmd,
                env=env,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )

            # Give it a moment to start
            await asyncio.sleep(2)

            # Check if process is still running
            if self.mcp_process.returncode is None:
                self.is_connected = True
                log.info("Z.AI MCP vision server started successfully")
                return True
            else:
                log.error(f"MCP server exited with code: {self.mcp_process.returncode}")
                return False

        except Exception as e:
            log.error(f"Failed to start Z.AI MCP server: {e}", exc_info=True)
            return False

    def _start_mcp_server_sync(self):
        """Start the MCP server synchronously"""
        try:
            # Set up environment variables for MCP server
            env = os.environ.copy()
            env['Z_AI_API_KEY'] = self.api_key
            env['Z_AI_MODE'] = self.mode

            # Start MCP server using npx
            cmd = [
                'npx', '-y', '@z_ai/mcp-server'
            ]

            log.info("Starting Z.AI MCP vision server...")
            log.info(f"Command: {' '.join(cmd)}")
            log.info(f"Environment variables: Z_AI_API_KEY={'*' * len(self.api_key)}, Z_AI_MODE={self.mode}")

            # Start the subprocess
            self.mcp_process = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=env,
                text=False  # Use bytes mode for proper MCP communication
            )

            # Give it a moment to start
            time.sleep(3)  # Increased startup time

            # Check if process is still running
            if self.mcp_process.returncode is None:
                self.is_connected = True
                log.info("Z.AI MCP vision server started successfully")
                log.info(f"MCP server PID: {self.mcp_process.pid}")
            else:
                log.error(f"MCP server exited with code: {self.mcp_process.returncode}")
                # Read stderr to see what went wrong
                if self.mcp_process.stderr:
                    stderr_output = self.mcp_process.stderr.read().decode()
                    log.error(f"MCP server stderr during startup: {stderr_output}")

        except Exception as e:
            log.error(f"Failed to start Z.AI MCP server synchronously: {e}", exc_info=True)

    def should_attempt_vision_analysis(self) -> bool:
        """
        Check if vision analysis should be attempted based on failure history and backoff timing

        Returns:
            True if vision analysis should be attempted, False if in backoff period
        """
        current_time = time.time()

        # If vision is temporarily disabled, check if backoff period has elapsed
        if self.vision_temporarily_disabled:
            if current_time - self.last_vision_failure_time >= self.vision_backoff_seconds:
                # Backoff period elapsed, re-enable vision with caution
                log.info(f"Vision backoff period elapsed ({self.vision_backoff_seconds}s). Re-enabling vision analysis.")
                self.vision_temporarily_disabled = False
                return True
            else:
                # Still in backoff period
                remaining_time = self.vision_backoff_seconds - (current_time - self.last_vision_failure_time)
                log.info(f"Vision analysis temporarily disabled. {remaining_time:.0f}s remaining in backoff period.")
                return False

        # If not disabled, allow attempt
        return True

    def handle_vision_failure(self, error_message: str) -> None:
        """
        Handle vision analysis failure by implementing exponential backoff

        Args:
            error_message: Description of the error that occurred
        """
        self.vision_failure_count += 1
        self.last_vision_failure_time = time.time()

        # Calculate exponential backoff: 60s, 120s, 240s, max 300s (5min)
        if self.vision_failure_count == 1:
            self.vision_backoff_seconds = 60
        else:
            # Double the backoff time, but cap at max
            self.vision_backoff_seconds = min(
                self.vision_backoff_seconds * 2,
                self.max_vision_backoff_seconds
            )

        # Disable vision temporarily
        self.vision_temporarily_disabled = True

        log.error(f"VISION FAILURE #{self.vision_failure_count}: {error_message}")
        log.error(f"Vision analysis temporarily disabled for {self.vision_backoff_seconds} seconds (exponential backoff)")
        log.error(f"This allows game state to continue updating while vision server recovers")

    def handle_vision_success(self) -> None:
        """
        Reset failure counters after successful vision analysis
        """
        if self.vision_failure_count > 0:
            log.info(f"Vision analysis succeeded after {self.vision_failure_count} previous failures. Resetting failure counters.")
            self.vision_failure_count = 0
            self.vision_backoff_seconds = 60  # Reset to initial backoff
            self.vision_temporarily_disabled = False
            self.last_vision_failure_time = 0

    def analyze_image_sync(self, image_path: str, prompt: str = "What does this image show?") -> Optional[str]:
        """
        Synchronous version of analyze_image for use in sync contexts with robust retry logic

        Args:
            image_path: Path to the image file
            prompt: Text prompt to accompany the image

        Returns:
            Analysis result as string, or None if failed and in backoff period
        """
        # CRITICAL: Check if we should attempt vision analysis based on failure history
        if not self.should_attempt_vision_analysis():
            # We're in a backoff period - return None to indicate vision unavailable
            # This allows the game to continue without vision analysis
            remaining_time = self.vision_backoff_seconds - (time.time() - self.last_vision_failure_time)
            log.warning(f"Vision analysis skipped - in backoff period ({remaining_time:.0f}s remaining)")
            return None

        # Attempt vision analysis with proper async handling
        try:
            # Check if we're already in an event loop
            try:
                loop = asyncio.get_running_loop()
                log.debug(f"Running in existing event loop, using ThreadPoolExecutor for vision analysis")
                # We're in an async context, use run_in_executor
                import concurrent.futures
                with concurrent.futures.ThreadPoolExecutor() as executor:
                    future = executor.submit(lambda: asyncio.run(self.analyze_image(image_path, prompt)))
                    result = future.result(timeout=self.timeout)
            except RuntimeError:
                log.debug(f"No existing event loop, using asyncio.run for vision analysis")
                # No running event loop, safe to use asyncio.run
                result = asyncio.run(self.analyze_image(image_path, prompt))

            if result is not None:
                # SUCCESS: Vision analysis completed successfully
                log.info(f"Vision analysis succeeded: {len(result)} characters returned")
                self.handle_vision_success()
                return result
            else:
                # FAILURE: Vision analysis returned None
                log.warning("Vision analysis returned None/empty result")
                self.handle_vision_failure("Vision analysis returned None/empty result")
                return None

        except concurrent.futures.TimeoutError:
            # FAILURE: Timeout during vision analysis
            error_msg = f"Vision analysis timeout after {self.timeout} seconds"
            log.error(error_msg)
            self.handle_vision_failure(error_msg)
            return None
        except Exception as e:
            # FAILURE: Exception occurred during vision analysis
            error_msg = f"Vision analysis exception: {str(e)}"
            log.error(f"Vision analysis failed with exception: {e}", exc_info=True)
            self.handle_vision_failure(error_msg)
            return None

    async def stop_mcp_server(self):
        """Stop the MCP server"""
        if self.mcp_process:
            try:
                self.mcp_process.terminate()
                await self.mcp_process.wait()
                log.info("Z.AI MCP vision server stopped")
            except Exception as e:
                log.warning(f"Error stopping MCP server: {e}")
            finally:
                self.mcp_process = None
                self.is_connected = False

    async def analyze_image(self, image_path: str, prompt: str = "What does this image show?") -> Optional[str]:
        """
        Analyze an image using the Z.AI MCP vision server

        Args:
            image_path: Path to the image file
            prompt: Text prompt to accompany the image

        Returns:
            Analysis result as string, or None if failed
        """
        if not self.is_connected:
            log.error("MCP server not connected")
            return None

        if not os.path.exists(image_path):
            log.error(f"Image file not found: {image_path}")
            return None

        try:
            # First, try to list available tools
            list_tools_request = {
                "jsonrpc": "2.0",
                "id": 1,
                "method": "tools/list",
                "params": {}
            }

            log.info(f"Requesting available tools: {json.dumps(list_tools_request, indent=2)}")

            # Send list tools request
            list_tools_json = json.dumps(list_tools_request) + '\n'
            self.mcp_process.stdin.write(list_tools_json.encode())
            self.mcp_process.stdin.flush()

            # Read tools list response
            import time
            import select

            if hasattr(select, 'select'):
                ready, _, _ = select.select([self.mcp_process.stdout], [], [], 10.0)
                if not ready:
                    log.error("Timeout waiting for tools list")
                    return None

            tools_response = self.mcp_process.stdout.readline()
            if tools_response:
                tools_data = json.loads(tools_response.decode())
                log.info(f"Available tools: {json.dumps(tools_data, indent=2)}")

                if 'result' in tools_data and 'tools' in tools_data['result']:
                    available_tools = tools_data['result']['tools']
                    log.info(f"Found {len(available_tools)} available tools")
                    for tool in available_tools:
                        log.info(f"Tool: {tool.get('name', 'unknown')} - {tool.get('description', 'no description')}")
            else:
                log.error("No response for tools list")

            # Use the correct tool name and parameters from the schema
            tool_name = "analyze_image"
            log.info(f"Using tool: {tool_name}")

            # Create MCP request for image analysis with correct schema
            mcp_request = {
                "jsonrpc": "2.0",
                "id": 2,
                "method": "tools/call",
                "params": {
                    "name": tool_name,
                    "arguments": {
                        "image_source": image_path,  # Use correct parameter name from schema
                        "prompt": prompt
                    }
                }
            }

            log.info(f"Sending MCP request: {json.dumps(mcp_request, indent=2)}")

            # Send request to MCP server
            request_json = json.dumps(mcp_request) + '\n'
            self.mcp_process.stdin.write(request_json.encode())
            self.mcp_process.stdin.flush()

            # Read response with timeout using sync approach since process was started with Popen
            try:
                log.info(f"Waiting for MCP server response for {tool_name}...")

                # Use select for timeout on subprocess stdout
                if hasattr(select, 'select'):
                    ready, _, _ = select.select([self.mcp_process.stdout], [], [], 30.0)
                    if not ready:
                        log.error(f"MCP server response timeout for {tool_name}")
                        return None

                response_line = self.mcp_process.stdout.readline()
                if not response_line:
                    log.error(f"No response from MCP server for {tool_name}")
                    # Check if server is still running
                    if self.mcp_process.poll() is not None:
                        log.error(f"MCP server process has terminated with code: {self.mcp_process.returncode}")
                        # Read stderr to see what went wrong
                        if self.mcp_process.stderr:
                            stderr_output = self.mcp_process.stderr.read().decode()
                            log.error(f"MCP server stderr: {stderr_output}")
                    return None

                log.info(f"Raw MCP response for {tool_name}: {response_line.decode().strip()}")
                response_data = json.loads(response_line.decode())
            except Exception as read_error:
                log.error(f"MCP server communication error for {tool_name}: {read_error}")
                return None

            if 'result' in response_data:
                result = response_data['result']
                # Handle different response formats
                if isinstance(result, dict):
                    # Check for MCP content format first
                    if 'content' in result and isinstance(result['content'], list) and len(result['content']) > 0:
                        content = result['content'][0]
                        if isinstance(content, dict) and 'text' in content:
                            analysis = content['text']
                            log.info(f"Successfully parsed MCP content format: {len(analysis)} chars")
                        else:
                            analysis = str(content)
                            log.warning(f"MCP content format unexpected, got: {type(content)}")
                    elif 'tools' in result:
                        # This is an INVALID response - MCP server returned tools list instead of analysis
                        log.error(f"MCP server returned tools list instead of analysis. This indicates a server error. Response: {result}")
                        return None
                    else:
                        # Fallback to other possible formats
                        analysis = result.get('description', result.get('analysis', str(result)))
                        log.info(f"Using fallback format for MCP response: {len(str(analysis))} chars")
                elif isinstance(result, str):
                    analysis = result
                else:
                    analysis = str(result)

                # Additional validation: ensure analysis is not just tool descriptions
                if analysis and isinstance(analysis, str):
                    # Check if the analysis contains tool-like content instead of actual image analysis
                    tool_keywords = ['analyze_image', 'analyze_video', 'inputSchema', 'maximum file size', 'supports both local files and remote URL']
                    if any(keyword.lower() in analysis.lower() for keyword in tool_keywords):
                        log.error(f"Analysis appears to contain tool descriptions instead of actual image analysis. Treating as invalid. Analysis preview: {analysis[:200]}...")
                        return None

                log.info(f"Successfully got analysis from {tool_name}")
                return analysis
            elif 'error' in response_data:
                log.error(f"MCP server error for {tool_name}: {response_data['error']}")
                return None
            else:
                log.error(f"Unexpected MCP response for {tool_name}: {response_data}")
                return None

        except Exception as e:
            log.error(f"Failed to analyze image: {e}", exc_info=True)
            return None

    async def __aenter__(self):
        """Async context manager entry"""
        await self.start_mcp_server()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        """Async context manager exit"""
        await self.stop_mcp_server()


def create_zai_vision_client(api_key: str) -> Optional[ZAIMCPClient]:
    """
    Create Z.AI MCP vision client

    Args:
        api_key: Z.AI API key

    Returns:
        ZAIMCPClient instance or None if failed
    """
    try:
        if not api_key:
            log.error("ZAI_API_KEY is required for MCP vision client")
            return None

        # Get timeout from feature config or use default
        try:
            from src.game.feature_config import DEFAULT_VISION_TIMEOUT
            timeout = DEFAULT_VISION_TIMEOUT
        except ImportError:
            timeout = 30  # Default fallback

        log.info(f"Creating Z.AI MCP vision client with timeout: {timeout}s")
        return ZAIMCPClient(api_key=api_key, timeout=timeout)
    except Exception as e:
        log.error(f"Failed to create ZAI MCP vision client: {e}", exc_info=True)
        return None