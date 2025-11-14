import pandas as pd
import re
from bs4 import BeautifulSoup
from collections import Counter
import matplotlib.pyplot as plt
from wordcloud import WordCloud
import io
import requests

# =============================
# 🔹 CONFIGURAÇÕES INICIAIS
# =============================

NOMES_URL = "https://raw.githubusercontent.com/amandaventurac/conta_comment_insta/main/nomes.csv"

# aceita: 10w, 3d, 12h, 2sem
pattern_numero_w = r"\d{1,4}(?:w|d|h|sem)"

# =============================
# 🔹 FUNÇÕES AUXILIARES DE PARSE HTML
# =============================

def detectar_mencoes(texto):
    """Detecta menções no texto do comentário."""
    mencoes = re.findall(r'@([A-Za-z0-9._]+)', texto)
    return mencoes if mencoes else []


def extract_username_and_text(node):
    """Extrai username e texto de um bloco que parece comentário (não curtida)."""
    username = None

    # detecta o username pelo primeiro <a href="/perfil/">
    for a in node.find_all("a", href=True):
        href = a["href"].strip()
        if re.match(r"^/[A-Za-z0-9._]+/$", href) and not href.startswith(('/explore/', '/reel/', '/p/', '/stories/')):
            username = href.strip("/")
            break

    # junta todos os textos
    texts = []
    for t in node.find_all(text=True):
        clean = t.strip()
        if clean:
            texts.append(clean)

    full_text = " ".join(texts)
    full_text = re.sub(r'\s+', ' ', full_text).strip()

    # ignorar ruídos
    if any(x in full_text.lower() for x in ['curtiu', 'respondeu', 'ver mais', 'like']):
        return None, None

    # remove repetição do username no começo
    if username and full_text.lower().startswith(username.lower()):
        comment_text = full_text[len(username):].strip(" :\n\t")
    else:
        comment_text = full_text

    if username and comment_text:
        return username, comment_text

    return None, None


def encontrar_secao_comentarios(soup):
    """Encontra a seção principal de comentários."""
    # tenta primeiro <ul> estruturado
    for ul in soup.find_all('ul'):
        lis = ul.find_all('li')
        if len(lis) >= 3:
            perfis = sum(1 for li in lis if li.find('a', href=re.compile(r"^/[A-Za-z0-9._]+/$")))
            if perfis >= 3:
                return ul

    # tenta <div>
    for div in soup.find_all('div'):
        lis = div.find_all('li')
        perfis = sum(1 for li in lis if li.find('a', href=re.compile(r"^/[A-Za-z0-9._]+/$")))
        if perfis >= 3:
            return div

    # fallback
    return soup


def coletar_todos_nos_comentarios(node):
    """Recursivamente coleta comentários e replies."""
    nos = [node]
    for child in node.find_all(['ul', 'div'], recursive=False):
        for li in child.find_all(['li', 'div'], recursive=False):
            nos.extend(coletar_todos_nos_comentarios(li))
    return nos

# =============================
# 🔹 LIMPEZA DE TEXTO
# =============================

def limpar_texto(text):
    """Remove Reply, Verified e padrões de número+w."""
    text = re.sub(r"\bReply\b", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\bVerified\b", "", text, flags=re.IGNORECASE)
    text = re.sub(pattern_numero_w, "", text)
    # Remove múltiplos espaços
    return re.sub(r'\s+', ' ', text).strip()

# =============================
# 🔹 LIMPEZA FINAL (ANTES DO XLS)
# =============================

def limpeza_final(text):
    """
    Remove padrões residuais do Instagram antes de exportar:
    - '[n curtida(s) Responder Opções de comentários Curtir]'
    """
    # Regex robusta para remover o padrão inteiro
    text = re.sub(
        r"\[?\s*\d+\s+curtidas?\s+Responder\s+Opções\s+de\s+comentários\s+Curtir\s*\]?",
        "",
        text,
        flags=re.IGNORECASE
    )
    # Remove múltiplos espaços e quebras de linha
    text = re.sub(r'\s+', ' ', text).strip()
    return text

# =============================
# 🔹 DETECÇÃO DE GÊNERO
# =============================

def carregar_base_nomes():
    try:
        nomes_df = pd.read_csv(NOMES_URL)
        nomes_df['name'] = nomes_df['name'].str.upper()
        return nomes_df
    except Exception as e:
        print(f"⚠️ Erro ao carregar base de nomes: {e}")
        return pd.DataFrame(columns=['name', 'classification'])


def detectar_genero(username, nomes_df):
    """Detecta o gênero a partir do username, comparando com a base de nomes."""
    if pd.isna(username) or not isinstance(username, str):
        return 'unknown'

    first_name = username.split('.')[0].split('_')[0].upper()
    match = nomes_df[nomes_df['name'] == first_name]

    if not match.empty:
        c = match['classification'].iloc[0]
        return 'female' if c == 'F' else 'male'

    return 'unknown'


# =============================
# 🔹 FUNÇÃO PRINCIPAL
# =============================

def contar_comentarios_html_instagram(uploaded_html):
    """Extrai comentários de um arquivo HTML do Instagram."""
    html = uploaded_html.read().decode('utf-8')
    soup = BeautifulSoup(html, 'html.parser')

    secao = encontrar_secao_comentarios(soup)

    possiveis_comentarios = []
    for li in secao.find_all(['li', 'div']):
        if li.find('a', href=True):
            hrefs = [a['href'] for a in li.find_all('a', href=True)]
            if any(re.match(r"^/[A-Za-z0-9._]+/$", h) for h in hrefs):
                possiveis_comentarios.append(li)

    comentarios = []
    vistos = set()

    for node in possiveis_comentarios:
        todos = coletar_todos_nos_comentarios(node)
        for n in todos:

            username, text = extract_username_and_text(n)
            if username and text:

                text_limpo = limpar_texto(text)
                if not text_limpo:
                    continue

                mencoes = detectar_mencoes(text_limpo)
                mencoes_lower = [m.lower() for m in mencoes]

                # 🚫 Ignorar comentários onde o usuário menciona ele mesmo
                if username.lower() in mencoes_lower:
                    continue

                chave = (username.lower(), text_limpo.lower())
                if chave not in vistos:
                    vistos.add(chave)
                    comentarios.append({
                        'username': username,
                        'text': text_limpo,
                        'mentions': ', '.join(mencoes)
                    })

    return comentarios


# =============================
# 🔹 PIPELINE GERAL (STREAMLIT)
# =============================

def processar_html(uploaded_html):
    logs = io.StringIO()
    logs.write("Iniciando processamento do HTML...\n")

    comentarios = contar_comentarios_html_instagram(uploaded_html)
    df = pd.DataFrame(comentarios)
    logs.write(f"Total de comentários extraídos: {len(df)}\n")

    nomes_df = carregar_base_nomes()
    df['genero'] = df['username'].apply(lambda u: detectar_genero(u, nomes_df))
    logs.write("Gênero detectado para cada usuário.\n")

    # Aplicar limpeza final para remover padrões residuais do Instagram
    df['text'] = df['text'].apply(limpeza_final)

    # Contagem de palavras
    palavras = []
    for t in df['text']:
        palavras.extend(re.findall(r'\b[a-zA-ZÀ-ÿ]{3,}\b', t.lower()))

    contagem = Counter(palavras)
    freq_df = pd.DataFrame(contagem.items(), columns=['palavra', 'frequencia']).sort_values(
        by='frequencia', ascending=False
    )

    logs.write(f"Total de palavras únicas: {len(freq_df)}\n")
    logs.write("Processamento concluído com sucesso.\n")

    return df, freq_df, logs.getvalue()


# =============================
# 🔹 SALVAR EM EXCEL (robusto)
# =============================

def salvar_excel(df, caminho):
    """
    Salva DataFrame em XLSX com openpyxl.
    → Não quebra acentos
    → Excel abre direto
    → Sem texto para colunas
    """
    df.to_excel(caminho, index=False, engine="openpyxl")


# =============================
# 🔹 VISUALIZAÇÕES
# =============================

def gerar_wordcloud(palavras_df):
    freq_dict = dict(zip(palavras_df['palavra'], palavras_df['frequencia']))
    wc = WordCloud(width=800, height=400, background_color="white").generate_from_frequencies(freq_dict)

    fig, ax = plt.subplots(figsize=(10, 5))
    ax.imshow(wc, interpolation="bilinear")
    ax.axis("off")
    return fig


def gerar_freq_palavras(palavras_df, top_n=20):
    top = palavras_df.head(top_n)
    fig, ax = plt.subplots(figsize=(8, 5))
    ax.barh(top['palavra'][::-1], top['frequencia'][::-1])
    ax.set_xlabel("Frequência")
    ax.set_ylabel("Palavra")
    ax.set_title("Palavras mais frequentes")
    plt.tight_layout()
    return fig
