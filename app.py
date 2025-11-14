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
)

# ============= FUNÇÕES DE LIMPEZA =============
def limpeza_final_robusta(texto):
    if not texto or not isinstance(texto, str):
        return None
    # remove [n curtida(s) Responder Opções de comentários Curtir]
    texto = re.sub(r'\d+\s+curtida[s]?\s+Responder Opções de comentários\s+Curtir', '', texto, flags=re.IGNORECASE)
    texto = re.sub(r'Responder Opções de comentários\s+Curtir', '', texto, flags=re.IGNORECASE)
    # remove 'Ocultar respostas' no início
    texto = re.sub(r'^Ocultar respostas\s+', '', texto, flags=re.IGNORECASE)
    # limpa múltiplos espaços
    texto = re.sub(r'\s+', ' ', texto).strip()
    return texto if texto else None

# ============= FUNÇÕES NOVAS: GERAR XLS =============
def gerar_xls_comentarios(df):
    # Remove duplicatas antes de salvar
    df = df.drop_duplicates(subset=['username', 'text']).reset_index(drop=True)
    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl") as writer:
        df.to_excel(writer, index=False, sheet_name="dados")
    buffer.seek(0)
    return buffer

def gerar_xls_palavras(df):
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
        comentarios_df, contagem_palavras_df, logs = processar_html(uploaded_html)

        # ===== LIMPEZA FINAL =====
        comentarios_df['text'] = comentarios_df['text'].apply(limpeza_final_robusta)
        comentarios_df = comentarios_df[comentarios_df['text'].notna()]

        # ===== REMOVER DUPLICATAS =====
        comentarios_df = comentarios_df.drop_duplicates(subset=['username', 'text']).reset_index(drop=True)

        # ===== RECONSTRUIR CONTAGEM DE PALAVRAS =====
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
            data=gerar_xls_comentarios(comentarios_df),
            file_name="comentarios_por_genero.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

        st.download_button(
            "📥 Baixar contagem de palavras (XLS)",
            data=gerar_xls_palavras(contagem_palavras_df),
            file_name="contagem_palavras.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        )

        # ------- PRÉVIA -------
        st.write("Visualização prévia:")
        st.dataframe(comentarios_df.head())

        # ===== RESUMO CORRETO =====
        st.markdown("### 🧾 Resumo do Processamento")
        st.write(f"Total de comentários válidos e únicos: {len(comentarios_df)}")
        st.write(f"Total de palavras únicas: {contagem_palavras_df['palavra'].nunique()}")

# ============= FLUXO 2 =============
else:
    st.header("📊 Fluxo 2 — Análise final dos XLS")

    comentarios_file = st.file_uploader("Envie o XLS de comentários", type=["xlsx"])
    palavras_file = st.file_uploader("Envie o XLS de contagem de palavras", type=["xlsx"])

    if comentarios_file and palavras_file:
        comentarios_df = pd.read_excel(comentarios_file)
        palavras_df = pd.read_excel(palavras_file)

        # ===== LIMPEZA FINAL E REMOÇÃO DE DUPLICATAS =====
        comentarios_df['text'] = comentarios_df['text'].apply(limpeza_final_robusta)
        comentarios_df = comentarios_df[comentarios_df['text'].notna()]
        comentarios_df = comentarios_df.drop_duplicates(subset=['username', 'text']).reset_index(drop=True)

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
        st.write(f"Total de comentários válidos: {len(comentarios_df)}")
        st.write(f"Distribuição de gênero:\n{genero_contagem.to_dict()}")
        st.write(f"Total de palavras únicas: {palavras_df['palavra'].nunique()}")
