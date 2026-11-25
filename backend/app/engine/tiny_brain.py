"""Tiny always-on decision brain via llama.cpp (faster small local model for quick calls)."""

import os
from pathlib import Path

MODEL_PATH = Path(
    os.environ.get(
        "TINY_BRAIN_MODEL",
        str(Path.home() / ".llama" / "qwen2.5-1.5b-instruct-q4_k_m.gguf"),
    )
)
_llm = None

SYSTEM_PROMPT = (
    "You are a fast local decision assistant. "
    "Answer briefly and directly. Never repeat the question or the instructions."
)


def _get_llm():
    global _llm
    try:
        from llama_cpp import Llama
    except ImportError as exc:
        raise RuntimeError("llama_cpp is missing: pip install llama-cpp-python") from exc
    if _llm is None:
        if not MODEL_PATH.exists():
            raise RuntimeError(
                f"Tiny brain model not found at {MODEL_PATH}. "
                "Set TINY_BRAIN_MODEL to a GGUF chat model or download one there."
            )
        layers = int(os.environ.get("LLAMA_GPU_LAYERS", "99"))
        try:
            _llm = Llama(
                model_path=str(MODEL_PATH),
                n_ctx=2048,
                n_gpu_layers=layers,
                chat_format="chatml",
                verbose=False,
            )
        except Exception:
            _llm = Llama(
                model_path=str(MODEL_PATH),
                n_ctx=2048,
                n_gpu_layers=0,
                chat_format="chatml",
                verbose=False,
            )
    return _llm


def _clean(text: str) -> str:
    for token in ("<|im_end|>", "<|im_start|>", "</s>", "[INST]", "[/INST]"):
        text = text.replace(token, "")
    return " ".join(text.split()).strip()


def tiny_brain(prompt: str) -> str:
    llm = _get_llm()
    try:
        out = llm.create_chat_completion(
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": prompt},
            ],
            max_tokens=128,
            temperature=0.1,
            repeat_penalty=1.15,
            stop=["<|im_end|>", "<|endoftext|>", "</s>"],
        )
        text = _clean(str(out["choices"][0]["message"]["content"]))
    except Exception:
        raw = (
            f"<|im_start|>system\n{SYSTEM_PROMPT}<|im_end|>\n"
            f"<|im_start|>user\n{prompt}<|im_end|>\n"
            "<|im_start|>assistant\n"
        )
        out = llm(
            raw,
            max_tokens=128,
            temperature=0.1,
            repeat_penalty=1.15,
            stop=["<|im_end|>", "</s>", "<|im_start|>"],
            echo=False,
        )
        text = _clean(str(out["choices"][0]["text"]))
    return text or "(tiny brain returned no answer)"
