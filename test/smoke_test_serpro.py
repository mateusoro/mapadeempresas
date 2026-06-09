"""
Smoke Test - SERPRO Viewer
Baseado em estatisticas_redesim_resumido.py
"""
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
import time
import os
import subprocess

# Config
SERPRO_URL = "http://localhost:3000"
LOG_FILE = r"C:\Users\Administrador\OneDrive\Área de Trabalho\Mateus\Desenvolvimento\ExtraçãoDados\smoke_test.log"
SERVER_SCRIPT = r"C:\Users\Administrador\OneDrive\Área de Trabalho\Mateus\Desenvolvimento\MAPA DE EMPRESAS\serpro-viewer\server-mapa-empresas.js"
SERVER_PORT = 3000
SERVER_WAIT = 8  # segundos para esperar antes de iniciar o Chrome

def log(msg):
    """Log para arquivo e console"""
    timestamp = time.strftime("%H:%M:%S")
    line = f"[{timestamp}] {msg}"
    print(line)
    with open(LOG_FILE, 'a', encoding='utf-8') as f:
        f.write(line + "\n")

def kill_port(port):
    """Mate qualquer processo usando a porta especificada"""
    log(f"   Matando processo na porta {port}...")
    try:
        result = subprocess.run(
            f'netstat -ano | findstr :{port}',
            shell=True, capture_output=True, text=True
        )
        lines = result.stdout.strip().split('\n')
        for line in lines:
            if 'LISTENING' in line:
                parts = line.split()
                for p in parts:
                    if p.isdigit() and int(p) > 0:
                        pid = p
                        break
                else:
                    continue
                log(f"   PID {pid} encontrado, matando...")
                subprocess.run(f'taskkill /F /PID {pid}', shell=True, capture_output=True)
        log("   Porta liberada OK")
    except Exception as e:
        log(f"   [AVISO] Erro ao matar processo: {e}")

def start_server():
    """Inicia o servidor Node.js em background"""
    log("   Iniciando servidor...")
    try:
        subprocess.Popen(
            ['node', SERVER_SCRIPT],
            cwd=os.path.dirname(SERVER_SCRIPT),
            shell=True,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP
        )
        log("   Servidor iniciado OK")
    except Exception as e:
        log(f"   [ERRO] Falha ao iniciar servidor: {e}")

def init_driver():
    """Inicializa Chrome como no script original"""
    options = webdriver.ChromeOptions()
    # options.add_argument("--headless")  # testando sem headless
    driver = webdriver.Chrome(options=options)
    return driver

def main():
    log("=" * 60)
    log("SMOKE TEST - SERPRO Viewer")
    log("=" * 60)

    driver = None
    try:
        # 0. Parar servidor existente e iniciar novamente
        log("0. Preparando servidor...")
        kill_port(SERVER_PORT)
        time.sleep(1)
        start_server()
        log(f"   Aguardando {SERVER_WAIT} segundos para servidor inicializar...")
        time.sleep(SERVER_WAIT)

        # 1. Abrir Chrome
        log("1. Abrindo Chrome...")
        driver = init_driver()
        log("   Chrome aberto OK")

        # 2. Navegar para URL
        log("2. Navegando para http://localhost:3000 ...")
        driver.get(SERPRO_URL)
        log(f"   URL atual: {driver.current_url}")
        log(f"   Título: {driver.title}")

        # 3. Aguardar carregamento
        log("3. Aguardando 5 segundos...")
        time.sleep(5)

        # 4. Verificar elementos da página
        log("4. Verificando elementos...")

        # Procurar sidebar
        try:
            sidebar = driver.find_element(By.CLASS_NAME, "sidebar")
            log(f"   [OK] Sidebar: {sidebar.is_displayed()}")
        except Exception as e:
            log(f"   [ERRO] Sidebar: {e}")

        # Procurar nav-item
        try:
            nav_itens = driver.find_elements(By.CLASS_NAME, "nav-item")
            log(f"   Nav items encontrados: {len(nav_itens)}")
            for item in nav_itens[:5]:
                log(f"      - {item.text.strip()}")
        except Exception as e:
            log(f"   [ERRO] Nav items: {e}")

        # 5. Verificar se dados carregaram
        log("5. Verificando dados...")

        # Stats cards
        try:
            total = driver.find_element(By.ID, "totalEmpresas")
            log(f"   totalEmpresas: '{total.text}'")
        except Exception as e:
            log(f"   [ERRO] totalEmpresas: {e}")

        # Tabela
        try:
            tbody = driver.find_element(By.ID, "tableBody")
            rows = tbody.find_elements(By.TAG_NAME, "tr")
            log(f"   Linhas na tabela: {len(rows)}")

            if rows:
                log("   Primeiras 3 linhas:")
                for i, row in enumerate(rows[:3]):
                    cells = row.find_elements(By.TAG_NAME, "td")
                    if cells:
                        cell_text = [c.text[:20] for c in cells[:5]]
                        log(f"      Row {i+1}: {cell_text}")
        except Exception as e:
            log(f"   [ERRO] Tabela: {e}")

        # 6. Clicar em Estatísticas
        log("6. Clicando em Estatísticas...")
        try:
            estatisticas = driver.find_element(By.CSS_SELECTOR, '[data-page="estatisticas"]')
            estatisticas.click()
            log("   Clicou OK")
            time.sleep(10)  # API demora ~3s, esperar 10s para garantir carregamento completo

            # Verificar page-estatisticas
            page_estat = driver.find_element(By.ID, "page-estatisticas")
            log(f"   page-estatisticas displayed: {page_estat.is_displayed()}")

        except Exception as e:
            log(f"   [ERRO] Clique Estatísticas: {e}")

        # 7. Verificar cards MEI
        log("7. Verificando cards MEI...")
        try:
            mei_ativos = driver.find_element(By.ID, "meiAtivos")
            mei_baixados = driver.find_element(By.ID, "meiBaixados")
            mei_total = driver.find_element(By.ID, "meiTotal")

            log(f"   MEI Ativos: '{mei_ativos.text}'")
            log(f"   MEI Baixados: '{mei_baixados.text}'")
            log(f"   MEI Total: '{mei_total.text}'")
        except Exception as e:
            log(f"   [ERRO] Cards MEI: {e}")

        # 8. Verificar tabela evolução anual
        log("8. Verificando tabela evolução anual...")
        try:
            evolucao_tbody = driver.find_element(By.ID, "tableBodyEvolucaoAnual")
            evolucao_rows = evolucao_tbody.find_elements(By.TAG_NAME, "tr")
            log(f"   Linhas na evolução: {len(evolucao_rows)}")

            if evolucao_rows:
                log("   Primeiras 5 linhas:")
                for i, row in enumerate(evolucao_rows[:5]):
                    cells = row.find_elements(By.TAG_NAME, "td")
                    if cells:
                        cell_text = [c.text[:15] for c in cells]
                        log(f"      Row {i+1}: {cell_text}")
        except Exception as e:
            log(f"   [ERRO] Tabela evolução: {e}")

        log("=" * 60)
        log("TESTE COMPLETO")
        log("=" * 60)

    except Exception as e:
        log(f"[ERRO GERAL] {e}")
        import traceback
        traceback.print_exc()

    finally:
        if driver:
            log("Fechando Chrome...")
            driver.quit()

if __name__ == "__main__":
    # Limpar log anterior
    if os.path.exists(LOG_FILE):
        os.remove(LOG_FILE)
    main()