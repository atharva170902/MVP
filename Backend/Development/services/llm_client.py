"""
LLM provider abstraction (design §1)
====================================

Wraps both Bedrock model families (Claude text + a vision model) and ALWAYS
returns token usage. Owns the model-not-enabled handling so a disabled model
becomes a clean per-slot error (``ModelNotEnabledError``), never a job crash.

All boto3 clients are LAZILY constructed via ``_client()`` which calls
``load_backend_env()`` first, so this module imports OFFLINE and makes no network
call at import time.

Secrets are referenced by env-var name only and never logged.
"""

import json
import os
import time
from typing import Any, Dict, List, Optional, Tuple

from services.env_bootstrap import load_backend_env
from services.generation_output import diagram_s3_key, media_type_for

# --------------------------------------------------------------------------- #
# Configuration
# --------------------------------------------------------------------------- #
# Default TEXT model id MUST remain EXACTLY this string (incl. the global. prefix) — AC10.
BEDROCK_TEXT_MODEL_ID = os.environ.get(
    "BEDROCK_TEXT_MODEL_ID",
    "global.anthropic.claude-sonnet-4-5-20250929-v1:0",
)
# UNVERIFIED placeholder default — the exact Qwen-VL id / availability in ap-south-1 is
# not confirmed. Overridable via BEDROCK_VISION_MODEL_ID; a disabled model degrades to a
# clean per-slot ModelNotEnabledError (design finding 12).
BEDROCK_VISION_MODEL_ID = os.environ.get(
    "BEDROCK_VISION_MODEL_ID",
    "qwen.qwen3-vl-235b-a22b",
)
BEDROCK_REGION = os.environ.get("AWS_REGION", os.environ.get("AWS_DEFAULT_REGION", "ap-south-1"))
MAX_TOKENS = int(os.environ.get("BEDROCK_MAX_TOKENS", "4000"))
BEDROCK_MAX_RETRIES = int(os.environ.get("BEDROCK_MAX_RETRIES", "3"))
# Max images attached to one vision slot (FR6); extra images are dropped.
GEN_MAX_IMAGES_PER_SLOT = int(os.environ.get("GEN_MAX_IMAGES_PER_SLOT", "3"))

TokenUsage = Dict[str, int]  # {"input_tokens": int, "output_tokens": int, "total_tokens": int}

# {"bytes": bytes, "media_type": str}
ImageInput = Dict[str, Any]


# --------------------------------------------------------------------------- #
# Errors
# --------------------------------------------------------------------------- #
class ModelNotEnabledError(Exception):
    """Bedrock AccessDenied/Validation/ResourceNotFound for an unenabled or
    unavailable model id -> per-slot error."""

    def __init__(self, model_id: str, region: str):
        self.model_id, self.region = model_id, region
        super().__init__(f"model {model_id} not enabled in {region}")


class LLMInvocationError(Exception):
    """Any other Bedrock failure (throttling after retries, timeout, malformed
    body, image fetch failure) -> per-slot error."""


# --------------------------------------------------------------------------- #
# Lazy client
# --------------------------------------------------------------------------- #
_bedrock = None


def _client():
    """Lazily build the region-pinned bedrock-runtime client. Calls
    ``load_backend_env()`` first (idempotent) so creds/region are present before
    construction. Importing this module never triggers client creation."""
    global _bedrock
    if _bedrock is None:
        load_backend_env()
        import boto3
        _bedrock = boto3.client("bedrock-runtime", region_name=BEDROCK_REGION)
    return _bedrock


# --------------------------------------------------------------------------- #
# Token usage parsing (from the model's OWN usage block, NOT ResponseMetadata)
# --------------------------------------------------------------------------- #
def _zero_usage() -> TokenUsage:
    return {"input_tokens": 0, "output_tokens": 0, "total_tokens": 0}


def _usage_from_claude(payload: dict) -> TokenUsage:
    """Parse Anthropic Messages usage: payload['usage']['input_tokens'/'output_tokens'].
    Shared by generate_text and the Anthropic vision branch."""
    usage = (payload or {}).get("usage") or {}
    inp = int(usage.get("input_tokens", 0) or 0)
    out = int(usage.get("output_tokens", 0) or 0)
    return {"input_tokens": inp, "output_tokens": out, "total_tokens": inp + out}


def _usage_from_qwen(payload: dict) -> TokenUsage:
    """Parse the Qwen response's own usage block.

    UNVERIFIED: confirm the exact Qwen-VL Bedrock response schema for the chosen
    id. Bedrock Qwen responses typically expose a ``usage`` object; we parse the
    common field names defensively. If no usage data is present we return zeros
    (the caller sets a slot-level warning).
    """
    usage = (payload or {}).get("usage") or {}
    # Accept both Anthropic-style and OpenAI-style field names defensively.
    inp = int(usage.get("input_tokens", usage.get("prompt_tokens", 0)) or 0)
    out = int(usage.get("output_tokens", usage.get("completion_tokens", 0)) or 0)
    total = usage.get("total_tokens")
    total = int(total) if total is not None else inp + out
    return {"input_tokens": inp, "output_tokens": out, "total_tokens": total}


# --------------------------------------------------------------------------- #
# Request-body builders
# --------------------------------------------------------------------------- #
def _build_text_body(system: str, user: str, max_tokens: int, temperature: float) -> dict:
    return {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": max_tokens,
        "temperature": temperature,
        "system": system,
        "messages": [{"role": "user", "content": [{"type": "text", "text": user}]}],
    }


def _build_vision_body(
    model_id: str,
    system: str,
    user: str,
    images: List[ImageInput],
    *,
    max_tokens: int = MAX_TOKENS,
    temperature: float = 0.6,
) -> dict:
    """Build the vision request body, selecting the envelope by model-id family.

    Caps the attached images at GEN_MAX_IMAGES_PER_SLOT (FR6); extra images are
    dropped. Each image is preceded by a text label ``Image N:`` so the model can
    reference them, then the question instruction follows last.
    """
    import base64

    capped = list(images or [])[:GEN_MAX_IMAGES_PER_SLOT]
    mid = (model_id or "").lower()

    if mid.startswith("qwen."):
        # UNVERIFIED: confirm Qwen-VL Bedrock schema for <id> before relying on this.
        # Placeholder envelope modelled on an OpenAI-style multimodal message. The
        # exact image field (base64 vs byte array) and prompt field names must be
        # confirmed from Bedrock docs for the chosen Qwen id.
        content: List[Dict[str, Any]] = []
        for i, img in enumerate(capped, start=1):
            b64 = base64.b64encode(img["bytes"]).decode("ascii")
            content.append({"type": "text", "text": f"Image {i}:"})
            content.append(
                {
                    "type": "image_url",
                    "image_url": {"url": f"data:{img['media_type']};base64,{b64}"},
                }
            )
        content.append({"type": "text", "text": user})
        return {
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": content},
            ],
            "max_tokens": max_tokens,
            "temperature": temperature,
        }

    # VERIFIED Anthropic Messages multimodal envelope (default / anthropic.*).
    content = []
    for i, img in enumerate(capped, start=1):
        b64 = base64.b64encode(img["bytes"]).decode("ascii")
        content.append({"type": "text", "text": f"Image {i}:"})
        content.append(
            {
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": img["media_type"],
                    "data": b64,
                },
            }
        )
    content.append({"type": "text", "text": user})
    return {
        "anthropic_version": "bedrock-2023-05-31",
        "max_tokens": max_tokens,
        "temperature": temperature,
        "system": system,
        "messages": [{"role": "user", "content": content}],
    }


# --------------------------------------------------------------------------- #
# Output parsing
# --------------------------------------------------------------------------- #
def parse_model_json(text: str) -> Any:
    """Extract a JSON value out of model text: strips ``` code fences, then finds
    the first balanced JSON array/object. Raises LLMInvocationError on failure
    (caller turns this into a per-slot 'model returned unparseable output')."""
    if text is None:
        raise LLMInvocationError("model returned unparseable output")
    cleaned = text.strip()
    # Strip code fences (``` or ```json ... ```).
    if cleaned.startswith("```"):
        cleaned = cleaned.split("\n", 1)[-1] if "\n" in cleaned else cleaned
        if cleaned.endswith("```"):
            cleaned = cleaned[: -len("```")]
        # also remove a leading "json" tag left after fence removal
        cleaned = cleaned.strip()
    # Try a direct parse first.
    try:
        return json.loads(cleaned)
    except (ValueError, TypeError):
        pass
    # Fall back to the first [...] or {...} span.
    for opener, closer in (("[", "]"), ("{", "}")):
        start = cleaned.find(opener)
        end = cleaned.rfind(closer)
        if start != -1 and end != -1 and end > start:
            try:
                return json.loads(cleaned[start : end + 1])
            except (ValueError, TypeError):
                continue
    raise LLMInvocationError("model returned unparseable output")


# --------------------------------------------------------------------------- #
# Invocation + retry
# --------------------------------------------------------------------------- #
def _invoke_with_retry(model_id: str, body: dict) -> dict:
    """Invoke Bedrock with bounded exponential backoff on throttling. Maps a
    model-not-enabled ClientError to ModelNotEnabledError and any other failure to
    LLMInvocationError."""
    from botocore.exceptions import ClientError

    attempt = 0
    while True:
        try:
            resp = _client().invoke_model(
                modelId=model_id,
                contentType="application/json",
                accept="application/json",
                body=json.dumps(body),
            )
            return json.loads(resp["body"].read())
        except ClientError as e:
            code = e.response.get("Error", {}).get("Code", "")
            if code in ("ThrottlingException", "TooManyRequestsException"):
                attempt += 1
                if attempt > BEDROCK_MAX_RETRIES:
                    raise LLMInvocationError(f"throttled after {BEDROCK_MAX_RETRIES} retries") from e
                time.sleep(min(2 ** attempt * 0.5, 8.0))
                continue
            if code in ("AccessDeniedException", "ValidationException", "ResourceNotFoundException"):
                raise ModelNotEnabledError(model_id, BEDROCK_REGION) from e
            raise LLMInvocationError(str(code or e)) from e


# --------------------------------------------------------------------------- #
# Public functions
# --------------------------------------------------------------------------- #
def generate_text(
    *,
    system: str,
    user: str,
    max_tokens: int = MAX_TOKENS,
    temperature: float = 0.7,
    model_id: Optional[str] = None,
) -> Tuple[str, TokenUsage]:
    """Invoke Claude Sonnet 4.5 (Messages API). Returns (assistant_text, usage).
    Raises ModelNotEnabledError / LLMInvocationError."""
    mid = model_id or BEDROCK_TEXT_MODEL_ID
    body = _build_text_body(system, user, max_tokens, temperature)
    payload = _invoke_with_retry(mid, body)
    try:
        text = payload["content"][0]["text"]
    except (KeyError, IndexError, TypeError) as e:
        raise LLMInvocationError("model returned unparseable output") from e
    return text, _usage_from_claude(payload)


def generate_vision(
    *,
    system: str,
    user: str,
    images: List[ImageInput],
    max_tokens: int = MAX_TOKENS,
    temperature: float = 0.6,
    model_id: Optional[str] = None,
) -> Tuple[str, TokenUsage]:
    """Invoke the vision model with image bytes + text. Returns (text, usage).

    Raises ModelNotEnabledError / LLMInvocationError. Usage is parsed from the
    model's own usage block; when truly absent the usage is zero (the generation
    service attaches a slot-level warning).
    """
    mid = model_id or BEDROCK_VISION_MODEL_ID
    body = _build_vision_body(mid, system, user, images, max_tokens=max_tokens, temperature=temperature)
    payload = _invoke_with_retry(mid, body)
    low = mid.lower()

    if low.startswith("qwen."):
        # UNVERIFIED parse path — best-effort for the Qwen branch.
        text = _extract_qwen_text(payload)
        usage = _usage_from_qwen(payload)
    else:
        try:
            text = payload["content"][0]["text"]
        except (KeyError, IndexError, TypeError) as e:
            raise LLMInvocationError("model returned unparseable output") from e
        usage = _usage_from_claude(payload)
    return text, usage


def _extract_qwen_text(payload: dict) -> str:
    """Best-effort extraction of generated text from an (UNVERIFIED) Qwen response."""
    # Try common shapes defensively.
    if not isinstance(payload, dict):
        raise LLMInvocationError("model returned unparseable output")
    choices = payload.get("choices")
    if isinstance(choices, list) and choices:
        msg = choices[0].get("message") or {}
        content = msg.get("content")
        if isinstance(content, str):
            return content
    content = payload.get("content")
    if isinstance(content, list) and content and isinstance(content[0], dict):
        if "text" in content[0]:
            return content[0]["text"]
    if isinstance(payload.get("output_text"), str):
        return payload["output_text"]
    raise LLMInvocationError("model returned unparseable output")


# --------------------------------------------------------------------------- #
# Image fetching (FR6/AC11, finding 2 round 2)
# --------------------------------------------------------------------------- #
def fetch_image_bytes(
    image_ref: dict,
    *,
    grade: str,
    subject: str,
    slot_folder: Optional[str],
    candidate_folders: List[str],
    bucket: str,
    s3,
) -> ImageInput:
    """Resolve a draft ``images[]`` entry to raw bytes (FR6/AC11, finding-2 r2).

    Folder resolution order (the diagram's OWN folder is authoritative):
      1. image_ref.get("folder")   # stamped by the frontend (§8) — preferred
      2. slot_folder                # the slot's resolved chapter folder (fallback)
      3. each f in candidate_folders  # probe other selected-chapter folders on 404

    The entry carries only a filename in ``key``. The key is built via
    ``diagram_s3_key``; a get_object 404/NoSuchKey tries the next folder. Only if
    no folder resolves AND the (best-effort, often-expired) presigned ``url``
    fallback also fails does it raise ``LLMInvocationError``.
    """
    filename = image_ref.get("key")
    if not filename:
        raise LLMInvocationError("image entry has no filename")

    # Ordered, deduped folder list (preserve order, drop falsy).
    ordered: List[str] = []
    for f in [image_ref.get("folder"), slot_folder, *(candidate_folders or [])]:
        if f and f not in ordered:
            ordered.append(f)

    for folder in ordered:
        key = diagram_s3_key(grade, subject, folder, filename)
        try:
            resp = s3.get_object(Bucket=bucket, Key=key)
            return {"bytes": resp["Body"].read(), "media_type": media_type_for(filename)}
        except Exception as e:  # noqa: BLE001 - try next folder on any missing-key error
            code = _s3_error_code(e)
            if code in ("NoSuchKey", "404", "NoSuchBucket"):
                continue
            # Non-404 S3 error: stop probing folders and move to the URL fallback.
            break

    # Last-resort fallback: the stored (often-expired) presigned URL.
    url = image_ref.get("url")
    if url and isinstance(url, str) and url.lower().startswith(("http://", "https://")):
        try:
            import requests

            r = requests.get(url, timeout=10)
            r.raise_for_status()
            content_type = r.headers.get("Content-Type") or media_type_for(filename)
            return {"bytes": r.content, "media_type": content_type.split(";")[0].strip()}
        except Exception as e:  # noqa: BLE001
            raise LLMInvocationError(f"could not fetch image {filename}") from e

    raise LLMInvocationError(f"could not fetch image {filename}")


def _s3_error_code(exc: Exception) -> str:
    """Extract an S3/botocore error code from an exception, if any."""
    response = getattr(exc, "response", None)
    if isinstance(response, dict):
        return response.get("Error", {}).get("Code", "")
    return exc.__class__.__name__
