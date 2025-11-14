import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
from wordcloud import WordCloud
from io import BytesIO
import re

# ============= CONFIGURAÇÃO INICIAL =============
st.set_page_config(page_title="Análise de Comentários", layout="wide")

# Importar funções adaptadas
from funcoes_analise import (
    processar_html,
    gerar_wordcloud,
    gerar_freq_palavras,
)

# ============= FUNÇÃO: LIMPEZA DE COMENTÁRIOS ============
def limpar_comentario(texto):
    if not texto or not isinstance(texto, str):
        return None
    texto = re.sub(r'\d+\s+curtida[s]?\s+Responder Opções de comentários\s+Curtir', '', texto, flags=re.IGNORECASE)
    texto = re.sub(r'Responder Opções de comentários\s+Curtir', '', texto, flags=re.IGNORECASE)
    texto = re.sub(r'^Ocultar respostas\s+', '', texto, flags=re.IGNORECASE)
    texto = re.sub(r'\s+', ' ', texto).strip()
    return texto if texto else None

# ============= FUNÇÃO: DEDUPLICAÇÃO ============
def deduplicar_comentarios(df):
    df_novo = pd.DataFrame(columns=df.columns)
    vistos = set()
    for _, row in df.iterrows():
        texto_limpo = limpar_comentario(row['text'])
        if texto_limpo:
            chave = (row['username'], texto_limpo)
            if chave not in vistos and not texto_limpo.lower().endswith("responder opções de comentários"):
                vistos.add(chave)
                nova_linha = row.copy()
                nova_linha['text'] = texto_limpo
                df_novo = pd.concat([df_novo, pd.DataFrame([nova_linha])], ignore_index=True)
    return df_novo

# ============= FUNÇÃO: GERAR XLS ============
def gerar_xls(df):
    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="dados")
    buffer.seek(0)
    return buffer

# ============= CABEÇALHO ============
st.title("💬 Sistema de Análise de Comentários do Instagram")
st.markdown("Este app possui **dois fluxos**: processamento inicial e análise final.")

# ============= SIDEBAR ============
fluxo = st.sidebar.radio(
    "Selecione o fluxo:",
    ["1️⃣ Processar HTML (gera XLS)", "2️⃣ Analisar XLS processados"],
)

# ============= FLUXO 1 ============
if fluxo.startswith("1️⃣"):
    st.header("📄 Fluxo 1 — Processar HTML")
    uploaded_html = st.file_uploader("Envie o arquivo HTML da página", type=["html", "htm"])

    if uploaded_html:
        st.info("⏳ Processando... isso pode levar alguns segundos.")
        comentarios_df, contagem_palavras_df, logs = processar_html(uploaded_html)
        st.success("✅ Processamento concluído!")

        # Logs
        with st.expander("Ver detalhes do processamento"):
            st.text(logs)

        # Limpeza e deduplicação
        comentarios_df = deduplicar_comentarios(comentarios_df)

        # Download XLS
        st.subheader("📊 Planilhas geradas")
        st.download_button(
            "📥 Baixar comentários (XLS)",
            data=gerar_xls(comentarios_df),
            file_name="comentarios_por_genero.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )
        st.download_button(
            "📥 Baixar contagem de palavras (XLS)",
            data=gerar_xls(contagem_palavras_df),
            file_name="contagem_palavras.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

        # Visualização
        st.subheader("Visualização prévia")
        st.write(f"Total de comentários únicos: {len(comentarios_df)}")
        st.dataframe(comentarios_df.head())

# ============= FLUXO 2 ============
else:
    st.header("📊 Fluxo 2 — Análise final dos XLS")
    comentarios_file = st.file_uploader("Envie o XLS de comentários", type=["xlsx"])
    palavras_file = st.file_uploader("Envie o XLS de contagem de palavras", type=["xlsx"])

    if comentarios_file and palavras_file:
        comentarios_df = pd.read_excel(comentarios_file)
        palavras_df = pd.read_excel(palavras_file)
        st.success("✅ Arquivos carregados com sucesso!")

        # Deduplicar novamente para garantir consistência
        comentarios_df = deduplicar_comentarios(comentarios_df)

        # Wordcloud baseada nos comentários limpos
        st.subheader("☁️ Nuvem de Palavras")
        texto_unico = " ".join(comentarios_df['text'].tolist())
        wc_fig = gerar_wordcloud(texto_unico)
        st.pyplot(wc_fig)

        # Frequência de palavras
        st.subheader("📈 Frequência de Palavras")
        freq_fig = gerar_freq_palavras(palavras_df)
        st.pyplot(freq_fig)

        # Contagem por gênero
        st.subheader("🚻 Contagem de Comentários por Gênero")
        genero_contagem = comentarios_df['genero'].value_counts()
        st.bar_chart(genero_contagem)

        # Resumo
        st.markdown("### 🧾 Resumo da Análise")
        st.write(f"Total de comentários únicos: {len(comentarios_df)}")
        st.write(f"Distribuição de gênero: {genero_contagem.to_dict()}")
