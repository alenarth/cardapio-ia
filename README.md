# Cardápio IA

Transforma **foto ou PDF de cardápio** em **dados estruturados** (itens, preços, categorias e tamanhos), prontos para cadastro em um app de delivery, usando um LLM multimodal com saída em JSON validada.

**Demo:** [cardapio-ia.streamlit.app](https://cardapio-ia.streamlit.app)

![tests](https://github.com/alenarth/cardapio-ia/actions/workflows/tests.yml/badge.svg)

## O problema

Cadastrar o cardápio de um restaurante novo num app de delivery costuma ser digitação manual: dezenas de itens, preços em formatos diferentes, pizzas com três tamanhos, fotos tortas tiradas com celular. É lento e cheio de erro de digitação.

Este projeto automatiza a primeira versão do cadastro e **deixa claro o que precisa de revisão humana**, em vez de fingir que o modelo nunca erra.

## Como funciona

```
fotos / PDF ──► páginas PNG ──► LLM multimodal ──► JSON (schema) ──► pós-processamento ──► cardápio validado
               (rotação EXIF,    (Gemini, saída      (Pydantic)        (preços, categorias,    + alertas
                redimensiona)     estruturada)                          duplicados, alertas)
```

1. **Entrada:** várias fotos ou um PDF de várias páginas. Cada página vira um PNG corrigido (rotação do celular) e redimensionado.
2. **Extração:** o LLM recebe a imagem e um **schema JSON** (definido em Pydantic) e devolve só dados nesse formato.
3. **Pós-processamento determinístico:** converte preços, padroniza categorias, junta páginas, remove duplicados e gera **alertas** (preço ausente, preço fora da faixa esperada).
4. **Saída:** tabela na tela + download em JSON e CSV.
5. **Avaliação:** a aba *Avaliação* da própria demo roda o extrator no conjunto de teste e mostra as métricas.

## Decisões técnicas

- **O LLM devolve o preço como texto, e o código converte.** LLMs erram formatação de número com frequência (`1.299,00` vs `1299.00`). Pedir o texto exato e converter com uma função testada (`prices.py`) deixa essa parte 100% previsível.
- **Saída estruturada com schema**, em vez de pedir "um JSON" no prompt: elimina respostas fora do formato e quebra de parse.
- **Alertas em vez de confiança cega:** item sem preço ou com preço suspeito aparece sinalizado para revisão. Num fluxo real, isso define o que vai para um humano.
- **Provedor de LLM atrás de uma interface (`MenuLLM`):** trocar Gemini por outro modelo é mudar uma classe. Os testes usam um LLM falso e rodam sem chave nem internet.
- **Avaliação com gabarito:** sem métrica não dá pra saber se uma mudança no prompt melhorou ou piorou.
- **Resiliência a falhas da API:** o modelo é escolhido automaticamente entre os Gemini Flash disponíveis para a chave (os nomes mudam a cada poucos meses). Se o modelo estiver sobrecarregado (erro 5xx), travar (timeout de 90 s) ou estourar a cota (429), o app tenta de novo e passa para o próximo modelo, em vez de travar a tela. Durante o desenvolvimento isso aconteceu de verdade: o modelo mais novo estava respondendo "alta demanda".

## Avaliação

Para medir a qualidade, o projeto tem um conjunto de **cardápios sintéticos** gerados com gabarito exato (`scripts/generate_synthetic.py`, semente fixa: o mesmo conjunto é gerado em qualquer máquina): 5 tipos de restaurante, 1 ou 2 colunas, fontes diferentes, 5 formatos de preço, pizzas e açaí com tamanhos, e efeito de foto de celular (rotação, desfoque, ruído).

A aba **Avaliação** da demo (ou o script `scripts/evaluate.py`) compara a extração com o gabarito:

- **Precisão:** dos itens extraídos, quantos existem de verdade (mede invenção de itens).
- **Recall:** dos itens reais, quantos foram encontrados.
- **Preço correto** e **categoria correta** nos itens encontrados.

| Métrica | Resultado |
|---|---|
| Modelo | gemini-3.6-flash |
| Cardápios avaliados | 8 (128 itens no gabarito) |
| Precisão | 100% |
| Recall | 100% |
| F1 | 100% |
| Preço correto | 100% |
| Categoria correta | 100% |
| Tempo médio por cardápio | 9,5 s |

Rodado em 07/11/2026 pela aba **Avaliação** da demo. A rodada parou no 9º cardápio porque bateu o limite diário do plano gratuito do Gemini.

**Leitura honesta do resultado:** os cardápios sintéticos são limpos e bem diagramados, então 100% aqui mostra que o pipeline funciona de ponta a ponta, não que ele acerta 100% em fotos reais. O próximo passo é medir num conjunto de fotos reais rotuladas à mão.

> Para reproduzir: `python -m scripts.generate_synthetic` e depois `python -m scripts.evaluate --data data/synthetic`.

Cardápios sintéticos são mais limpos que fotos reais. Para uma medida honesta do mundo real, coloque fotos em `data/real/` com o gabarito revisado à mão (`foto.jpg` + `foto.json` no mesmo formato do download da app).

## Como rodar

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate    |    Linux/Mac: source .venv/bin/activate
pip install -r requirements-dev.txt

# chave gratuita em https://aistudio.google.com/apikey
# Windows (PowerShell): $env:GEMINI_API_KEY="sua_chave"
# Linux/Mac:            export GEMINI_API_KEY="sua_chave"

streamlit run app.py                             # abre a interface no navegador
python -m scripts.generate_synthetic             # gera os 15 cardápios de teste
python -m scripts.evaluate --data data/synthetic # roda a avaliação
pytest -q                                        # testes (não precisam de chave)
```

## Estrutura

```
app.py                        interface Streamlit (extração, exemplos e avaliação)
menu_extractor/
  schema.py                   modelos Pydantic (saída do LLM e saída final)
  llm.py                      prompt + cliente Gemini com saída estruturada
  pipeline.py                 arquivos → páginas PNG → LLM → cardápio
  prices.py                   conversão determinística de preços em reais
  postprocess.py              normalização, junção de páginas, alertas
  evaluation.py               métricas contra gabarito
scripts/
  generate_synthetic.py       gera cardápios sintéticos com gabarito
  evaluate.py                 roda a avaliação e imprime a tabela
tests/                        testes com LLM falso (rodam no GitHub Actions)
```

## Limitações e próximos passos

- Cardápios com foto de prato ocupando a página toda ou escrita à mão ainda não foram avaliados.
- Comparar modelos (custo × qualidade × tempo) usando o mesmo script de avaliação.
- Detectar adicionais e combos ("+ R$ 3,00 bacon") como estrutura própria.
- Montar um conjunto de cardápios reais rotulados para medir o desempenho fora do sintético.

---

Feito por [Arthur Alen](https://linkedin.com/in/arthuralen) · Licença MIT
