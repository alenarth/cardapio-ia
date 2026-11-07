"""LLM access. Kept behind a tiny interface so the rest of the code (and the
tests) never depend on a specific provider."""

import os
import re
from typing import Protocol

from .schema import LlmMenu

PROMPT = """Você é um sistema de cadastro de cardápios para um app de delivery.
Extraia TODOS os itens vendáveis da imagem do cardápio.

Regras:
- Copie nomes e preços exatamente como impressos. Não invente nem arredonde.
- `category` é o título da seção onde o item aparece (ex.: "Pizzas", "Bebidas").
  Se não houver seções, use o tipo do item.
- Se o item tiver tamanhos/opções com preços diferentes, preencha `variations`
  e deixe `price_text` como null.
- Se um preço não estiver legível ou não existir, use null. Nunca chute.
- Ignore textos que não são itens: endereço, telefone, horário, slogans.
"""


_SKIP = ("lite", "image", "tts", "audio", "live", "embedding", "thinking", "exp", "latest", "computer")


def pick_flash_model(model_names: list[str]) -> str:
    """Choose the newest Gemini Flash model from the ones this API key can use.

    Model names change every few months, so instead of hard-coding one we
    look at what the API offers. Stable versions win over previews.
    """
    def version(name: str) -> tuple[int, ...]:
        return tuple(int(n) for n in re.findall(r"\d+", name.split("flash")[0]))

    names = [n.removeprefix("models/") for n in model_names]
    flash = [n for n in names if n.startswith("gemini-") and "flash" in n and not any(s in n for s in _SKIP)]
    stable = [n for n in flash if "preview" not in n]
    candidates = stable or flash
    if not candidates:
        raise RuntimeError("Nenhum modelo Gemini Flash disponível para esta chave de API.")
    return max(candidates, key=lambda n: (version(n), -len(n)))


def available_models(client) -> list[str]:
    return [m.name for m in client.models.list() if "generateContent" in (getattr(m, "supported_actions", None) or [])]


class MenuLLM(Protocol):
    def extract(self, image_png: bytes) -> LlmMenu: ...


class GeminiMenuLLM:
    """Multimodal extraction with Gemini + JSON schema (structured output)."""

    def __init__(self, api_key: str | None = None, model: str | None = None):
        from google import genai  # imported lazily so tests don't need it

        api_key = api_key or os.environ.get("GEMINI_API_KEY")
        if not api_key:
            raise RuntimeError("Defina a variável de ambiente GEMINI_API_KEY.")
        self._client = genai.Client(api_key=api_key)
        self.model = model or os.environ.get("GEMINI_MODEL") or pick_flash_model(available_models(self._client))

    def extract(self, image_png: bytes) -> LlmMenu:
        from google.genai import types

        response = self._client.models.generate_content(
            model=self.model,
            contents=[types.Part.from_bytes(data=image_png, mime_type="image/png"), PROMPT],
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=LlmMenu,
                temperature=0,
            ),
        )
        return LlmMenu.model_validate_json(response.text)
