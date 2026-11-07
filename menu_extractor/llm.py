"""LLM access. Kept behind a tiny interface so the rest of the code (and the
tests) never depend on a specific provider."""

import os
import re
import time
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


MIN_SECONDS_BETWEEN_CALLS = 5.0  # keeps us under the free tier's requests-per-minute limit


class QuotaError(RuntimeError):
    """The Gemini free tier limit was hit (HTTP 429)."""


def make_client(api_key: str):
    """Gemini client without silent automatic retries: on a quota error we
    want to tell the user right away instead of hanging for minutes."""
    from google import genai
    from google.genai import types

    try:
        options = types.HttpOptions(retry_options=types.HttpRetryOptions(attempts=1))
        return genai.Client(api_key=api_key, http_options=options)
    except (AttributeError, TypeError, ValueError):
        return genai.Client(api_key=api_key)


class GeminiCaller:
    """Shared plumbing: picks the model, spaces out calls, translates errors."""

    def __init__(self, api_key: str | None = None, model: str | None = None):
        api_key = api_key or os.environ.get("GEMINI_API_KEY")
        if not api_key:
            raise RuntimeError("Defina a variável de ambiente GEMINI_API_KEY.")
        self._client = make_client(api_key)
        self.model = model or os.environ.get("GEMINI_MODEL") or pick_flash_model(available_models(self._client))
        self._last_call = 0.0
        self._low_thinking = True

    def _with_low_thinking(self, config):
        """Extraction and classification don't need long reasoning: asking for
        low thinking makes answers several times faster. Falls back silently on
        SDK versions or models that don't support it."""
        if config is None or not self._low_thinking:
            return config
        try:
            from google.genai import types

            return config.model_copy(update={"thinking_config": types.ThinkingConfig(thinking_level="low")})
        except Exception:
            self._low_thinking = False
            return config

    def _generate(self, contents, config):
        from google.genai import errors

        wait = MIN_SECONDS_BETWEEN_CALLS - (time.monotonic() - self._last_call)
        if wait > 0:
            time.sleep(wait)
        try:
            try:
                return self._client.models.generate_content(
                    model=self.model, contents=contents, config=self._with_low_thinking(config))
            except errors.ClientError as error:
                if error.code != 400 or not self._low_thinking or "think" not in str(error).lower():
                    raise
                self._low_thinking = False  # model rejects the option: retry without it
                return self._client.models.generate_content(model=self.model, contents=contents, config=config)
        except errors.ClientError as error:
            detail = str(error)[:400]
            if error.code == 429:
                raise QuotaError(
                    "Limite do plano gratuito do Gemini atingido. Espere alguns minutos "
                    f"(ou até o dia seguinte, se for o limite diário). Detalhe: {detail}"
                ) from error
            raise RuntimeError(f"Erro da API do Gemini ({error.code}): {detail}") from error
        finally:
            self._last_call = time.monotonic()


class MenuLLM(Protocol):
    def extract(self, image_png: bytes) -> LlmMenu: ...


class GeminiMenuLLM(GeminiCaller):
    """Multimodal extraction with Gemini + JSON schema (structured output)."""

    def extract(self, image_png: bytes) -> LlmMenu:
        from google.genai import types

        response = self._generate(
            contents=[types.Part.from_bytes(data=image_png, mime_type="image/png"), PROMPT],
            config=types.GenerateContentConfig(
                response_mime_type="application/json",
                response_schema=LlmMenu,
                temperature=0,
            ),
        )
        return LlmMenu.model_validate_json(response.text)
