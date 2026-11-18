import os
import sys
import io
import time

# Garante importação correta independente do diretório de execução
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import pandas as pd
import streamlit as st
from datetime import datetime
from scraper import raspar_google_maps

# Configuração da Página
st.set_page_config(
    page_title="LeadHunter - Extrator de Leads & WhatsApp",
    page_icon="⚡",
    layout="wide",
    initial_sidebar_state="expanded"
)

# Estilização CSS Moderna
st.markdown("""
<style>
    .main-title {
        font-size: 2.2rem;
        font-weight: 800;
        background: linear-gradient(90deg, #25D366, #128C7E, #00B4D8);
        -webkit-background-clip: text;
        -webkit-text-fill-color: transparent;
        margin-bottom: 0.2rem;
    }
    .sub-title {
        color: #888888;
        font-size: 1.05rem;
        margin-bottom: 1.5rem;
    }
    .metric-card {
        background-color: #1e1e24;
        border: 1px solid #2e2e38;
        border-radius: 10px;
        padding: 15px;
        text-align: center;
    }
    .zap-btn-style {
        background-color: #25D366;
        color: white;
        padding: 6px 12px;
        border-radius: 6px;
        text-decoration: none;
        font-weight: bold;
    }
    div[data-testid="stMetricValue"] {
        font-size: 1.8rem;
    }
</style>
""", unsafe_allow_html=True)

# Diretório para salvar históricos
HISTORICO_DIR = os.path.join(os.path.dirname(__file__), "historico")
os.makedirs(HISTORICO_DIR, exist_ok=True)

# Inicializa sessão se não existir
if "leads_data" not in st.session_state:
    st.session_state["leads_data"] = []
if "termo_atual" not in st.session_state:
    st.session_state["termo_atual"] = ""

# Sidebar: Configuração da Busca
with st.sidebar:
    st.markdown("### 🎯 Parâmetros da Prospecção")
    
    nicho = st.text_input(
        "Nicho / Ramo de Atuação",
        value="Clínicas de Estética",
        help="Ex: Dentistas, Restaurantes, Contabilidades, Imobiliárias, Academias..."
    )
    
    cidade = st.text_input(
        "Cidade / Região",
        value="Campinas, SP",
        help="Ex: São Paulo, SP | Barra da Tijuca, RJ | Curitiba, PR"
    )
    
    termo_pesquisa = f"{nicho} em {cidade}".strip()
    st.caption(f"🔍 Busca: **{termo_pesquisa}**")
    
    limite = st.slider("Quantidade de Leads", min_value=5, max_value=80, value=20, step=5)
    
    modo_visivel = st.checkbox("Exibir Navegador (Debug)", value=False, help="Marque se quiser ver o robô abrindo o navegador na tela.")

    st.markdown("---")
    st.markdown("### 💬 Mensagem do WhatsApp")
    
    modelo_msg = st.selectbox(
        "Modelo de Abordagem",
        [
            "Venda de Sites & Presença Online",
            "Serviços de Tráfego Pago / Anúncios",
            "Apresentação Comercial Geral",
            "Personalizada"
        ]
    )
    
    if modelo_msg == "Venda de Sites & Presença Online":
        template_padrao = "Olá {nome}! Tudo bem? Encontrei vocês no Google Maps e reparei que vocês poderiam atrair muito mais clientes locais com uma presença online otimizada. Podemos conversar 2 minutos?"
    elif modelo_msg == "Serviços de Tráfego Pago / Anúncios":
        template_padrao = "Olá {nome}! Vi o excelente trabalho de vocês em {cidade}. Nós ajudamos empresas do nicho de {categoria} a lotarem a agenda com anúncios segmentados. Quem é o responsável pelo comercial?"
    elif modelo_msg == "Apresentação Comercial Geral":
        template_padrao = "Olá {nome}, tudo bem? Localizei a empresa de vocês aqui em {cidade} e gostaria de apresentar uma oportunidade rápida de parceria para a área de {categoria}."
    else:
        template_padrao = "Olá {nome}! Tudo bem? Vi a empresa de vocês no Google Maps."
        
    msg_zap = st.text_area(
        "Texto da Mensagem (tags: {nome}, {categoria}, {cidade})",
        value=template_padrao,
        height=120
    )
    
    st.markdown("---")
    # Histórico de Buscas Salvas
    st.markdown("### 📂 Histórico de Buscas")
    arquivos_salvos = sorted([f for f in os.listdir(HISTORICO_DIR) if f.endswith(".xlsx")], reverse=True)
    if arquivos_salvos:
        escolhido = st.selectbox("Carregar busca anterior:", ["-- Selecione --"] + arquivos_salvos)
        if st.button("Carregar Dados"):
            if escolhido != "-- Selecione --":
                caminho = os.path.join(HISTORICO_DIR, escolhido)
                df_carregado = pd.read_excel(caminho)
                st.session_state["leads_data"] = df_carregado.to_dict(orient="records")
                st.session_state["termo_atual"] = escolhido.replace(".xlsx", "")
                st.success(f"Carregado: {escolhido}")
                st.rerun()

# Cabeçalho Principal
st.markdown('<div class="main-title">⚡ LeadHunter - Extrator de Leads & WhatsApp</div>', unsafe_allow_html=True)
st.markdown('<div class="sub-title">Prospecte clientes locais no Google Maps e inicie conversas no WhatsApp com 1 clique.</div>', unsafe_allow_html=True)

# Linha de Ação Principal
col_btn, col_info = st.columns([1, 3])
with col_btn:
    iniciar_busca = st.button("🚀 Iniciar Prospecção", use_container_width=True, type="primary")

# Execução do Scraper
if iniciar_busca:
    if not nicho or not cidade:
        st.error("Por favor, preencha o Nicho e a Cidade antes de iniciar.")
    else:
        barra_progresso = st.progress(0)
        status_box = st.empty()
        
        # Callback para atualizar a UI em tempo real
        def on_progresso(atual, total, status_text, lead):
            pct = 0.0
            if total > 0:
                pct = min(1.0, atual / total)
            barra_progresso.progress(pct)
            status_box.info(f"⏳ **[{atual}/{total}]** {status_text}")

        # Inicia extração
        try:
            inicio = time.time()
            leads = raspar_google_maps(
                termo_busca=termo_pesquisa,
                limite=limite,
                mensagem_zap_template=msg_zap.replace("{cidade}", cidade),
                headless=not modo_visivel,
                progresso_callback=on_progresso
            )
            duracao = round(time.time() - inicio, 1)
            
            st.session_state["leads_data"] = leads
            st.session_state["termo_atual"] = termo_pesquisa
            
            # Salva automaticamente no histórico
            if leads:
                df_export = pd.DataFrame(leads)
                nome_arquivo = f"leads_{int(time.time())}_{termo_pesquisa.replace(' ', '_').replace(',', '')[:30]}.xlsx"
                caminho_hist = os.path.join(HISTORICO_DIR, nome_arquivo)
                df_export.to_excel(caminho_hist, index=False)
                
            barra_progresso.progress(1.0)
            status_box.success(f"✅ Concluído com sucesso! {len(leads)} leads encontrados em {duracao}s.")
            time.sleep(1)
            st.rerun()

        except Exception as e:
            status_box.error(f"Erro durante a extração: {str(e)}")

# Exibição dos Dados e Tabela
dados = st.session_state.get("leads_data", [])

if dados:
    df = pd.DataFrame(dados)
    
    # Tratamento e colunas de auxílio
    df["avaliacao_num"] = pd.to_numeric(df["avaliacao"], errors="coerce").fillna(0.0)
    df["tem_zap"] = df["telefone_zap"].apply(lambda x: bool(x and str(x).strip()))
    df["tem_site"] = df["site"].apply(lambda x: bool(x and x != "N/A" and str(x).startswith("http")))
    
    # Cards de Métricas
    m1, m2, m3, m4 = st.columns(4)
    with m1:
        st.metric("🏢 Total de Leads", len(df))
    with m2:
        total_zap = int(df["tem_zap"].sum())
        pct_zap = round((total_zap / len(df)) * 100) if len(df) > 0 else 0
        st.metric("📱 Com WhatsApp", f"{total_zap} ({pct_zap}%)")
    with m3:
        sem_site = int((~df["tem_site"]).sum())
        st.metric("🌐 Sem Site (Oportunidade)", sem_site)
    with m4:
        media_nota = df[df["avaliacao_num"] > 0]["avaliacao_num"].mean()
        media_fmt = f"⭐ {media_nota:.1f}" if pd.notnull(media_nota) else "N/A"
        st.metric("⭐ Média de Avaliações", media_fmt)

    st.markdown("---")
    
    # Filtros da Tabela
    st.markdown("#### 🔍 Filtros Rápidos")
    f_col1, f_col2, f_col3 = st.columns([1.5, 1.5, 2])
    
    with f_col1:
        filtro_zap = st.selectbox(
            "Filtro de Contato",
            ["Todos os contatos", "Apenas com WhatsApp / Celular", "Apenas com Telefone Fixo", "Sem Telefone"]
        )
    with f_col2:
        filtro_site = st.selectbox(
            "Filtro de Site",
            ["Todos", "Apenas SEM Site (Para vender sites)", "Apenas COM Site"]
        )
    with f_col3:
        termo_filtro = st.text_input("Filtrar por nome, categoria ou endereço:", "")

    # Aplica filtros no DataFrame
    df_filtrado = df.copy()
    
    if filtro_zap == "Apenas com WhatsApp / Celular":
        df_filtrado = df_filtrado[df_filtrado["tipo_telefone"] == "Celular / WhatsApp"]
    elif filtro_zap == "Apenas com Telefone Fixo":
        df_filtrado = df_filtrado[df_filtrado["tipo_telefone"].str.contains("Fixo", na=False)]
    elif filtro_zap == "Sem Telefone":
        df_filtrado = df_filtrado[df_filtrado["tipo_telefone"] == "Sem Telefone"]
        
    if filtro_site == "Apenas SEM Site (Para vender sites)":
        df_filtrado = df_filtrado[~df_filtrado["tem_site"]]
    elif filtro_site == "Apenas COM Site":
        df_filtrado = df_filtrado[df_filtrado["tem_site"]]
        
    if termo_filtro:
        termo_lower = termo_filtro.lower()
        df_filtrado = df_filtrado[
            df_filtrado["nome"].str.lower().str.contains(termo_lower, na=False) |
            df_filtrado["categoria"].str.lower().str.contains(termo_lower, na=False) |
            df_filtrado["endereco"].str.lower().str.contains(termo_lower, na=False)
        ]

    st.caption(f"Mostrando **{len(df_filtrado)}** de **{len(df)}** leads.")

    # TABELA PERSONALIZADA COM BOTÃO DO WHATSAPP
    # Reordenamos e configuramos as colunas
    colunas_exibir = [
        "link_whatsapp",
        "nome",
        "telefone",
        "tipo_telefone",
        "avaliacao",
        "total_avaliacoes",
        "categoria",
        "site",
        "endereco",
        "maps_link"
    ]
    
    colunas_presentes = [c for c in colunas_exibir if c in df_filtrado.columns]
    df_tabela = df_filtrado[colunas_presentes].copy()

    st.dataframe(
        df_tabela,
        use_container_width=True,
        hide_index=True,
        column_config={
            "link_whatsapp": st.column_config.LinkColumn(
                "💬 WhatsApp",
                help="Clique para abrir a conversa direta com o cliente no WhatsApp Web",
                display_text="📲 Chamar no Zap",
                width="medium"
            ),
            "nome": st.column_config.TextColumn("Nome da Empresa", width="large"),
            "telefone": st.column_config.TextColumn("Telefone", width="medium"),
            "tipo_telefone": st.column_config.TextColumn("Tipo", width="small"),
            "avaliacao": st.column_config.TextColumn("Nota", width="small"),
            "total_avaliacoes": st.column_config.NumberColumn("Avaliações", width="small"),
            "categoria": st.column_config.TextColumn("Categoria", width="medium"),
            "site": st.column_config.LinkColumn("Website", display_text="🌐 Acessar Site", width="medium"),
            "endereco": st.column_config.TextColumn("Endereço", width="large"),
            "maps_link": st.column_config.LinkColumn("Google Maps", display_text="📍 Ver no Mapa", width="small")
        }
    )

    # BOTÕES DE EXPORTAÇÃO
    st.markdown("---")
    st.markdown("### 📥 Exportar Resultados")
    
    col_exp1, col_exp2, col_exp3 = st.columns([1, 1, 2])
    
    # 1. Exportar para Excel (.xlsx) com estilo
    buffer_excel = io.BytesIO()
    with pd.ExcelWriter(buffer_excel, engine="openpyxl") as writer:
        df_filtrado.to_excel(writer, index=False, sheet_name="Leads_Google_Maps")
    buffer_excel.seek(0)
    
    with col_exp1:
        st.download_button(
            label="📊 Baixar Planilha Excel (.xlsx)",
            data=buffer_excel,
            file_name=f"leads_{st.session_state.get('termo_atual', 'maps').replace(' ', '_')}.xlsx",
            mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            use_container_width=True
        )

    # 2. Exportar para CSV formatado em UTF-8 com BOM
    csv_bytes = df_filtrado.to_csv(index=False, sep=";", encoding="utf-8-sig").encode("utf-8-sig")
    with col_exp2:
        st.download_button(
            label="📄 Baixar Arquivo CSV (.csv)",
            data=csv_bytes,
            file_name=f"leads_{st.session_state.get('termo_atual', 'maps').replace(' ', '_')}.csv",
            mime="text/csv",
            use_container_width=True
        )

else:
    # Mensagem de Boas-vindas quando ainda não há dados
    st.info("👈 Preencha o **Nicho** e a **Cidade** na barra lateral e clique em **🚀 Iniciar Prospecção** para extrair seus primeiros leads!")
    
    st.markdown("""
    #### 💡 Como prospectar clientes com o app:
    1. **Escolha o nicho**: Selecione profissões e comércios locais (ex: *Academias, Dentistas, Imobiliárias, Pizzarias, Mecânicas*).
    2. **Defina a cidade/região**: Quanto mais específico, mais assertiva a busca (ex: *Campinas, SP* ou *Moema, São Paulo*).
    3. **Escolha o modelo de abordagem**: Personalize a mensagem de abordagem com o nome da empresa e nicho.
    4. **Inicie a busca**: O app raspa o Google Maps em tempo real, extraindo telefones, sites e endereços.
    5. **Abra o Zap**: Clique direto no botão **'📲 Chamar no Zap'** da tabela para falar com o dono ou gerente!
    """)
