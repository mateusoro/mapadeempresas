"""
otimizar_texto.py - Otimizacao textual das colunas do banco SERPRO.

Apos a importacao mensal, roda este script para compactar colunas de texto:

  mes_abertura  : 'Janeiro'..'Dezembro'   -> 1..12 (INTEGER)
  mes_baixa     : 'Janeiro'..'Dezembro'   -> 1..12 (INTEGER)  /  '-' -> NULL
  opcao_mei     : 'MEI' / 'Nao-MEI'       -> 'S' / 'N'
  porte         : 'Microempresa'          -> 'ME'
                  'Empresa de pequeno porte' -> 'EPP'
                  'Outras'                -> 'OUTRAS' (ou mantem)
  natureza_juridica : 'Empresario Individual' -> 'EI'
                      'Sociedade Limitada'    -> 'LTDA'
                      (outras: mantem)

Uso:
    python otimizar_texto.py            # roda no base_dados.db
    python otimizar_texto.py --dry-run  # mostra o que faria, sem alterar
    python otimizar_texto.py --no-backup # pula o backup
"""
import os
import sys
import sqlite3
import shutil
import time
from datetime import datetime

# Flush forcado para que prints aparecam mesmo em background/pipe
import functools
print = functools.partial(print, flush=True)

SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
DB = os.path.join(SCRIPT_DIR, 'base_dados.db')

# Mapeamentos - chaves sao EXATAMENTE como aparecem no banco (Title Case)
# A funcao otimizar_lookup compara com LOWER() para tolerancia.
MESES_PT_NUM = {
    'Janeiro': 1,
    'Fevereiro': 2,
    'Mar\xe7o': 3,      # Março (com ç)
    'Abril': 4,
    'Maio': 5,
    'Junho': 6,
    'Julho': 7,
    'Agosto': 8,
    'Setembro': 9,
    'Outubro': 10,
    'Novembro': 11,
    'Dezembro': 12,
}

PORTE_MAP = {
    'Microempresa': 'ME',
    'Empresa de pequeno porte': 'EPP',
    'Outras': 'OUTRAS',
}

NATUREZA_MAP = {
    'Empres\xe1rio Individual': 'EI',   # empresário (com á)
    'Sociedade Limitada': 'LTDA',
}

OPCAO_MEI_MAP = {
    'MEI': 'S',
    'N\xe3o-MEI': 'N',                   # não-MEI (com ã)
}


def normaliza_texto(s):
    """Lowercase + remove acentos + trim."""
    if s is None:
        return ''
    s = str(s).strip().lower()
    repl = {
        '\xe1': 'a', '\xe0': 'a', '\xe2': 'a', '\xe3': 'a', '\xe4': 'a', '\xe5': 'a',
        '\xe9': 'e', '\xe8': 'e', '\xea': 'e', '\xeb': 'e',
        '\xed': 'i', '\xec': 'i', '\xee': 'i', '\xef': 'i',
        '\xf3': 'o', '\xf2': 'o', '\xf4': 'o', '\xf5': 'o', '\xf6': 'o',
        '\xfa': 'u', '\xf9': 'u', '\xfb': 'u', '\xfc': 'u',
        '\xe7': 'c', '\xc7': 'C',
        '\xed': 'i',  # i com acento
    }
    for k, v in repl.items():
        s = s.replace(k, v)
    return s


def parse_args():
    dry_run = '--dry-run' in sys.argv
    no_backup = '--no-backup' in sys.argv
    return dry_run, no_backup


def fazer_backup():
    """Cria copia de seguranca com timestamp."""
    ts = datetime.now().strftime('%Y%m%d_%H%M%S')
    backup = os.path.join(SCRIPT_DIR, f'base_dados_pre_otimtexto_{ts}.db')
    print(f"[BACKUP] Copiando {DB} -> {backup}")
    shutil.copy2(DB, backup)
    size_gb = os.path.getsize(backup) / 1e9
    print(f"[BACKUP] OK - {size_gb:.2f} GB")
    return backup


def contagem_antes_depois(cnxn, sql, label):
    """Helper para mostrar distribuicao de valores."""
    cur = cnxn.cursor()
    cur.execute(sql)
    rows = cur.fetchall()
    print(f"  {label}: {len(rows)} valores distintos")
    for r in rows[:8]:
        print(f"    {r[0]!r}: {r[1]:,}".replace(',', '.'))
    if len(rows) > 8:
        print(f"    ... (+{len(rows) - 8} outros)")


def otimizar_mes(cnxn, coluna, dry_run=False):
    """Converte 'Janeiro'..'Dezembro' -> 1..12 e '-' -> NULL."""
    cur = cnxn.cursor()
    total_alt = 0
    for nome_mes, num in MESES_PT_NUM.items():
        # Compara com LOWER para tolerar capitalizacao diferente.
        # Para mes, os valores estao sempre em Title Case, entao LOWER eh desnecessario,
        # mas eh defensivo.
        if dry_run:
            cur.execute(
                f"SELECT COUNT(*) FROM dados_serpro WHERE {coluna} = ?",
                (nome_mes,)
            )
            n = cur.fetchone()[0]
            if n:
                print(f"    [DRY] {coluna} = '{nome_mes}' -> {num}: {n:,} linhas".replace(',', '.'))
            total_alt += n
        else:
            cur.execute(
                f"UPDATE dados_serpro SET {coluna} = ? WHERE {coluna} = ?",
                (num, nome_mes)
            )
            total_alt += cur.rowcount
    # '-' -> NULL em mes_baixa
    if coluna == 'mes_baixa':
        if dry_run:
            cur.execute(f"SELECT COUNT(*) FROM dados_serpro WHERE {coluna} = '-'")
            n = cur.fetchone()[0]
            print(f"    [DRY] {coluna} = '-' -> NULL: {n:,} linhas".replace(',', '.'))
            total_alt += n
        else:
            cur.execute(
                f"UPDATE dados_serpro SET {coluna} = NULL WHERE {coluna} = '-'"
            )
            total_alt += cur.rowcount
    if not dry_run:
        cnxn.commit()  # checkpoint: persiste o progresso da coluna
    return total_alt


def otimizar_lookup(cnxn, coluna, mapa, dry_run=False):
    """Aplica mapa de traducao: 'valor original' -> 'valor otimizado'."""
    cur = cnxn.cursor()
    total_alt = 0
    for original, otimizado in mapa.items():
        if dry_run:
            cur.execute(
                f"SELECT COUNT(*) FROM dados_serpro WHERE {coluna} = ?",
                (original,)
            )
            n = cur.fetchone()[0]
            if n:
                print(f"    [DRY] {coluna} = '{original}' -> '{otimizado}': {n:,} linhas".replace(',', '.'))
            total_alt += n
        else:
            cur.execute(
                f"UPDATE dados_serpro SET {coluna} = ? WHERE {coluna} = ?",
                (otimizado, original)
            )
            total_alt += cur.rowcount
    if not dry_run:
        cnxn.commit()  # checkpoint: persiste o progresso da coluna
    return total_alt


def main():
    dry_run, no_backup = parse_args()

    print("="*70)
    print("OTIMIZACAO TEXTUAL DO BANCO SERPRO")
    print("="*70)
    print(f"Banco: {DB}")
    if not os.path.exists(DB):
        print(f"ERRO: banco nao encontrado")
        return 1
    if dry_run:
        print("MODO: DRY-RUN (nenhuma alteracao sera feita)")
    else:
        print("MODO: APLICAR (alteracoes serao commitadas)")
    if no_backup:
        print("Backup: PULADO (--no-backup)")
    print()

    if not dry_run and not no_backup:
        fazer_backup()

    cnxn = sqlite3.connect(DB)
    cur = cnxn.cursor()

    # =====================
    # ANTES
    # =====================
    print("\n[BEFORE] Estado atual:")
    contagem_antes_depois(cnxn, "SELECT mes_abertura, COUNT(*) FROM dados_serpro GROUP BY mes_abertura", "mes_abertura")
    contagem_antes_depois(cnxn, "SELECT mes_baixa, COUNT(*) FROM dados_serpro GROUP BY mes_baixa", "mes_baixa")
    contagem_antes_depois(cnxn, "SELECT opcao_mei, COUNT(*) FROM dados_serpro GROUP BY opcao_mei", "opcao_mei")
    contagem_antes_depois(cnxn, "SELECT porte, COUNT(*) FROM dados_serpro GROUP BY porte", "porte")
    contagem_antes_depois(cnxn, "SELECT natureza_juridica, COUNT(*) FROM dados_serpro GROUP BY natureza_juridica", "natureza_juridica")

    t0 = time.time()

    # =====================
    # UPDATES
    # =====================
    if not dry_run:
        # Sem transacao unica: cada etapa faz commit separado,
        # assim se algo falhar, as etapas anteriores ja estao persistidas.
        pass

    print("\n[1/5] mes_abertura: 'Janeiro'..'Dezembro' -> 1..12")
    n = otimizar_mes(cnxn, 'mes_abertura', dry_run)
    print(f"    Total: {n:,} linhas alteradas".replace(',', '.'))

    print("\n[2/5] mes_baixa: 'Janeiro'..'Dezembro' -> 1..12 | '-' -> NULL")
    n = otimizar_mes(cnxn, 'mes_baixa', dry_run)
    print(f"    Total: {n:,} linhas alteradas".replace(',', '.'))

    print("\n[3/5] opcao_mei: 'MEI' -> 'S' | 'Nao-MEI' -> 'N'")
    n = otimizar_lookup(cnxn, 'opcao_mei', OPCAO_MEI_MAP, dry_run)
    print(f"    Total: {n:,} linhas alteradas".replace(',', '.'))

    print("\n[4/5] porte: 'Microempresa' -> 'ME' | 'Empresa de pequeno porte' -> 'EPP' | 'Outras' -> 'OUTRAS'")
    n = otimizar_lookup(cnxn, 'porte', PORTE_MAP, dry_run)
    print(f"    Total: {n:,} linhas alteradas".replace(',', '.'))

    print("\n[5/5] natureza_juridica: 'Empresario Individual' -> 'EI' | 'Sociedade Limitada' -> 'LTDA' (outras mantidas)")
    n = otimizar_lookup(cnxn, 'natureza_juridica', NATUREZA_MAP, dry_run)
    print(f"    Total: {n:,} linhas alteradas".replace(',', '.'))

    if not dry_run:
        # Cada otimizar_*() ja fez commit por coluna. Nada a fazer aqui.
        # AVISO: VACUUM eh omitido por seguranca (pode corromper banco se interrompido).
        # Para compactar o arquivo, rode manualmente apos confirmar que tudo esta OK:
        #   python -c "import sqlite3; c=sqlite3.connect('base_dados.db'); c.execute('VACUUM')"
        pass
    else:
        cnxn.rollback()

    # =====================
    # DEPOIS
    # =====================
    print("\n[AFTER] Estado final:")
    contagem_antes_depois(cnxn, "SELECT mes_abertura, COUNT(*) FROM dados_serpro GROUP BY mes_abertura", "mes_abertura")
    contagem_antes_depois(cnxn, "SELECT mes_baixa, COUNT(*) FROM dados_serpro GROUP BY mes_baixa", "mes_baixa")
    contagem_antes_depois(cnxn, "SELECT opcao_mei, COUNT(*) FROM dados_serpro GROUP BY opcao_mei", "opcao_mei")
    contagem_antes_depois(cnxn, "SELECT porte, COUNT(*) FROM dados_serpro GROUP BY porte", "porte")
    contagem_antes_depois(cnxn, "SELECT natureza_juridica, COUNT(*) FROM dados_serpro GROUP BY natureza_juridica", "natureza_juridica")

    elapsed = time.time() - t0
    size_gb = os.path.getsize(DB) / 1e9
    print(f"\n[TEMPO] {elapsed:.1f}s")
    print(f"[TAMANHO] {size_gb:.2f} GB")
    print(f"[MODO] {'DRY-RUN (nada alterado)' if dry_run else 'APLICADO'}")

    cnxn.close()
    return 0


if __name__ == '__main__':
    sys.exit(main())
