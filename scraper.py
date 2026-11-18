import re
import time
import urllib.parse
from typing import Callable, Optional, List, Dict, Any
from playwright.sync_api import sync_playwright, TimeoutError as PlaywrightTimeoutError

def formatar_telefone_brasil(tel_raw: str) -> Dict[str, Any]:
    """
    Limpa e formata números de telefone do Brasil.
    Retorna dicionário com:
    - telefone_formatado: (11) 98765-4321 ou (11) 3456-7890
    - telefone_zap: 5511987654321 (apenas números para wa.me)
    - tipo: 'Celular / WhatsApp' ou 'Fixo' ou 'Inválido'
    - tem_zap: bool
    """
    if not tel_raw or tel_raw == "N/A":
        return {
            "telefone_formatado": "N/A",
            "telefone_zap": "",
            "tipo": "Sem Telefone",
            "tem_zap": False
        }
    
    # Remove tudo que não for dígito
    digits = re.sub(r"\D", "", tel_raw)
    
    # Se começar com 0 (ex: 011987654321), remove o zero inicial
    if digits.startswith("0") and len(digits) in (11, 12):
        digits = digits[1:]
        
    # Se já começar com DDI 55 e tiver 12 ou 13 dígitos
    if digits.startswith("55") and len(digits) in (12, 13):
        sem_ddi = digits[2:]
    else:
        sem_ddi = digits
        
    # Telefones celulares no Brasil: DDD (2) + 9 dígitos = 11 dígitos
    # Telefones fixos: DDD (2) + 8 dígitos = 10 dígitos
    if len(sem_ddi) == 11 and sem_ddi[2] == "9":
        ddd = sem_ddi[:2]
        num = sem_ddi[2:]
        formatado = f"({ddd}) {num[:5]}-{num[5:]}"
        zap = f"55{sem_ddi}"
        return {
            "telefone_formatado": formatado,
            "telefone_zap": zap,
            "tipo": "Celular / WhatsApp",
            "tem_zap": True
        }
    elif len(sem_ddi) == 10:
        ddd = sem_ddi[:2]
        num = sem_ddi[2:]
        formatado = f"({ddd}) {num[:4]}-{num[4:]}"
        # Mesmo fixo, muitas empresas colocam WhatsApp Business
        zap = f"55{sem_ddi}"
        return {
            "telefone_formatado": formatado,
            "telefone_zap": zap,
            "tipo": "Fixo / Zap Business",
            "tem_zap": True
        }
    elif len(digits) >= 8:
        # Número genérico
        return {
            "telefone_formatado": tel_raw.strip(),
            "telefone_zap": f"55{digits}" if not digits.startswith("55") else digits,
            "tipo": "Outro",
            "tem_zap": True
        }
        
    return {
        "telefone_formatado": tel_raw.strip(),
        "telefone_zap": "",
        "tipo": "Inválido",
        "tem_zap": False
    }

def gerar_link_whatsapp(telefone_zap: str, mensagem: str = "") -> str:
    """Gera link wa.me direto com mensagem opcional codificada."""
    if not telefone_zap:
        return ""
    if mensagem:
        encoded_msg = urllib.parse.quote(mensagem)
        return f"https://wa.me/{telefone_zap}?text={encoded_msg}"
    return f"https://wa.me/{telefone_zap}"

def raspar_google_maps(
    termo_busca: str,
    limite: int = 20,
    mensagem_zap_template: str = "",
    headless: bool = True,
    progresso_callback: Optional[Callable[[int, int, str, Dict[str, Any]], None]] = None,
    deve_cancelar_callback: Optional[Callable[[], bool]] = None
) -> List[Dict[str, Any]]:
    """
    Raspa empresas no Google Maps para prospecção de leads.
    
    Args:
        termo_busca: O que buscar (ex: 'Dentistas em Campinas, SP')
        limite: Quantidade máxima de leads a extrair
        mensagem_zap_template: Template de mensagem com {nome}, {categoria}, {cidade}
        headless: True para rodar em segundo plano, False para abrir janela visível
        progresso_callback: Função (atual, total, status_text, lead_atual)
        deve_cancelar_callback: Função que retorna True se o usuário clicou em Parar
        
    Returns:
        Lista de dicionários com todos os dados dos leads.
    """
    resultados: List[Dict[str, Any]] = []
    encoded_query = urllib.parse.quote_plus(termo_busca)
    url_busca = f"https://www.google.com/maps/search/{encoded_query}?hl=pt-BR"
    
    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=headless,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-dev-shm-usage"
            ]
        )
        context = browser.new_context(
            user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
            locale="pt-BR"
        )
        page = context.new_page()
        page.set_default_timeout(20000)
        
        if progresso_callback:
            progresso_callback(0, limite, f"Conectando ao Google Maps para '{termo_busca}'...", {})
            
        page.goto(url_busca, wait_until="domcontentloaded")
        page.wait_for_timeout(3000)
        
        # Aceita consentimento do Google se aparecer
        try:
            consent_btn = page.locator('button:has-text("Aceitar tudo"), button:has-text("Concordo"), form[action*="consent"] button')
            if consent_btn.count() > 0:
                consent_btn.first.click()
                page.wait_for_timeout(1500)
        except Exception:
            pass

        # Verifica se o container de feed existe
        feed = page.locator('div[role="feed"]')
        if feed.count() == 0:
            # Pode ter caído direto na página de um local ou sem resultados
            page.wait_for_timeout(2000)
            if feed.count() == 0:
                browser.close()
                return resultados

        if progresso_callback:
            progresso_callback(0, limite, "Carregando listagem de estabelecimentos...", {})

        # 1. Faz scrolls sucessivos para carregar a quantidade desejada de cards
        tentativas_sem_novos = 0
        cards_coletados_hrefs = set()
        cards_elementos = []

        while len(cards_coletados_hrefs) < limite and tentativas_sem_novos < 5:
            if deve_cancelar_callback and deve_cancelar_callback():
                break

            # Pega todos os cards de locais atuais
            links = page.locator('div[role="feed"] a[href*="/maps/place/"]').all()
            tamanho_anterior = len(cards_coletados_hrefs)
            
            for lk in links:
                try:
                    href = lk.get_attribute("href")
                    if href and href not in cards_coletados_hrefs:
                        cards_coletados_hrefs.add(href)
                        cards_elementos.append(lk)
                        if len(cards_coletados_hrefs) >= limite:
                            break
                except Exception:
                    continue

            if len(cards_coletados_hrefs) == tamanho_anterior:
                tentativas_sem_novos += 1
            else:
                tentativas_sem_novos = 0

            if len(cards_coletados_hrefs) >= limite:
                break

            # Checa se chegou ao fim da lista
            fim_texto = page.locator('text="Você chegou ao final da lista"')
            if fim_texto.count() > 0:
                break

            # Rola a barra de rolagem do feed para baixo
            try:
                page.evaluate('document.querySelector("div[role=\\"feed\\"]").scrollTop += 3500')
                page.wait_for_timeout(1800)
            except Exception:
                break

        total_encontrados = min(len(cards_elementos), limite)
        if progresso_callback:
            progresso_callback(0, total_encontrados, f"{total_encontrados} estabelecimentos identificados. Extraindo detalhes...", {})

        # 2. Itera sobre cada card para extrair os detalhes profundos
        for idx in range(total_encontrados):
            if deve_cancelar_callback and deve_cancelar_callback():
                break
                
            lead_info: Dict[str, Any] = {
                "nome": "N/A",
                "categoria": "Geral",
                "avaliacao": "N/A",
                "total_avaliacoes": 0,
                "telefone": "N/A",
                "telefone_zap": "",
                "tipo_telefone": "Sem Telefone",
                "link_whatsapp": "",
                "site": "N/A",
                "endereco": "N/A",
                "maps_link": ""
            }

            try:
                # Re-localiza o link para evitar stale elements
                current_links = page.locator('div[role="feed"] a[href*="/maps/place/"]').all()
                if idx < len(current_links):
                    card = current_links[idx]
                else:
                    break

                maps_url = card.get_attribute("href") or ""
                lead_info["maps_link"] = maps_url
                
                # Nome pode vir do aria-label do link
                raw_name = card.get_attribute("aria-label") or ""
                if not raw_name:
                    try:
                        raw_name = card.locator('div.fontHeadlineSmall').inner_text()
                    except Exception:
                        raw_name = card.inner_text().split("\n")[0]
                lead_info["nome"] = raw_name.strip()

                if progresso_callback:
                    progresso_callback(idx + 1, total_encontrados, f"Extraindo dados de: {lead_info['nome']}", lead_info)

                # Clica no card para abrir o painel lateral com dados detalhados
                try:
                    card.scroll_into_view_if_needed()
                    card.click()
                    page.wait_for_timeout(1600)
                except Exception:
                    # Tenta forçar clique via javascript
                    try:
                        card.evaluate("el => el.click()")
                        page.wait_for_timeout(1600)
                    except Exception:
                        pass

                # Confirma / atualiza Nome pelo título do painel
                try:
                    title_elem = page.locator('h1.DUwDvf').first
                    if title_elem.count() > 0:
                        tit_text = title_elem.inner_text().strip()
                        if tit_text:
                            lead_info["nome"] = tit_text
                except Exception:
                    pass

                # Categoria
                try:
                    cat_btn = page.locator('button.DkEaL').first
                    if cat_btn.count() > 0:
                        lead_info["categoria"] = cat_btn.inner_text().strip()
                except Exception:
                    pass

                # Avaliação e Quantidade de Avaliações
                try:
                    rating_box = page.locator('div.F7nice').first
                    if rating_box.count() > 0:
                        rating_span = rating_box.locator('span[aria-hidden="true"]').first
                        if rating_span.count() > 0:
                            lead_info["avaliacao"] = rating_span.inner_text().strip().replace(",", ".")
                            
                        rev_span = rating_box.locator('span[aria-label*="avalia"]').first
                        if rev_span.count() > 0:
                            rev_text = rev_span.get_attribute("aria-label") or rev_span.inner_text()
                            num_rev = re.sub(r"\D", "", rev_text)
                            lead_info["total_avaliacoes"] = int(num_rev) if num_rev else 0
                except Exception:
                    pass

                # Telefone
                raw_phone = ""
                try:
                    phone_btn = page.locator('button[data-tooltip="Copiar número de telefone"], button[data-item-id^="phone:"], button[aria-label*="Telefone"]').first
                    if phone_btn.count() > 0:
                        aria = phone_btn.get_attribute("aria-label") or ""
                        if "Telefone:" in aria:
                            raw_phone = aria.replace("Telefone:", "").strip()
                        else:
                            raw_phone = phone_btn.inner_text().strip()
                            # Limpa ícones especiais
                            raw_phone = re.sub(r"[^\d\s\(\)\-\+]", "", raw_phone).strip()
                except Exception:
                    pass

                # Formata Telefone e WhatsApp
                info_tel = formatar_telefone_brasil(raw_phone)
                lead_info["telefone"] = info_tel["telefone_formatado"]
                lead_info["telefone_zap"] = info_tel["telefone_zap"]
                lead_info["tipo_telefone"] = info_tel["tipo"]
                
                # Monta mensagem personalizada para o WhatsApp
                msg_customizada = ""
                if mensagem_zap_template and lead_info["telefone_zap"]:
                    msg_customizada = mensagem_zap_template.format(
                        nome=lead_info["nome"],
                        categoria=lead_info["categoria"],
                        termo=termo_busca
                    )
                lead_info["link_whatsapp"] = gerar_link_whatsapp(lead_info["telefone_zap"], msg_customizada)

                # Website
                try:
                    site_btn = page.locator('a[data-tooltip="Abrir o site"], a[data-item-id="authority"], a[aria-label*="Website"]').first
                    if site_btn.count() > 0:
                        site_href = site_btn.get_attribute("href") or ""
                        # Se for redirect do Google, limpa
                        if site_href.startswith("/url?q="):
                            site_href = site_href.split("/url?q=")[1].split("&")[0]
                        lead_info["site"] = site_href.strip() if site_href else "N/A"
                except Exception:
                    pass

                # Endereço
                try:
                    addr_btn = page.locator('button[data-tooltip="Copiar endereço"], button[data-item-id="address"], button[aria-label*="Endereço"]').first
                    if addr_btn.count() > 0:
                        aria_addr = addr_btn.get_attribute("aria-label") or ""
                        if "Endereço:" in aria_addr:
                            lead_info["endereco"] = aria_addr.replace("Endereço:", "").strip()
                        else:
                            addr_text = addr_btn.inner_text().strip()
                            lead_info["endereco"] = re.sub(r"[\ue000-\uf8ff]", "", addr_text).strip()
                except Exception:
                    pass

                resultados.append(lead_info)

                if progresso_callback:
                    progresso_callback(idx + 1, total_encontrados, f"Pronto: {lead_info['nome']} ({lead_info['tipo_telefone']})", lead_info)

            except Exception as e:
                # Continua se algum card individual falhar
                continue

        browser.close()

    return resultados
