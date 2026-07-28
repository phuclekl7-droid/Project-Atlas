"""
Image Generation Plugin (Feature 52)

Generates images from text descriptions using external APIs.
Supports multiple backends:
  - Replicate API (SDXL, Flux, etc.)
  - Stability AI API (Stable Diffusion)

Requires at least one API key in settings or environment.

Usage:
    plugin = ImageGeneratorPlugin()
    result = plugin.execute("vẽ một con mèo đội mũ")
    result = plugin.execute("generate an image of a futuristic city")
"""

import base64
import io
import json
import os
import re
from typing import Optional
from urllib.parse import urlparse

from src.plugin import BasePlugin, PluginResult

# Try HTTP clients
_HAS_REQUESTS = False
_HAS_AIOHTTP = False

try:
    import requests
    _HAS_REQUESTS = True
except ImportError:
    requests = None  # type: ignore

try:
    import aiohttp
    _HAS_AIOHTTP = True
except ImportError:
    aiohttp = None  # type: ignore


# ── API Configuration ──

REPLICATE_API_URL = "https://api.replicate.com/v1/predictions"
STABILITY_API_URL = "https://api.stability.ai/v1/generation/stable-diffusion-xl-1024-v1-0/text-to-image"

# Default models by backend
DEFAULT_MODELS = {
    "replicate": "stability-ai/sdxl:39ed52f2a78e934b3ba6e2a89f5b1c712de7dfea535525255b1aa35c5565e08b",
    "stability": "stable-diffusion-xl-1024-v1-0",
}

# Negative prompt for quality
NEGATIVE_PROMPT = (
    "blurry, low quality, distorted, deformed, ugly, bad anatomy, "
    "bad proportions, extra limbs, extra fingers, watermark, text"
)


def _extract_prompt(user_input: str) -> Optional[str]:
    """Extract the image generation prompt from user input.

    Strips command prefixes like "vẽ", "generate", "/draw", etc.
    Returns the clean prompt or None if no prompt found.

    Args:
        user_input: Raw user input

    Returns:
        Clean prompt string, or None
    """
    text = user_input.strip()

    # Strip command prefixes (case-insensitive)
    prefixes = [
        r"^/draw\s+", r"^/imagine\s+", r"^/generate\s+", r"^/image\s+",
        r"^vẽ\s+", r"^vẽ cho tôi\s+", r"^hãy vẽ\s+",
        r"^generate\s+", r"^create an image of\s+", r"^create a\s+",
        r"^draw\s+", r"^make an image of\s+", r"^generate an image of\s+",
        r"^generate a picture of\s+",
    ]

    for prefix in prefixes:
        text = re.sub(prefix, "", text, count=1, flags=re.IGNORECASE)

    text = text.strip().strip(".,!?")

    if len(text) < 3:
        return None

    return text


def _generate_replicate(prompt: str, api_key: str, model: str = None) -> Optional[dict]:
    """Generate image using Replicate API.

    Args:
        prompt: Text prompt for image generation
        api_key: Replicate API token
        model: Model string (default: SDXL)

    Returns:
        Dict with image_url, or None on failure
    """
    if not _HAS_REQUESTS:
        return None

    model = model or DEFAULT_MODELS["replicate"]

    try:
        # Start prediction
        response = requests.post(
            REPLICATE_API_URL,
            headers={
                "Authorization": f"Token {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "version": model.split(":")[1] if ":" in model else model,
                "input": {
                    "prompt": prompt,
                    "negative_prompt": NEGATIVE_PROMPT,
                    "width": 1024,
                    "height": 1024,
                    "num_outputs": 1,
                    "scheduler": "DPMSolverMultistep",
                    "num_inference_steps": 30,
                    "guidance_scale": 7.5,
                },
            },
            timeout=30,
        )

        if response.status_code != 201 and response.status_code != 200:
            return {"error": f"API error: {response.status_code} - {response.text[:200]}"}

        data = response.json()
        prediction_id = data.get("id")

        if not prediction_id:
            return {"error": "No prediction ID returned"}

        # Poll for completion
        max_polls = 30
        poll_interval = 2  # seconds
        import time

        for _ in range(max_polls):
            time.sleep(poll_interval)

            poll_resp = requests.get(
                f"{REPLICATE_API_URL}/{prediction_id}",
                headers={"Authorization": f"Token {api_key}"},
                timeout=15,
            )

            if poll_resp.status_code != 200:
                continue

            poll_data = poll_resp.json()
            status = poll_data.get("status", "")

            if status == "succeeded":
                output = poll_data.get("output")
                if isinstance(output, list) and len(output) > 0:
                    return {"image_url": output[0]}
                elif isinstance(output, str):
                    return {"image_url": output}
                else:
                    return {"error": "No output from model"}
            elif status == "failed":
                return {"error": f"Generation failed: {poll_data.get('error', 'Unknown error')}"}
            elif status == "canceled":
                return {"error": "Generation was canceled"}

        return {"error": "Timeout waiting for image generation"}

    except requests.exceptions.RequestException as e:
        return {"error": f"Network error: {e}"}
    except Exception as e:
        return {"error": str(e)}


def _generate_stability(prompt: str, api_key: str) -> Optional[dict]:
    """Generate image using Stability AI API.

    Args:
        prompt: Text prompt
        api_key: Stability AI API key

    Returns:
        Dict with image_url (base64), or None on failure
    """
    if not _HAS_REQUESTS:
        return None

    try:
        response = requests.post(
            STABILITY_API_URL,
            headers={
                "Authorization": f"Bearer {api_key}",
                "Content-Type": "application/json",
                "Accept": "application/json",
            },
            json={
                "text_prompts": [
                    {"text": prompt, "weight": 1.0},
                    {"text": NEGATIVE_PROMPT, "weight": -1.0},
                ],
                "cfg_scale": 7,
                "height": 1024,
                "width": 1024,
                "samples": 1,
                "steps": 30,
            },
            timeout=60,
        )

        if response.status_code != 200:
            return {"error": f"Stability API error: {response.status_code}"}

        data = response.json()
        artifacts = data.get("artifacts", [])

        if not artifacts:
            return {"error": "No image generated"}

        # Return base64-encoded image
        img_data = artifacts[0].get("base64", "")
        return {"image_base64": img_data}

    except Exception as e:
        return {"error": str(e)}


class ImageGeneratorPlugin(BasePlugin):
    """Plugin that generates images from text descriptions."""

    def __init__(
        self,
        replicate_api_key: Optional[str] = None,
        stability_api_key: Optional[str] = None,
        default_backend: str = "replicate",
    ):
        """Initialize with API keys.

        Args:
            replicate_api_key: Replicate API token
            stability_api_key: Stability AI API key
            default_backend: Which backend to try first ("replicate" or "stability")
        """
        self._replicate_key = replicate_api_key or os.environ.get("REPLICATE_API_TOKEN", "")
        self._stability_key = stability_api_key or os.environ.get("STABILITY_API_KEY", "")
        self._default_backend = default_backend
        self._has_http = _HAS_REQUESTS

    @property
    def name(self) -> str:
        return "image_generator"

    @property
    def description(self) -> str:
        if self._replicate_key or self._stability_key:
            return "Tạo ảnh từ mô tả văn bản (SDXL / Flux via API)"
        return "Tạo ảnh từ mô tả văn bản (cần cấu hình API key: REPLICATE_API_TOKEN hoặc STABILITY_API_KEY)"

    @property
    def available(self) -> bool:
        """Whether this plugin can generate images."""
        return self._has_http and bool(self._replicate_key or self._stability_key)

    def execute(self, user_input: str) -> PluginResult:
        """Generate an image from a text description.

        Args:
            user_input: Text description of the image to generate

        Returns:
            PluginResult with image URL or base64 data
        """
        if not user_input or not user_input.strip():
            return PluginResult(success=False, output="", plugin_name=self.name)

        # Check if this looks like an image generation request
        gen_keywords = [
            "vẽ", "generate", "draw", "create image", "tạo ảnh",
            "/draw", "/imagine", "/generate", "make an image",
            "tạo hình", "picture of",
        ]
        is_gen_request = any(kw in user_input.lower() for kw in gen_keywords)

        if not is_gen_request:
            return PluginResult(success=False, output="", plugin_name=self.name)

        # Extract prompt
        prompt = _extract_prompt(user_input)
        if not prompt or len(prompt) < 3:
            return PluginResult(
                success=False,
                output=(
                    "Vui lòng mô tả ảnh bạn muốn tạo.\n\n"
                    "Ví dụ:\n"
                    "- `vẽ một con mèo đội mũ cao bồi`\n"
                    "- `/draw futuristic city at sunset`"
                ),
                plugin_name=self.name,
            )

        if not self._has_http:
            return PluginResult(
                success=False,
                output="⚠️ Thiếu thư viện `requests`. Chạy: `pip install requests`",
                plugin_name=self.name,
            )

        if not self._replicate_key and not self._stability_key:
            return PluginResult(
                success=False,
                output=(
                    "⚠️ **Chưa cấu hình API key**\n\n"
                    "Cần ít nhất một trong các biến môi trường:\n"
                    "- `REPLICATE_API_TOKEN` (khuyên dùng)\n"
                    "- `STABILITY_API_KEY`\n\n"
                    "Đăng ký tại:\n"
                    "- https://replicate.com/account/api-tokens\n"
                    "- https://platform.stability.ai/account/keys"
                ),
                plugin_name=self.name,
            )

        # Try backends in configured order
        result_dict = None
        backend_used = None

        # Determine backend order
        backends = []
        if self._default_backend == "replicate" and self._replicate_key:
            backends.append(("replicate", self._replicate_key))
        if self._stability_key:
            backends.append(("stability", self._stability_key))
        if self._default_backend != "replicate" and self._replicate_key:
            backends.append(("replicate", self._replicate_key))

        for backend_name, api_key in backends:
            if backend_name == "replicate":
                result_dict = _generate_replicate(prompt, api_key)
            elif backend_name == "stability":
                result_dict = _generate_stability(prompt, api_key)

            if result_dict:
                if "error" not in result_dict:
                    backend_used = backend_name
                    break
                # Only log first error, continue to next backend
                if backend_name == backends[0][0]:
                    continue

        if result_dict is None:
            return PluginResult(
                success=False,
                output="❌ Không thể kết nối tới dịch vụ tạo ảnh. Kiểm tra kết nối internet.",
                plugin_name=self.name,
            )

        if "error" in result_dict:
            return PluginResult(
                success=False,
                output=f"❌ Lỗi tạo ảnh: {result_dict['error']}",
                plugin_name=self.name,
            )

        # Format output
        image_url = result_dict.get("image_url", "")
        image_b64 = result_dict.get("image_base64", "")

        if image_url:
            output = (
                f"🎨 **Ảnh đã tạo**\n"
                f"> Prompt: *{prompt}* | Backend: {backend_used}\n\n"
                f"![Generated Image]({image_url})\n\n"
                f"[🔗 Mở ảnh gốc]({image_url})"
            )
        elif image_b64:
            # Display as data URI
            output = (
                f"🎨 **Ảnh đã tạo**\n"
                f"> Prompt: *{prompt}* | Backend: {backend_used}\n\n"
                f"![Generated Image](data:image/png;base64,{image_b64})"
            )
        else:
            output = "✅ Ảnh đã được tạo nhưng không có đường dẫn hiển thị."

        return PluginResult(
            success=True,
            output=output,
            plugin_name=self.name,
            data={
                "prompt": prompt,
                "backend": backend_used,
                "image_url": image_url,
            },
        )
