"""Data models.

Two layers on purpose:
- `Llm*` models are what the LLM must return. Prices stay as raw text
  ("R$ 12,90") because LLMs are unreliable at number formatting; we parse
  them ourselves, deterministically.
- `Menu` / `MenuItem` are the clean, validated output of the pipeline.
"""

from pydantic import BaseModel, Field


class LlmVariation(BaseModel):
    name: str = Field(description="Nome da variação, ex.: 'Broto', 'Grande', '500 ml'")
    price_text: str | None = Field(description="Preço exatamente como impresso, ou null")


class LlmItem(BaseModel):
    name: str = Field(description="Nome do prato/produto como impresso")
    description: str | None = Field(description="Descrição/ingredientes, ou null")
    category: str = Field(description="Seção do cardápio onde o item aparece")
    price_text: str | None = Field(description="Preço único exatamente como impresso, ou null se só houver variações")
    variations: list[LlmVariation] = Field(description="Tamanhos/opções com preço próprio; lista vazia se não houver")


class LlmMenu(BaseModel):
    restaurant_name: str | None = Field(description="Nome do restaurante, se aparecer")
    items: list[LlmItem]


class Variation(BaseModel):
    name: str
    price: float | None


class MenuItem(BaseModel):
    name: str
    description: str | None = None
    category: str
    price: float | None = None
    variations: list[Variation] = []
    warnings: list[str] = []


class Menu(BaseModel):
    restaurant_name: str | None = None
    items: list[MenuItem] = []
    warnings: list[str] = []

    def to_rows(self) -> list[dict]:
        """Flatten to one row per sellable option (handy for tables/CSV)."""
        rows = []
        for item in self.items:
            if item.variations:
                for variation in item.variations:
                    rows.append(self._row(item, f"{item.name} ({variation.name})", variation.price))
            else:
                rows.append(self._row(item, item.name, item.price))
        return rows

    @staticmethod
    def _row(item: MenuItem, name: str, price: float | None) -> dict:
        return {
            "categoria": item.category,
            "item": name,
            "preco": price,
            "descricao": item.description or "",
            "alertas": "; ".join(item.warnings),
        }
