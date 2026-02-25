from __future__ import annotations

from collections import Counter
import json
import os
import time
import urllib.error
import urllib.request
from typing import Any

from reasoning_nlp.summarizer.prompt_builder import build_summary_prompt


_SYSTEM_PROMPT = (
    "Ban la tro ly tom tat video. "
    "Chi tra ve dung 1 JSON object hop le voi cac key: "
    "title, plot_summary, moral_lesson, evidence, quality_flags. "
    "Khong chen markdown, khong chen text ngoai JSON."
)


def _neutral_summary(
    context_blocks: list[dict[str, object]],
    run_seed: int,
    model_version: str,
    temperature: float,
    backend: str,
    retry_count: int,
    latency_ms: int,
    token_count: int,
    quality_flags: list[str] | None = None,
) -> dict[str, object]:
    flags = list(quality_flags or [])
    if not flags:
        flags = ["LLM_NEUTRAL_FALLBACK"]
    return {
        "schema_version": "1.1",
        "title": "Neutral Summary",
        "plot_summary": "Khong du du lieu de tao tom tat chi tiet.",
        "moral_lesson": "Hay dua tren bang chung ro rang truoc khi ket luan.",
        "evidence": _build_basic_evidence(context_blocks),
        "quality_flags": sorted(set(flags)),
        "generation_meta": {
            "model": model_version,
            "seed": run_seed,
            "temperature": temperature,
            "backend": backend,
            "retry_count": retry_count,
            "latency_ms": latency_ms,
            "token_count": token_count,
        },
    }


def _build_basic_evidence(context_blocks: list[dict[str, object]]) -> list[dict[str, object]]:
    timestamps = [str(x.get("timestamp", "")) for x in context_blocks if str(x.get("timestamp", ""))]
    if not timestamps:
        return []
    return [
        {
            "claim": "Tom tat dua tren cac moc canh/chu thich va hoi thoai da align.",
            "timestamps": sorted(set(timestamps))[:3],
        }
    ]


def _heuristic_summary(
    context_blocks: list[dict[str, object]],
    run_seed: int,
    model_version: str,
    temperature: float,
    backend: str,
    retry_count: int,
    latency_ms: int,
    token_count: int,
    extra_flags: list[str] | None = None,
) -> dict[str, object]:
    if not context_blocks:
        return _neutral_summary(
            context_blocks=context_blocks,
            run_seed=run_seed,
            model_version=model_version,
            temperature=temperature,
            backend=backend,
            retry_count=retry_count,
            latency_ms=latency_ms,
            token_count=token_count,
            quality_flags=["LLM_NEUTRAL_FALLBACK"],
        )

    timestamps = [str(x.get("timestamp", "")) for x in context_blocks if str(x.get("timestamp", ""))]
    dialogue_non_empty = [
        str(x.get("dialogue_text", "")).strip()
        for x in context_blocks
        if str(x.get("dialogue_text", "")).strip() and str(x.get("dialogue_text", "")).strip() != "(khong co)"
    ]
    image_non_empty = [
        str(x.get("image_text", "")).strip()
        for x in context_blocks
        if str(x.get("image_text", "")).strip() and str(x.get("image_text", "")).strip() != "(khong co)"
    ]

    sample_image = image_non_empty[0] if image_non_empty else "Khung hinh khong ro"
    sample_dialogue = dialogue_non_empty[0] if dialogue_non_empty else "(khong co)"

    fallback_counter = Counter(str(x.get("fallback_type", "")) for x in context_blocks)
    quality_flags: list[str] = []
    if fallback_counter.get("no_match", 0) > 0:
        quality_flags.append("ALIGN_HAS_NO_MATCH")
    quality_flags.extend(extra_flags or [])

    evidence = []
    if timestamps:
        evidence.append(
            {
                "claim": "Tom tat dua tren cac moc canh/chu thich va hoi thoai da align.",
                "timestamps": sorted(set(timestamps))[:3],
            }
        )

    return {
        "schema_version": "1.1",
        "title": "Video Summary",
        "plot_summary": (
            "Noi dung cho thay dien bien theo thu tu thoi gian voi hinh anh chinh la "
            f"'{sample_image}' va hoi thoai noi bat la '{sample_dialogue}'."
        ),
        "moral_lesson": "Thong diep duoc rut ra tu cac su kien da xuat hien trong video.",
        "evidence": evidence,
        "quality_flags": sorted(set(quality_flags)),
        "generation_meta": {
            "model": model_version,
            "seed": run_seed,
            "temperature": temperature,
            "backend": backend,
            "retry_count": retry_count,
            "latency_ms": latency_ms,
            "token_count": token_count,
        },
    }


def _api_chat_completion(
    *,
    prompt: str,
    model_name: str,
    timeout_ms: int,
    max_new_tokens: int,
    temperature: float,
    do_sample: bool,
) -> tuple[dict[str, Any], int, int]:
    base_url = os.getenv("OPENAI_BASE_URL", "").strip()
    api_key = os.getenv("OPENAI_API_KEY", "").strip()
    api_model = os.getenv("OPENAI_MODEL", "").strip() or model_name

    if not base_url or not api_key:
        raise RuntimeError("OPENAI_BASE_URL/OPENAI_API_KEY are required for api backend")

    url = f"{base_url.rstrip('/')}/chat/completions"
    payload = {
        "model": api_model,
        "messages": [
            {"role": "system", "content": _SYSTEM_PROMPT},
            {"role": "user", "content": prompt},
        ],
        "max_tokens": int(max_new_tokens),
        "temperature": float(temperature if do_sample else 0.0),
        "response_format": {"type": "json_object"},
    }
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        method="POST",
    )

    started = time.perf_counter()
    try:
        with urllib.request.urlopen(req, timeout=max(1, int(timeout_ms / 1000))) as resp:
            body = resp.read().decode("utf-8")
    except urllib.error.HTTPError as exc:
        msg = exc.read().decode("utf-8", errors="ignore")
        raise RuntimeError(f"api error {exc.code}: {msg}") from exc
    except Exception as exc:
        raise RuntimeError(f"api request failed: {exc}") from exc
    latency_ms = int((time.perf_counter() - started) * 1000)

    payload_out = json.loads(body)
    choices = payload_out.get("choices", [])
    if not isinstance(choices, list) or not choices:
        raise RuntimeError("api response missing choices")
    content = choices[0].get("message", {}).get("content", "")
    if not isinstance(content, str) or not content.strip():
        raise RuntimeError("api response missing message.content")
    usage = payload_out.get("usage", {})
    token_count = int(usage.get("total_tokens", 0)) if isinstance(usage, dict) else 0
    return _parse_json_payload(content), latency_ms, token_count


def _local_transformers_completion(
    *,
    prompt: str,
    model_name: str,
    timeout_ms: int,
    max_new_tokens: int,
    temperature: float,
    do_sample: bool,
) -> tuple[dict[str, Any], int, int]:
    del timeout_ms
    try:
        from transformers import AutoModelForCausalLM, AutoTokenizer, pipeline
    except Exception as exc:
        raise RuntimeError(f"transformers backend unavailable: {exc}") from exc

    started = time.perf_counter()
    tokenizer = AutoTokenizer.from_pretrained(model_name)
    model = AutoModelForCausalLM.from_pretrained(model_name)
    generator = pipeline("text-generation", model=model, tokenizer=tokenizer)
    prompt_text = (
        f"{_SYSTEM_PROMPT}\n\n"
        "Tra ve JSON: {\"title\":...,\"plot_summary\":...,\"moral_lesson\":...,\"evidence\":[],\"quality_flags\":[]}\n\n"
        f"CONTEXT:\n{prompt}"
    )
    out = generator(
        prompt_text,
        max_new_tokens=max(64, int(max_new_tokens)),
        do_sample=bool(do_sample),
        temperature=float(temperature),
        return_full_text=False,
    )
    latency_ms = int((time.perf_counter() - started) * 1000)
    if not isinstance(out, list) or not out:
        raise RuntimeError("local backend produced empty output")
    text = str(out[0].get("generated_text", "")).strip()
    if not text:
        raise RuntimeError("local backend produced blank text")
    token_count = len(tokenizer.encode(text)) if hasattr(tokenizer, "encode") else 0
    return _parse_json_payload(text), latency_ms, token_count


def _parse_json_payload(text: str) -> dict[str, Any]:
    try:
        payload = json.loads(text)
        if isinstance(payload, dict):
            return payload
    except Exception:
        pass

    start = text.find("{")
    end = text.rfind("}")
    if start >= 0 and end > start:
        maybe = text[start : end + 1]
        try:
            payload = json.loads(maybe)
            if isinstance(payload, dict):
                return payload
        except Exception:
            pass
    raise RuntimeError("response is not a valid JSON object")


def generate_internal_summary(
    context_blocks: list[dict[str, object]],
    run_seed: int,
    model_version: str,
    tokenizer_version: str,
    temperature: float = 0.1,
    backend: str = "api",
    fallback_backend: str = "local",
    timeout_ms: int = 30000,
    max_retries: int = 2,
    max_new_tokens: int = 512,
    do_sample: bool = False,
) -> dict[str, object]:
    del tokenizer_version
    if not context_blocks:
        return _neutral_summary(
            context_blocks=context_blocks,
            run_seed=run_seed,
            model_version=model_version,
            temperature=temperature,
            backend="neutral",
            retry_count=0,
            latency_ms=0,
            token_count=0,
        )

    prompt = build_summary_prompt(context_blocks)
    backends = [backend]
    if fallback_backend and fallback_backend not in backends:
        backends.append(fallback_backend)

    errors: list[str] = []
    for backend_name in backends:
        for attempt in range(max(0, int(max_retries)) + 1):
            try:
                if backend_name == "api":
                    payload, latency_ms, token_count = _api_chat_completion(
                        prompt=prompt,
                        model_name=model_version,
                        timeout_ms=timeout_ms,
                        max_new_tokens=max_new_tokens,
                        temperature=temperature,
                        do_sample=do_sample,
                    )
                elif backend_name == "local":
                    payload, latency_ms, token_count = _local_transformers_completion(
                        prompt=prompt,
                        model_name=model_version,
                        timeout_ms=timeout_ms,
                        max_new_tokens=max_new_tokens,
                        temperature=temperature,
                        do_sample=do_sample,
                    )
                else:
                    raise RuntimeError(f"unsupported backend: {backend_name}")

                out = dict(payload)
                out.setdefault("schema_version", "1.1")
                out.setdefault("quality_flags", [])
                if not isinstance(out["quality_flags"], list):
                    out["quality_flags"] = []
                out["quality_flags"] = sorted(set(list(out["quality_flags"])))
                out["generation_meta"] = {
                    "model": model_version,
                    "seed": run_seed,
                    "temperature": temperature,
                    "backend": backend_name,
                    "retry_count": attempt,
                    "latency_ms": latency_ms,
                    "token_count": token_count,
                }
                return out
            except Exception as exc:
                errors.append(f"{backend_name}:{exc}")

    return _heuristic_summary(
        context_blocks=context_blocks,
        run_seed=run_seed,
        model_version=model_version,
        temperature=temperature,
        backend="fallback",
        retry_count=max(0, int(max_retries)),
        latency_ms=0,
        token_count=0,
        extra_flags=["LLM_NEUTRAL_FALLBACK", "LLM_BACKEND_FAILED", *errors[:3]],
    )
