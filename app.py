import streamlit as st
import pandas as pd
import matplotlib.pyplot as plt
from wordcloud import WordCloud
from io import BytesIO
import re
from collections import Counter

# ============= CONFIGURAÇÃO INICIAL =============
st.set_page_config(page_title="Análise de Comentários", layout="wide")

# Importar suas funções do notebook adaptadas
from funcoes_analise import (
    processar_html,        # gera dfs
    gerar_wordcloud,
    gerar_freq_palavras,
    limpeza_final_robusta, # função de limpeza final robusta
)

# ============= FUNÇÃO NOVA: GERAR XLS =============
def gerar_xls(df):
    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="dados")
    buffer.seek(0)
    return buffer

# ============= CABEÇALHO =============
st.title("💬 Sistema de Análise de Comentários do Instagram")
st.markdown("Este app possui **dois fluxos**: processamento inicial e análise final.")

# ============= SIDEBAR =============
fluxo = st.sidebar.radio(
    "Selecione o fluxo:",
    ["1️⃣ Processar HTML (gera XLS)", "2️⃣ Analisar XLS processados"],
)

# ============= FLUXO 1 =============
if fluxo.startswith("1️⃣"):
    st.header("📄 Fluxo 1 — Processar HTML")

    uploaded_html = st.file_uploader("Envie o arquivo HTML da página", type=["html", "htm"])

    if uploaded_html:
        st.info("⏳ Processando... isso pode levar alguns segundos.")

        # Chamada da função principal que gera os DataFrames
        comentarios_df, _, logs = processar_html(uploaded_html)

        # ===== APLICAR LIMPEZA FINAL ROBUSTA E REMOVER DUPLICATAS =====
        comentarios_df['text'] = comentarios_df['text'].apply(limpeza_final_robusta)
        comentarios_df = comentarios_df[comentarios_df['text'].notna()]
        comentarios_df = comentarios_df.drop_duplicates(subset=['username', 'text'])

        # ===== RECONTAR PALAVRAS APENAS DOS COMENTÁRIOS VÁLIDOS =====
        palavras = []
        for t in comentarios_df['text']:
            palavras.extend(re.findall(r'\b[a-zA-ZÀ-ÿ]{3,}\b', t.lower()))
        contagem = Counter(palavras)
        contagem_palavras_df = pd.DataFrame(contagem.items(), columns=['palavra', 'frequencia']).sort_values(
            by='frequencia', ascending=False
        )

        st.success("✅ Processamento concluído!")

        # ------- LOGS -------
        with st.expander("Ver detalhes do processamento"):
            st.text(logs)

        # ------- DOWNLOADS EM XLS -------
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

        # ------- PRÉVIA -------
        st.write("Visualização prévia:")
        st.dataframe(comentarios_df.head())

        # ===== ATUALIZAR NÚMERO DE COMENTÁRIOS E PALAVRAS =====
        st.markdown("### 🧾 Resumo do Processamento")
        st.write(f"Total de comentários válidos após limpeza: {len(comentarios_df)}")
        st.write(f"Total de palavras únicas: {contagem_palavras_df['palavra'].nunique()}")

# ============= FLUXO 2 =============
else:
    st.header("📊 Fluxo 2 — Análise final dos XLS")

    comentarios_file = st.file_uploader("Envie o XLS de comentários", type=["xlsx"])
    palavras_file = st.file_uploader("Envie o XLS de contagem de palavras", type=["xlsx"])

    if comentarios_file and palavras_file:
        comentarios_df = pd.read_excel(comentarios_file)
        palavras_df = pd.read_excel(palavras_file)

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

        # --- Resumo ---
        st.markdown("### 🧾 Resumo da Análise")
        st.write(f"Total de comentários: {len(comentarios_df)}")
        st.write(f"Distribuição de gênero:\n{genero_contagem.to_dict()}")
        st.write(f"Total de palavras únicas: {palavras_df['palavra'].nunique()}")
