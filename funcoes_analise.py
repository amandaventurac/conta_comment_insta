import pandas as pd
import re
from bs4 import BeautifulSoup
from collections import Counter
import io
import matplotlib.pyplot as plt
from wordcloud import WordCloud

# =============================
# 🔹 CONFIGURAÇÕES INICIAIS
# =============================
NOMES_URL = "https://raw.githubusercontent.com/amandaventurac/conta_comment_insta/main/nomes.csv"
pattern_numero_w = r"\d{1,4}(?:w|d|h|sem)"

# =============================
# 🔹 FUNÇÕES AUXILIARES
# =============================
def detectar_mencoes(texto):
    return re.findall(r'@([A-Za-z0-9._]+)', texto) or []

def extract_username_and_text(node):
    username = None
    for a in node.find_all("a", href=True):
        href = a["href"].strip()
        if re.match(r"^/[A-Za-z0-9._]+/$", href) and not href.startswith(('/explore/', '/reel/', '/p/', '/stories/')):
            username = href.strip("/")
            break

    texts = [t.strip() for t in node.find_all(text=True) if t.strip()]
    full_text = " ".join(texts)
    full_text = re.sub(r'\s+', ' ', full_text).strip()
    if any(x in full_text.lower() for x in ['curtiu', 'respondeu', 'ver mais', 'like']):
        return None, None
    if username and full_text.lower().startswith(username.lower()):
        comment_text = full_text[len(username):].strip(" :\n\t")
    else:
        comment_text = full_text
    if username and comment_text:
        return username, comment_text
    return None, None

def encontrar_secao_comentarios(soup):
    for ul in soup.find_all('ul'):
        lis = ul.find_all('li')
        if len(lis) >= 3:
            perfis = sum(1 for li in lis if li.find('a', href=re.compile(r"^/[A-Za-z0-9._]+/$")))
            if perfis >= 3:
                return ul
    for div in soup.find_all('div'):
        lis = div.find_all('li')
        perfis = sum(1 for li in lis if li.find('a', href=re.compile(r"^/[A-Za-z0-9._]+/$")))
        if perfis >= 3:
            return div
    return soup

def coletar_todos_nos_comentarios(node):
    nos = [node]
    for child in node.find_all(['ul', 'div'], recursive=False):
        for li in child.find_all(['li', 'div'], recursive=False):
            nos.extend(coletar_todos_nos_comentarios(li))
    return nos

# =============================
# 🔹 LIMPEZA DE TEXTO
# =============================
def limpar_texto(text):
    text = re.sub(r"\bReply\b", "", text, flags=re.IGNORECASE)
    text = re.sub(r"\bVerified\b", "", text, flags=re.IGNORECASE)
    text = re.sub(pattern_numero_w, "", text)
    text = re.sub(r'\[\d+\s+curtid[as]* Responder Opções de comentários(?: Curtir)?\]', "", text)
    text = re.sub(r'\s+', ' ', text).strip()
    return text if text else None

def limpeza_final_robusta(text):
    if not text:
        return None
    if text.lower().startswith("ocultar respostas"):
        return None
    return limpar_texto(text)

def limpeza_final_robusta_2(text):
    if not text:
        return None
    if text.lower().endswith("Responder Opções de comentários"):
        return None
    return limpar_texto(text)

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
                text_limpo = limpeza_final_robusta(text)
                if not text_limpo:
                    continue
                mencoes = detectar_mencoes(text_limpo)
                mencoes_lower = [m.lower() for m in mencoes]
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

def processar_html(uploaded_html):
    logs = io.StringIO()
    logs.write("Iniciando processamento do HTML...\n")
    comentarios = contar_comentarios_html_instagram(uploaded_html)
    df = pd.DataFrame(comentarios)
    logs.write(f"Total de comentários extraídos (antes de limpeza final): {len(df)}\n")

    nomes_df = carregar_base_nomes()
    df['genero'] = df['username'].apply(lambda u: detectar_genero(u, nomes_df))

    # --- limpar e remover duplicatas ---
    df['text'] = df['text'].apply(limpeza_final_robusta)
    df['text'] = df['text'].apply(limpeza_final_robusta_2)
    df = df[df['text'].notna()]
    df = df.drop_duplicates(subset=['username', 'text'])

    logs.write(f"Total de comentários válidos após limpeza e deduplicação: {len(df)}\n")

    # --- contagem de palavras ---
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
# 🔹 SALVAR EM EXCEL
# =============================
def salvar_excel(df, caminho):
    df.to_excel(caminho, index=False, engine="openpyxl")

# =============================
# 🔹 VISUALIZAÇÕES
# =============================
def gerar_wordcloud(palavras_df):
    # 🔹 DEBUG: checar tipo e conteúdo
    print("Debug: tipo de palavras_df =", type(palavras_df))
    print("Debug: colunas disponíveis =", palavras_df.columns if hasattr(palavras_df, 'columns') else "N/A")
    print("Debug: primeiras linhas =", palavras_df.head() if hasattr(palavras_df, 'head') else "N/A")

    if palavras_df is None or palavras_df.empty:
        print("⚠️ DataFrame de palavras vazio. Não é possível gerar WordCloud.")
        return None
    if 'palavra' not in palavras_df.columns or 'frequencia' not in palavras_df.columns:
        print("⚠️ Colunas 'palavra' ou 'frequencia' não existem no DataFrame.")
        return None

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
