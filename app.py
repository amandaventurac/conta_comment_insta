import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
from wordcloud import WordCloud
import io
import base64

# ============= CONFIGURAÇÃO INICIAL =============
st.set_page_config(page_title="Análise de Comentários", layout="wide")

# Importar suas funções do notebook adaptadas
from funcoes_analise import (
    processar_html,   # gera dfs
    gerar_wordcloud,
    gerar_freq_palavras,
)

# ============= CABEÇALHO =============
st.title("💬 Sistema de Análise de Comentários do Instagram")
st.markdown("Este app possui **dois fluxos**: processamento inicial e análise final.")

# ============= SIDEBAR =============
fluxo = st.sidebar.radio(
    "Selecione o fluxo:",
    ["1️⃣ Processar HTML (gera CSVs)", "2️⃣ Analisar CSVs processados"],
)

# ============= FLUXO 1 =============
if fluxo.startswith("1️⃣"):
    st.header("📄 Fluxo 1 — Processar HTML")

    uploaded_html = st.file_uploader("Envie o arquivo HTML da página", type=["html", "htm"])

    if uploaded_html:
        st.info("⏳ Processando... isso pode levar alguns segundos.")

        # Chamada da sua função principal que gera os DataFrames
        comentarios_df, contagem_palavras_df, logs = processar_html(uploaded_html)

        st.success("✅ Processamento concluído!")

        # Mostrar logs e resumo
        with st.expander("Ver detalhes do processamento"):
            st.text(logs)

        # Oferecer os CSVs para download
        def baixar_csv(df, filename):
            csv = df.to_csv(index=False)
            b64 = base64.b64encode(csv.encode()).decode()
            href = f'<a href="data:file/csv;base64,{b64}" download="{filename}">📥 Baixar {filename}</a>'
            st.markdown(href, unsafe_allow_html=True)

        st.subheader("📊 Planilhas geradas")
        baixar_csv(comentarios_df, "comentarios_por_genero.csv")
        baixar_csv(contagem_palavras_df, "contagem_palavras.csv")

        st.write("Visualização prévia:")
        st.dataframe(comentarios_df.head())

# ============= FLUXO 2 =============
else:
    st.header("📊 Fluxo 2 — Análise final dos CSVs")

    comentarios_file = st.file_uploader("Envie o CSV de comentários", type=["csv"])
    palavras_file = st.file_uploader("Envie o CSV de contagem de palavras", type=["csv"])

    if comentarios_file and palavras_file:
        comentarios_df = pd.read_csv(comentarios_file)
        palavras_df = pd.read_csv(palavras_file)

        st.success("✅ Arquivos carregados com sucesso!")

        # --- Wordcloud ---
        st.subheader("☁️ Nuvem de Palavras")
        fig_wc = gerar_wordcloud(palavras_df)
        st.pyplot(fig_wc)

        # --- Frequência ---
        st.subheader("📈 Frequência de Palavras")
        fig_freq = gerar_freq_palavras(palavras_df)
        st.pyplot(fig_freq)

        # --- Contagem por gênero ---
        st.subheader("🚻 Contagem de Comentários por Gênero")
        genero_contagem = comentarios_df['genero'].value_counts()
        st.bar_chart(genero_contagem)

        # --- Logs / resumo ---
        st.markdown("### 🧾 Resumo da Análise")
        st.write(f"Total de comentários: {len(comentarios_df)}")
        st.write(f"Distribuição de gênero:\n{genero_contagem.to_dict()}")
