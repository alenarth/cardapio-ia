"""Streamlit web app: upload menu photos or a PDF, get structured data back."""

import json
import tempfile
from pathlib import Path

import pandas as pd
import streamlit as st

from menu_extractor.evaluation import Scores, score_menu
from menu_extractor.llm import GeminiMenuLLM
from menu_extractor.pipeline import extract_menu
from menu_extractor.schema import Menu

SYNTHETIC = Path("data/synthetic")

st.set_page_config(page_title="Cardápio IA", page_icon="🍕", layout="wide")


@st.cache_resource
def get_llm() -> GeminiMenuLLM:
    return GeminiMenuLLM()


@st.cache_resource
def ensure_synthetic_data() -> list[Path]:
    """The test set is generated from a fixed seed, so it is identical everywhere."""
    if not list(SYNTHETIC.glob("menu_*.json")):
        from scripts.generate_synthetic import generate

        generate(n=15, out=SYNTHETIC, seed=42)
    return sorted(SYNTHETIC.glob("menu_*.jpg"))


def show_menu(result) -> None:
    menu = result.menu
    st.subheader(menu.restaurant_name or "Restaurante não identificado")
    flagged = sum(1 for item in menu.items if item.warnings)
    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Itens", len(menu.items))
    c2.metric("Para revisar", flagged)
    c3.metric("Páginas", result.pages)
    c4.metric("Tempo", f"{result.seconds:.1f}s")
    for warning in menu.warnings:
        st.warning(warning)

    rows = pd.DataFrame(menu.to_rows())
    st.dataframe(rows, hide_index=True, column_config={
        "preco": st.column_config.NumberColumn("preço", format="R$ %.2f"),
    })
    d1, d2 = st.columns(2)
    d1.download_button("Baixar JSON", json.dumps(menu.model_dump(), ensure_ascii=False, indent=2),
                       "cardapio.json", "application/json")
    d2.download_button("Baixar CSV", rows.to_csv(index=False).encode("utf-8-sig"), "cardapio.csv", "text/csv")
    with st.expander("JSON completo"):
        st.json(menu.model_dump())


def run_extraction(paths: list[Path]) -> None:
    try:
        with st.spinner("Lendo o cardápio com IA..."):
            llm = get_llm()
            result = extract_menu(paths, llm)
    except RuntimeError as error:
        st.error(str(error))
        return
    show_menu(result)
    st.caption(f"Modelo: {llm.model}")


def run_evaluation(examples: list[Path]) -> None:
    try:
        llm = get_llm()
    except RuntimeError as error:
        st.error(str(error))
        return
    total = Scores(0, 0, 0, 0, 0)
    rows, bar = [], st.progress(0.0, text="Avaliando...")
    for i, image in enumerate(examples, start=1):
        truth = Menu.model_validate(json.loads(image.with_suffix(".json").read_text(encoding="utf-8")))
        try:
            result = extract_menu([image], llm)
        except RuntimeError as error:
            st.warning(f"Avaliação interrompida no cardápio {i}: {error}")
            break
        scores = score_menu(result.menu, truth)
        total += scores
        rows.append({"cardápio": image.name, "itens reais": scores.true_items, "F1": scores.f1,
                     "preço correto": scores.price_accuracy, "categoria correta": scores.category_accuracy,
                     "segundos": result.seconds})
        bar.progress(i / len(examples), text=f"Avaliando {i}/{len(examples)}...")
    bar.empty()
    if not rows:
        return
    df = pd.DataFrame(rows)
    st.markdown(
        "| Métrica | Valor |\n|---|---|\n"
        f"| Modelo | {llm.model} |\n"
        f"| Cardápios | {len(rows)} |\n"
        f"| Itens no gabarito | {total.true_items} |\n"
        f"| Precisão | {total.precision:.1%} |\n"
        f"| Recall | {total.recall:.1%} |\n"
        f"| F1 | {total.f1:.1%} |\n"
        f"| Preço correto | {total.price_accuracy:.1%} |\n"
        f"| Categoria correta | {total.category_accuracy:.1%} |\n"
        f"| Tempo médio por cardápio | {df['segundos'].mean():.1f}s |"
    )
    st.dataframe(df, hide_index=True)


st.title("🍕 Cardápio IA")
st.write(
    "Transforma **foto ou PDF de cardápio** em dados estruturados (itens, preços, categorias e tamanhos), "
    "prontos para cadastro em app de delivery. Itens com preço ausente ou suspeito são sinalizados para revisão."
)

examples = ensure_synthetic_data()
upload_tab, example_tab, eval_tab = st.tabs(["Enviar cardápio", "Exemplos", "Avaliação"])

with upload_tab:
    files = st.file_uploader("Fotos ou PDF do cardápio", type=["jpg", "jpeg", "png", "webp", "pdf"],
                             accept_multiple_files=True)
    if files and st.button("Extrair cardápio", type="primary"):
        folder = Path(tempfile.mkdtemp())
        paths = []
        for f in files:
            path = folder / f.name
            path.write_bytes(f.getvalue())
            paths.append(path)
        run_extraction(paths)

with example_tab:
    st.caption("Cardápios sintéticos (restaurantes fictícios) gerados pelo projeto, com gabarito conhecido.")
    choice = st.selectbox("Exemplo", examples, format_func=lambda p: p.stem)
    left, right = st.columns([2, 3])
    left.image(str(choice))
    with right:
        if st.button("Extrair este exemplo", type="primary"):
            run_extraction([choice])

with eval_tab:
    st.write(
        f"Roda o extrator nos {len(examples)} cardápios sintéticos e compara com o gabarito: "
        "**precisão** (itens extraídos que existem), **recall** (itens reais encontrados), "
        "acerto de **preço** e de **categoria**."
    )
    if st.button("Rodar avaliação"):
        run_evaluation(examples)
