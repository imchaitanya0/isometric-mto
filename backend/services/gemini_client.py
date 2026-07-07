"""
Gemini Vision API client — two-pass extraction.

Pass A: Full drawing image → symbols, bboxes, drawing metadata
Pass B: Cropped BOM region  → structured BOM table rows

Both calls use structured JSON output to avoid parsing ambiguity.
Falls back gracefully when API key is missing.
"""
import concurrent.futures
import json
import logging
import re
from pathlib import Path

logger = logging.getLogger(__name__)

import google.generativeai as genai
from google.generativeai.types import GenerationConfig

from core.config import settings
from core.exceptions import MissingAPIKeyError, PipelineError

# Load prompts at import time
_PROMPT_DIR = Path(__file__).parent.parent / "prompts"
_PASS_A_PROMPT = (_PROMPT_DIR / "extraction_prompt.md").read_text(encoding="utf-8")
_PASS_B_PROMPT = (_PROMPT_DIR / "bom_prompt.md").read_text(encoding="utf-8")

MODEL_NAME = "gemini-3.1-flash-lite"


def _get_client() -> genai.GenerativeModel:
    """Initialise and return the Gemini model, raising if no key."""
    if not settings.has_api_key:
        raise MissingAPIKeyError()
    genai.configure(api_key=settings.gemini_api_key)
    return genai.GenerativeModel(MODEL_NAME)


GEMINI_TIMEOUT_SECONDS = 90  # Max time for one Gemini call


def _call_gemini(model: genai.GenerativeModel, prompt_text: str, image_bytes: bytes) -> str:
    """Helper to call Gemini and return raw text."""
    img = {
        "mime_type": "image/png",
        "data": image_bytes
    }
    
    try:
        response = model.generate_content(
            contents=[prompt_text, img],
            generation_config=genai.GenerationConfig(
                temperature=0.1,
                max_output_tokens=8192,
            ),
            request_options={"timeout": GEMINI_TIMEOUT_SECONDS},
        )
        
        if hasattr(response, 'text') and response.text:
            text_out = response.text
        elif response.candidates:
            parts = response.candidates[0].content.parts
            # Skip thinking parts (thought=True), return only text output parts
            text_parts = [
                p.text for p in parts
                if hasattr(p, 'text') and p.text and not getattr(p, 'thought', False)
            ]
            if text_parts:
                text_out = "\n".join(text_parts)
            else:
                # Fallback: all text parts
                all_parts = [p.text for p in parts if hasattr(p, 'text') and p.text]
                if all_parts:
                    text_out = "\n".join(all_parts)
                else:
                    finish = response.candidates[0].finish_reason if response.candidates else "unknown"
                    raise PipelineError(f"Gemini returned no text content. finish_reason={finish}")
        else:
            finish = response.candidates[0].finish_reason if response.candidates else "unknown"
            raise PipelineError(f"Gemini returned no text content. finish_reason={finish}")

        # Debug logging to file
        with open("/tmp/gemini_raw_out.log", "a") as f:
            f.write(f"\n--- NEW GEMINI CALL ({len(text_out)} chars) ---\n")
            f.write(text_out)
            f.write("\n------------------------\n")
            
        return text_out
        
    except Exception as e:
        err_str = str(e)
        if ("429" in err_str or "Quota exceeded" in err_str):
            logger.error(f"Gemini API rate limit hit: {err_str[:100]}")
            if "PerDay" in err_str:
                raise PipelineError("Free Tier Daily Quota Reached. The AI model has exhausted its 50 requests per day limit. Please try again tomorrow (resets at midnight PT).") from e
            else:
                raise PipelineError("Free Tier Quota Limit Reached (5 requests per minute). Please wait 1 minute for the quota to automatically reset and try again.") from e
        if ("504" in err_str or "503" in err_str or "Deadline Exceeded" in err_str):
            logger.error(f"Gemini API timeout hit: {err_str[:100]}")
            raise PipelineError("The AI model timed out due to heavy server load. This did NOT consume your quota. Please try again.") from e
        raise PipelineError(f"Gemini API call failed: {e}") from e


def _sanitize_gemini_json(text: str) -> str:
    """
    Repair common JSON encoding errors produced by Gemini.
    Simplest approach: look for known size fields and replace " with 'in' inside them.
    """
    # Fix 1: "size_nps": "6"" -> "size_nps": "6in"
    text = re.sub(r'("size_nps"|"nps"|"size")\s*:\s*"([^"]+)"', lambda m: f'{m.group(1)}: "{m.group(2).replace(chr(34), "in")}"', text)
    # Fix 2: Remove trailing commas before } or ]
    text = re.sub(r',\s*([}\]])', r'\1', text)
    return text


def _extract_json(raw: str) -> dict:
    """
    Extract JSON from a Gemini response.
    Handles: raw JSON, markdown fenced JSON, or leading/trailing whitespace.
    """
    if not raw or not raw.strip():
        return {}

    text = raw.strip()

    def try_parse(s: str) -> dict | None:
        try:
            return json.loads(s)
        except json.JSONDecodeError:
            try:
                return json.loads(_sanitize_gemini_json(s))
            except json.JSONDecodeError:
                return None

    # 1. Direct parse
    res = try_parse(text)
    if res is not None:
        return res

    # 2. Strip markdown fences
    if text.startswith("```"):
        lines = text.split("\n")
        inner_lines = lines[1:]
        if inner_lines and inner_lines[-1].strip() == "```":
            inner_lines = inner_lines[:-1]
        inner = "\n".join(inner_lines).strip()
        res = try_parse(inner)
        if res is not None:
            return res
        text = inner  # use inner for bracket search below

    # 3. Find the outermost { }
    start = text.find("{")
    if start != -1:
        depth = 0
        for i, ch in enumerate(text[start:], start=start):
            if ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    candidate = text[start : i + 1]
                    res = try_parse(candidate)
                    if res is not None:
                        return res
                    break

    # 4. Fallback instead of crashing the whole pipeline
    print(f"[WARNING] Could not parse Gemini JSON. Returning empty. Length: {len(raw)}")
    return {}


def pass_a_extract(full_image_bytes: bytes) -> dict:
    """
    Pass A: Send the full isometric drawing to Gemini.

    Returns a dict with:
        drawing_meta: dict
        items: list[dict]
        field_welds: int
    """
    model = _get_client()
    raw = _call_gemini(model, _PASS_A_PROMPT, full_image_bytes)
    result = _extract_json(raw)

    # Ensure required keys exist
    result.setdefault("drawing_meta", {})
    result.setdefault("items", [])
    result.setdefault("field_welds", 0)
    return result


def pass_b_extract(bom_image_bytes: bytes) -> dict:
    """
    Pass B: Send the cropped BOM region to Gemini.

    Returns a dict with:
        bom_rows: list[dict]
        drawing_no: str | None
        revision: str | None
        line_number: str | None
        confidence: float
    """
    model = _get_client()
    raw = _call_gemini(model, _PASS_B_PROMPT, bom_image_bytes)
    result = _extract_json(raw)

    result.setdefault("bom_rows", [])
    result.setdefault("confidence", 0.5)
    return result
