import sys
import io

# UTF-8 output para Windows
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')
sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8', errors='replace')

from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
import os
from datetime import datetime
import sqlite3
import pandas as pd
from openpyxl import load_workbook
from pathlib import Path

# Mudar para o diretório do script (suporta execução via caminho completo)
SCRIPT_DIR = Path(__file__).parent.resolve()
os.chdir(SCRIPT_DIR)

# Configuração de pasta para logs de snapshots
logs_folder = os.path.join(os.getcwd(), "serpro_snapshots_logs") + os.sep
if not os.path.exists(logs_folder):
    os.makedirs(logs_folder)
    print(f"Pasta de logs criada: {logs_folder}")

# Configuração do Chrome
options = webdriver.ChromeOptions()
prefs = {
    "download.default_directory": os.path.join(os.getcwd(), "downloads_serpro"),
    "download.prompt_for_download": False,
    "download.directory_upgrade": True,
    "safebrowsing.enabled": True
}
options.add_experimental_option("prefs", prefs)

# Criar pasta de downloads se não existir
download_folder = os.path.join(os.getcwd(), "downloads_serpro")
if not os.path.exists(download_folder):
    os.makedirs(download_folder)
    print(f"Pasta de downloads criada: {download_folder}")

# Configuração do banco de dados SQLite
cnxn = sqlite3.connect('base_dados.db')

def salvar_snapshot(nome_etapa):
    """Salva snapshot HTML da página para auditoria"""
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    
    try:
        # Salvar HTML completo
        html_content = driver.page_source
        html_filename = os.path.join(logs_folder, f"{timestamp}_{nome_etapa}.html")
        with open(html_filename, 'w', encoding='utf-8') as f:
            f.write(html_content)
        print(f"  [HTML] {html_filename}")
        
        # Salvar log resumido
        log_filename = os.path.join(logs_folder, f"{timestamp}_{nome_etapa}_log.txt")
        with open(log_filename, 'w', encoding='utf-8') as f:
            f.write(f"Etapa: {nome_etapa}\n")
            f.write(f"Timestamp: {timestamp}\n")
            f.write(f"URL: {driver.current_url}\n")
            f.write(f"Titulo: {driver.title}\n")
        print(f"  [LOG] {log_filename}")
        
        return True
    except Exception as e:
        print(f"✗ Erro ao salvar snapshot: {e}")
        return False

def aguardar_carregamento_pagina(timeout=60):
    """Aguarda a página carregar completamente"""
    print("\n[1] Aguardando carregamento da página...")
    
    try:
        # Espera o document estar ready
        WebDriverWait(driver, timeout).until(
            lambda driver: driver.execute_script("return document.readyState") == "complete"
        )
        print("✓ Página carregada (document.readyState = complete)")
        
        # Aguarda um pouco extra para elementos renderizarem
        time.sleep(3)
        
        salvar_snapshot("01_pagina_carregada")
        return True
        
    except Exception as e:
        print(f"✗ Erro no carregamento: {e}")
        salvar_snapshot("01_erro_carregamento")
        return False

def aguardar_elemento_qv_inner_object(intervalo=10, timeout_max=600):
    """
    Aguarda o elemento <div class="qv-inner-object"> aparecer
    Verifica a cada 'intervalo' segundos até 'timeout_max'
    """
    print("\n[1.5] Aguardando elemento 'qv-inner-object'...")
    print(f"       Verificando a cada {intervalo} segundos (timeout: {timeout_max}s)")
    
    tempo_decorrido = 0
    tentativa = 0
    
    while tempo_decorrido < timeout_max:
        tentativa += 1
        
        try:
            # Verifica se o elemento existe
            elemento = driver.find_element(By.CLASS_NAME, "qv-inner-object")
            
            if elemento:
                print(f"✓ Elemento encontrado na tentativa {tentativa} ({tempo_decorrido}s)")
                salvar_snapshot("01_5_qv_inner_object_encontrado")
                return True
                
        except:
            pass
        
        # Verifica também via CSS selector (mais específico)
        try:
            elemento = driver.find_element(By.CSS_SELECTOR, "div.qv-inner-object")
            if elemento:
                print(f"✓ Elemento encontrado via CSS selector na tentativa {tentativa} ({tempo_decorrido}s)")
                salvar_snapshot("01_5_qv_inner_object_encontrado")
                return True
        except:
            pass
        
        # Se não encontrou, aguarda e verifica novamente
        print(f"  [{tentativa}] Não encontrado. Aguardando {intervalo}s... ({tempo_decorrido}/{timeout_max}s)")
        time.sleep(intervalo)
        tempo_decorrido += intervalo
    
    print(f"✗ Timeout! Elemento não encontrado em {timeout_max} segundos")
    salvar_snapshot("01_5_erro_qv_inner_object_timeout")
    return False

def clicar_botao_direito_meio_tela():
    """Clica com botão direito no meio da tela e aguarda o menu aparecer"""
    print("\n[2] Clicando com botão direito no meio da tela...")
    
    try:
        # Obtém dimensões da janela
        window_size = driver.get_window_size()
        meio_x = window_size['width'] // 2
        meio_y = window_size['height'] // 2
        
        # Tenta encontrar um elemento SVG ou canvas (comum em dashboards)
        elementos_interativos = driver.find_elements(By.CSS_SELECTOR, "svg, canvas, [role='main'], .object-wrapper, [ng-app]")
        
        if elementos_interativos:
            elemento = elementos_interativos[0]
            print(f"✓ Elemento interativo encontrado: {elemento.tag_name}")
        else:
            elemento = driver.find_element(By.TAG_NAME, "body")
            print("  Usando elemento body")
        
        # Clica com botão direito
        actions = ActionChains(driver)
        actions.context_click(elemento).perform()
        
        print(f"✓ Clique direito realizado em ({meio_x}, {meio_y})")
        
        # Aguarda o menu aparecer
        time.sleep(2)
        
        salvar_snapshot("02_menu_contexto")
        return True
        
    except Exception as e:
        print(f"✗ Erro ao clicar com botão direito: {e}")
        salvar_snapshot("02_erro_menu_contexto")
        return False

def clicar_exportar_dados():
    """Clica na opção 'Exportar dados' via JavaScript"""
    print("\n[3] Clicando em 'Exportar dados'...")
    
    try:
        resultado = driver.execute_script("""
            const elementos = Array.from(document.querySelectorAll('*'));
            const encontrado = elementos.find(el => 
                el.textContent.toLowerCase().includes('exportar') && 
                el.textContent.toLowerCase().includes('dados')
            );
            if (encontrado) {
                encontrado.click();
                return true;
            }
            return false;
        """)
        
        if resultado:
            print("✓ Clicado em 'Exportar dados'")
            time.sleep(3)  # Aguarda menu aparecer
            salvar_snapshot("03_exportar_dados_clicado")
            return True
        
        print("✗ 'Exportar dados' não encontrado")
        salvar_snapshot("03_erro_exportar_dados")
        return False
        
    except Exception as e:
        print(f"✗ Erro ao clicar em 'Exportar dados': {e}")
        salvar_snapshot("03_erro_exportar_dados")
        return False
        
    except Exception as e:
        print(f"✗ Erro ao clicar em 'Exportar dados': {e}")
        salvar_snapshot("03_erro_exportar_dados")
        return False

def clicar_formatacao_tabela():
    """Clica em 'Formatação de tabela' via JavaScript"""
    print("\n[4] Clicando em 'Formatação de tabela'...")
    
    try:
        resultado = driver.execute_script("""
            const elementos = Array.from(document.querySelectorAll('*'));
            const encontrado = elementos.find(el => 
                el.textContent.toLowerCase().includes('formatação') && 
                el.textContent.toLowerCase().includes('tabela')
            ) || elementos.find(el => 
                el.textContent.toLowerCase().includes('formato')
            );
            if (encontrado) {
                encontrado.click();
                return true;
            }
            return false;
        """)
        
        if resultado:
            print("✓ Clicado em 'Formatação de tabela'")
            time.sleep(2)
            salvar_snapshot("04_formatacao_tabela_clicada")
            return True
        
        print("✗ 'Formatação de tabela' não encontrado")
        salvar_snapshot("04_erro_formatacao_tabela")
        return False
        
    except Exception as e:
        print(f"✗ Erro ao clicar em 'Formatação de tabela': {e}")
        salvar_snapshot("04_erro_formatacao_tabela")
        return False
        
    except Exception as e:
        print(f"✗ Erro: {e}")
        salvar_snapshot("04_erro_formatacao_tabela")
        return False

def aguardar_botao_export_url(intervalo=5, timeout_max=120):
    """
    Aguarda o botão <a class="export-url"> aparecer e clica nele
    Este é o link para download que aparece APÓS clicar em "Exportar"
    """
    print("\n[5.5] Aguardando link de download (botão export-url)...")
    print(f"       Verificando a cada {intervalo} segundos (timeout: {timeout_max}s)")
    
    tempo_decorrido = 0
    tentativa = 0
    
    while tempo_decorrido < timeout_max:
        tentativa += 1
        
        try:
            # Procura pelo elemento <a class="export-url">
            elemento = driver.find_element(By.CSS_SELECTOR, "a.export-url")
            
            if elemento and elemento.is_displayed():
                print(f"✓ Botão 'export-url' encontrado na tentativa {tentativa} ({tempo_decorrido}s)")
                print(f"  URL: {elemento.get_attribute('href')[:80]}...")
                
                # Scroll para o elemento
                driver.execute_script("arguments[0].scrollIntoView(true);", elemento)
                time.sleep(0.5)
                
                # Clica no botão
                elemento.click()
                print(f"✓ Clique no botão export-url realizado!")
                
                salvar_snapshot("05_5_botao_export_clicado")
                time.sleep(2)  # Aguarda o navegador processar o clique
                
                return True
        
        except Exception as e:
            pass
        
        # Se não encontrou, aguarda e verifica novamente
        print(f"  [{tentativa}] Link não encontrado. Aguardando... ({tempo_decorrido}/{timeout_max}s)")
        time.sleep(intervalo)
        tempo_decorrido += intervalo
    
    print(f"✗ Timeout! Botão export-url não apareceu em {timeout_max} segundos")
    salvar_snapshot("05_5_erro_export_url_timeout")
    return False

def verificar_download_completo(intervalo=10, timeout_max=600):
    """
    Verifica se um arquivo foi baixado na pasta downloads_serpro
    Aguarda a cada 'intervalo' segundos até 'timeout_max'
    """
    print("\n[5.6] Verificando download do arquivo...")
    print(f"       Verificando a cada {intervalo} segundos (timeout: {timeout_max}s)")
    print(f"       Pasta: {download_folder}")
    
    tempo_decorrido = 0
    tentativa = 0
    arquivo_encontrado = None
    
    while tempo_decorrido < timeout_max:
        tentativa += 1
        
        try:
            # Lista arquivos na pasta de downloads
            arquivos = os.listdir(download_folder)
            
            if arquivos:
                # Filtra arquivos que não são .crdownload (downloads incompletos)
                arquivos_completos = [f for f in arquivos if not f.endswith('.crdownload') and not f.endswith('.tmp')]
                
                if arquivos_completos:
                    arquivo_encontrado = arquivos_completos[0]
                    tamanho = os.path.getsize(os.path.join(download_folder, arquivo_encontrado))
                    print(f"✓ Arquivo baixado na tentativa {tentativa} ({tempo_decorrido}s)")
                    print(f"  Nome: {arquivo_encontrado}")
                    print(f"  Tamanho: {tamanho} bytes")
                    salvar_snapshot("05_5_download_completo")
                    return True
                else:
                    print(f"  [{tentativa}] Arquivo ainda baixando... ({tempo_decorrido}/{timeout_max}s)")
            else:
                print(f"  [{tentativa}] Nenhum arquivo detectado. Aguardando... ({tempo_decorrido}/{timeout_max}s)")
        
        except Exception as e:
            print(f"  Erro ao verificar pasta: {e}")
        
        time.sleep(intervalo)
        tempo_decorrido += intervalo
    
    print(f"✗ Timeout! Arquivo não foi baixado em {timeout_max} segundos")
    salvar_snapshot("05_5_erro_download_timeout")
    return False

def clicar_exportar_final():
    """Clica no botão 'Exportar' final via JavaScript"""
    print("\n[5] Clicando em 'Exportar'...")
    
    try:
        resultado = driver.execute_script("""
            const botoes = Array.from(document.querySelectorAll('button, [role="button"]'));
            const encontrado = botoes.find(el => 
                el.textContent.toLowerCase().includes('exportar')
            );
            if (encontrado) {
                encontrado.click();
                return true;
            }
            return false;
        """)
        
        if resultado:
            print("✓ Clicado em 'Exportar'")
            salvar_snapshot("05_exportacao_clicada")
            time.sleep(2)
            
            # Aguarda o link de download aparecer
            if not aguardar_botao_export_url(intervalo=5, timeout_max=120):
                return False
            
            # Aguarda o download completar
            if verificar_download_completo(intervalo=10, timeout_max=600):
                salvar_snapshot("05_exportacao_completada")
                return True
            else:
                return False
        
        print("✗ Botão 'Exportar' não encontrado")
        salvar_snapshot("05_erro_exportacao")
        return False
        
    except Exception as e:
        print(f"✗ Erro ao clicar em 'Exportar': {e}")
        salvar_snapshot("05_erro_exportacao")
        return False
        
        # [ETAPA FINAL] Aguarda o download completar
        if verificar_download_completo(intervalo=10, timeout_max=600):
            salvar_snapshot("05_exportacao_completada")
            return True
        else:
            return False
        
    except Exception as e:
        print(f"✗ Erro ao clicar: {e}")
        print("  Tentando alternativa via JavaScript...")
        
        try:
            resultado = driver.execute_script("""
                const botoes = Array.from(document.querySelectorAll('button, [role="button"]'));
                const encontrado = botoes.find(el => 
                    el.textContent.toLowerCase().includes('exportar')
                );
                if (encontrado) {
                    encontrado.click();
                    return true;
                }
                return false;
            """)
            
            if resultado:
                print("✓ Clicado via JavaScript")
                salvar_snapshot("05_exportacao_clicada")
                time.sleep(1)
                
                # Aguarda o link e o download
                if not aguardar_botao_export_url(intervalo=5, timeout_max=120):
                    return False
                
                if verificar_download_completo(intervalo=10, timeout_max=600):
                    salvar_snapshot("05_exportacao_completada")
                    return True
                else:
                    return False
        
        except Exception as e2:
            print(f"✗ Alternativa também falhou: {e2}")
        
        salvar_snapshot("05_erro_exportacao")
        return False

def importar_excel_para_sqlite(caminho_arquivo):
    """Importa o arquivo Excel baixado para o banco SQLite"""
    print("\n" + "="*60)
    print("IMPORTANDO EXCEL PARA SQLITE")
    print("="*60)
    print(f"Arquivo: {caminho_arquivo}")
    sys.stdout.flush()

    nome_tabela = 'dados_serpro'

    try:
        # Conectar ao banco
        cnxn = sqlite3.connect('base_dados.db')
        cursor = cnxn.cursor()

        # Limpar dados anteriores
        print("Limpando dados da tabela dados_serpro...")
        cursor.execute(f"DELETE FROM {nome_tabela}")
        cnxn.commit()
        print("Dados limpos com sucesso.")
        sys.stdout.flush()

        # Criar tabela se nao existir
        cursor.execute(f'''
            CREATE TABLE IF NOT EXISTS {nome_tabela} (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                ano_abertura TEXT,
                mes_abertura TEXT,
                ano_baixa TEXT,
                mes_baixa TEXT,
                regiao TEXT,
                uf TEXT,
                municipio TEXT,
                natureza_juridica TEXT,
                des_secao TEXT,
                tipo_situacao TEXT,
                porte TEXT,
                opcao_mei TEXT,
                quantidade INTEGER
            )
        ''')
        cnxn.commit()

        # Processar com openpyxl em chunks
        print("Lendo Excel com openpyxl...")
        sys.stdout.flush()

        wb = load_workbook(filename=caminho_arquivo, read_only=True, data_only=True)
        ws = wb.active

        chunk_size = 5000
        chunk_num = 0
        total_inserido = 0
        row_num = 0
        dados = []

        for row in ws.iter_rows(min_row=2, values_only=True):
            row_num += 1

            try:
                dados.append((
                    str(row[0]) if row[0] is not None else '',
                    str(row[1]) if row[1] is not None else '',
                    str(row[2]) if row[2] is not None else '',
                    str(row[3]) if row[3] is not None else '',
                    str(row[4]) if row[4] is not None else '',
                    str(row[5]) if row[5] is not None else '',
                    str(row[6]) if row[6] is not None else '',
                    str(row[7]) if row[7] is not None else '',
                    str(row[8]) if row[8] is not None else '',
                    str(row[9]) if row[9] is not None else '',
                    str(row[10]) if row[10] is not None else '',
                    str(row[11]) if row[11] is not None else '',
                    int(row[12]) if row[12] is not None else 0
                ))
            except Exception as e:
                pass

            if len(dados) >= chunk_size:
                chunk_num += 1
                print(f"  Inserting chunk {chunk_num}: {len(dados)} rows... (row {row_num})")
                sys.stdout.flush()

                cursor.executemany(f'''
                    INSERT INTO {nome_tabela} (
                        ano_abertura, mes_abertura, ano_baixa, mes_baixa,
                        regiao, uf, municipio, natureza_juridica,
                        des_secao, tipo_situacao, porte, opcao_mei, quantidade
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                ''', dados)
                cnxn.commit()

                total_inserido += len(dados)
                print(f"  Chunk {chunk_num} inserted! Total: {total_inserido}")
                sys.stdout.flush()
                dados = []

        # Insert remaining
        if dados:
            chunk_num += 1
            print(f"  Inserting final chunk {chunk_num}: {len(dados)} rows...")
            sys.stdout.flush()

            cursor.executemany(f'''
                INSERT INTO {nome_tabela} (
                    ano_abertura, mes_abertura, ano_baixa, mes_baixa,
                    regiao, uf, municipio, natureza_juridica,
                    des_secao, tipo_situacao, porte, opcao_mei, quantidade
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', dados)
            cnxn.commit()

            total_inserido += len(dados)
            print(f"  Final chunk inserted! Total: {total_inserido}")
            sys.stdout.flush()

        wb.close()

        # Verify total
        cursor.execute(f"SELECT COUNT(*) FROM {nome_tabela}")
        total_final = cursor.fetchone()[0]

        cursor.close()
        cnxn.close()

        print("\n" + "="*60)
        print(f"IMPORTACAO CONCLUIDA!")
        print(f"Total registros na tabela: {total_final}")
        print("="*60)
        sys.stdout.flush()
        return True

    except Exception as e:
        print(f"Erro na importacao: {e}")
        import traceback
        traceback.print_exc()
        return False

def executar_ciclo_completo():
    """Executa ciclo completo: baixar + importar"""
    print("\n" + "="*60)
    print("INICIANDO CICLO COMPLETO (BAIXAR + IMPORTAR)")
    print("="*60)
    
    # Etapa 1: Baixar
    if not baixar_somente():
        print("\n✗ Falha na etapa de download")
        return False
    
    # Etapa 2: Importar
    if not importar_ultimo_download():
        print("\n✗ Falha na etapa de importacao")
        return False
    
    print("\n" + "="*60)
    print("✓ CICLO COMPLETO FINALIZADO COM SUCESSO!")
    print("="*60)
    return True

def executar_em_loop(intervalo_minutos=60, limite_tentativas=None):
    """Executa a automação em loop a cada X minutos"""
    print(f"\n⏰ Modo LOOP ativado: execução a cada {intervalo_minutos} minuto(s)")
    if limite_tentativas:
        print(f"   Limite de tentativas: {limite_tentativas}")
    else:
        print(f"   Limite de tentativas: infinito")
    
    tentativa = 0
    while True:
        tentativa += 1
        
        if limite_tentativas and tentativa > limite_tentativas:
            print(f"\n✓ Limite de tentativas ({limite_tentativas}) atingido. Encerrando.")
            break
        
        print(f"\n{'='*60}")
        print(f"TENTATIVA {tentativa} - {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print(f"{'='*60}")
        
        resultado = executar_ciclo_completo()
        
        if resultado:
            print(f"\n✓ Sucesso na tentativa {tentativa}")
        else:
            print(f"\n✗ Falha na tentativa {tentativa}")
        
        if tentativa < (limite_tentativas or float('inf')):
            print(f"\n⏳ Próxima execução em {intervalo_minutos} minuto(s)...")
            time.sleep(intervalo_minutos * 60)

def baixar_somente(ano=None):
    """Faz apenas o download do arquivo do SERPRO sem importar para o banco"""
    print("\n" + "="*60)
    print("MODO: BAIXAR SOMENTE")
    print("="*60)
    
    url_base = "https://dd.serpro.gov.br/publico/single/?appid=7979697b-ad3d-4b28-a5bf-9cd48ea9eae7&obj=vVDJ&theme=tema%20serpro&opt=ctxmenu,currsel&identity=preview_hdmBV"
    
    if ano:
        url = f"{url_base}&select=$::Ano%20de%20Abertura,{ano}"
        print(f"Filtrando por ano: {ano}")
    else:
        url = url_base
        print("Baixando todos os anos")
    
    try:
        global driver
        driver = webdriver.Chrome(options=options)
        print("✓ Navegador aberto")
        
        print(f"\nAcessando: {url}")
        driver.get(url)
        driver.maximize_window()
        print("✓ URL acessada")
        
        salvar_snapshot("00_pagina_inicial")
        
        if not aguardar_carregamento_pagina():
            return False
        
        if not aguardar_elemento_qv_inner_object(intervalo=10, timeout_max=600):
            return False
        
        if not clicar_botao_direito_meio_tela():
            return False

        # Espera 2s para o menu de contexto abrir totalmente
        time.sleep(2)

        # Clicar em "Exportar dados" usando Selenium real (AngularJS não reage a .click() JS)
        print("\n[3] Clicando em 'Exportar dados' (click nativo)...")
        try:
            li_export_dados = WebDriverWait(driver, 15).until(
                EC.element_to_be_clickable((By.CSS_SELECTOR, "li#export-data"))
            )
            # Pega o <span> interno com o texto (mais estável para o evento)
            span = li_export_dados.find_element(By.CSS_SELECTOR, "span.lui-list__text")
            driver.execute_script("arguments[0].scrollIntoView({block:'center'});", li_export_dados)
            time.sleep(0.3)
            # Clique duplo: ActionChains dispara mousedown+mouseup+click que o AngularJS escuta
            ActionChains(driver).move_to_element(span).pause(0.1).click(span).perform()
            print("✓ Clicado em 'Exportar dados' (ActionChains)")
            time.sleep(2)  # espera diálogo abrir
            salvar_snapshot("03_exportar_dados")

            # VERIFICAÇÃO: o menu de contexto deve ter sumido e o diálogo deve ter aparecido
            contexto_ainda_visivel = driver.execute_script("""
                const menu = document.querySelector('li#export-data');
                return menu && menu.offsetParent !== null;
            """)
            if contexto_ainda_visivel:
                print("⚠ Menu de contexto AINDA visível após o clique. Salvando snapshot de debug...")
                salvar_snapshot("03_debug_menu_ainda_visivel")
                return False
            print("✓ Menu de contexto sumiu (clique confirmado)")
        except Exception as e:
            print(f"✗ Falha ao clicar em 'Exportar dados': {e}")
            salvar_snapshot("03_erro_exportar_dados")
            return False

        # Espera 2s para o diálogo de exportação abrir
        time.sleep(2)

        # Clicar em "Exportar" no diálogo - agora com click nativo também
        print("\n[4] Clicando em 'Exportar' (botão do diálogo)...")
        try:
            # Tenta achar pelo texto exato em <button> do Qlik
            botao_exportar = WebDriverWait(driver, 15).until(
                EC.element_to_be_clickable((By.XPATH, "//button[normalize-space(.)='Exportar' or .//span[normalize-space(.)='Exportar']]"))
            )
            driver.execute_script("arguments[0].scrollIntoView({block:'center'});", botao_exportar)
            time.sleep(0.3)
            ActionChains(driver).move_to_element(botao_exportar).pause(0.1).click(botao_exportar).perform()
            print(f"✓ Clicado em 'Exportar' (botão nativo)")
            time.sleep(2)
            salvar_snapshot("04_exportar")

            # VERIFICAÇÃO: o diálogo deve ter sumido e o link de download deve começar a aparecer
            # (link pode demorar até 180s, então só checamos que o diálogo sumiu)
            dialogo_ainda_visivel = driver.execute_script("""
                const btn = Array.from(document.querySelectorAll('button, span'))
                    .find(el => (el.innerText || el.textContent || '').trim() === 'Exportar' && el.offsetParent);
                return btn !== undefined;
            """)
            if dialogo_ainda_visivel:
                print("⚠ Botão 'Exportar' AINDA visível após o clique. Salvando snapshot de debug...")
                salvar_snapshot("04_debug_botao_ainda_visivel")
                return False
            print("✓ Diálogo fechou (clique confirmado)")
        except Exception as e:
            print(f"✗ 'Exportar' (botão final) não encontrado: {e}")
            salvar_snapshot("04_erro_exportar")
            return False

        # Espera 2s antes de procurar o link de download
        time.sleep(2)

        # Aguardar link de download aparecer
        print("\n[5] Aguardando link de download...")
        if not aguardar_botao_export_url(intervalo=5, timeout_max=180):
            return False
        
        # Aguardar download terminar
        print("\nAguardando finalizacao do download...")
        if not aguardar_download_terminar(timeout_max=600):
            print("\n✗ Download nao completou")
            return False
        
        arquivos = [f for f in os.listdir(download_folder) if f.endswith('.xlsx') and not f.endswith('.crdownload')]
        if arquivos:
            arquivo_baixado = os.path.join(download_folder, arquivos[0])
            print(f"\n✓ Download concluido: {arquivo_baixado}")
            return True
        else:
            print("\n✗ Nenhum arquivo baixado encontrado")
            return False
            
    except Exception as e:
        print(f"\n✗ Erro: {e}")
        salvar_snapshot("99_erro_geral")
        return False
    finally:
        if driver:
            time.sleep(2)
            driver.quit()
            print("✓ Navegador fechado")


def aguardar_download_terminar(intervalo=5, timeout_max=600):
    """Aguarda o arquivo .crdownload sumir (download completo)"""
    print(f"Aguardando download (timeout: {timeout_max}s)...")
    tempo_decorrido = 0
    
    while tempo_decorrido < timeout_max:
        crdownload_files = [f for f in os.listdir(download_folder) if f.endswith('.crdownload')]
        
        if not crdownload_files:
            print(f"✓ Download completo! ({tempo_decorrido}s)")
            return True
        
        tamanho = os.path.getsize(os.path.join(download_folder, crdownload_files[0])) if crdownload_files else 0
        print(f"  Download em andamento: {crdownload_files[0]} ({tamanho/1024/1024:.1f}MB)")
        
        time.sleep(intervalo)
        tempo_decorrido += intervalo
    
    print(f"✗ Timeout no download ({timeout_max}s)")
    return False


def importar_ultimo_download():
    """Importa o último arquivo baixado para o banco SQLite"""
    arquivos = [f for f in os.listdir(download_folder) if f.endswith('.xlsx') and not f.endswith('.crdownload')]
    
    if not arquivos:
        print("✗ Nenhum arquivo .xlsx encontrado na pasta de downloads")
        return False
    
    arquivo_baixado = os.path.join(download_folder, arquivos[0])
    print(f"\nArquivo encontrado: {arquivo_baixado}")
    
    return importar_excel_para_sqlite(arquivo_baixado)


def executar_ciclo_completo():
    """Executa ciclo completo: baixar + importar"""
    print("\n" + "="*60)
    print("INICIANDO CICLO COMPLETO (BAIXAR + IMPORTAR)")
    print("="*60)
    
    # Etapa 1: Baixar
    if not baixar_somente():
        print("\n✗ Falha na etapa de download")
        return False
    
    # Etapa 2: Importar
    if not importar_ultimo_download():
        print("\n✗ Falha na etapa de importacao")
        return False
    
    print("\n" + "="*60)
    print("✓ CICLO COMPLETO FINALIZADO COM SUCESSO!")
    print("="*60)
    return True


if __name__ == "__main__":
    import argparse
    
    print("EXPORTADOR DE DADOS SERPRO COM SNAPSHOTS")
    print("========================================\n")
    
    parser = argparse.ArgumentParser(description="Exportador SERPRO")
    parser.add_argument("acao", nargs="?", default="completo",
                        choices=["completo", "baixar", "importar", "info"],
                        help="Acoes: completo (padrao), baixar, importar, info")
    parser.add_argument("--arquivo", "-f", type=str, default=None,
                        help="Caminho do arquivo para importar (usado com acao=importar)")
    parser.add_argument("--ano", "-y", type=str, default=None,
                        help="Ano para filtrar no download (ex: 2026)")
    
    args = parser.parse_args()
    
    if args.acao == "info":
        print("=== STATUS DO SISTEMA ===")
        arquivos = [f for f in os.listdir(download_folder) if f.endswith('.xlsx') and not f.endswith('.crdownload')]
        if arquivos:
            print(f"Arquivos disponiveis para importacao:")
            for f in arquivos:
                tamanho = os.path.getsize(os.path.join(download_folder, f))
                print(f"  - {f} ({tamanho} bytes)")
        else:
            print("Nenhum arquivo .xlsx na pasta de downloads")
        
        try:
            cnxn = sqlite3.connect('base_dados.db')
            cursor = cnxn.cursor()
            cursor.execute("SELECT COUNT(*) FROM dados_serpro")
            total = cursor.fetchone()[0]
            cursor.execute("SELECT MIN(ano_abertura), MAX(ano_abertura) FROM dados_serpro")
            range_anos = cursor.fetchone()
            print(f"\nBanco de dados:")
            print(f"  Total registros: {total}")
            print(f"  Range anos: {range_anos[0]} a {range_anos[1]}")
            cursor.close()
            cnxn.close()
        except Exception as e:
            print(f"  Erro ao verificar banco: {e}")
    
    elif args.acao == "baixar":
        baixar_somente(ano=args.ano)
    
    elif args.acao == "importar":
        if args.arquivo:
            importar_excel_para_sqlite(args.arquivo)
        else:
            importar_ultimo_download()
    
    elif args.acao == "completo":
        # Para ciclo completo, usa ano se especificado
        if args.ano:
            # Baixar com ano + importar
            if not baixar_somente(ano=args.ano):
                print("\n✗ Falha no download")
            else:
                importar_ultimo_download()
        else:
            executar_ciclo_completo()
    
    else:
        parser.print_help()
