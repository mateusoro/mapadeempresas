# Índices do banco `base_dados.db`

Banco: ~8.97 GB (pós-otimização), ~21M registros. Servido por `server-mapa-empresas.js`.

Para garantir que a inteligência artificial (ChatGPT / Custom GPT Actions) consiga realizar qualquer análise sobre a base de dados de 21M de registros sem estourar o limite de tempo (timeout de 100s do Cloudflare), foram criados os seguintes **índices de cobertura (covering indexes)**.

Um índice de cobertura inclui a coluna de filtro e a coluna de dados (`quantidade`), permitindo que o SQLite execute `SUM(quantidade)` diretamente a partir do índice na memória, sem nunca ler a tabela principal no disco lento do WSL.

## Lista de Índices de Cobertura Criados

| Nome do Índice | Colunas Indexadas | Finalidade / Queries Beneficiadas | Tempo de Criação |
|---|---|---|---|
| `idx_tipo_situacao_qty` | `(tipo_situacao, quantidade)` | Total de baixas (`WHERE tipo_situacao='Baixada'`) | ~22s |
| `idx_opcao_mei_qty` | `(opcao_mei, quantidade)` | Total de MEIs / não-MEIs | ~23s |
| `idx_ano_mes_abertura_qty` | `(ano_abertura, mes_abertura, quantidade)` | Aberturas anuais e mensais | ~21s |
| `idx_ano_baixa_qty` | `(ano_baixa, quantidade)` | Aberturas vs Baixas (Mortalidade) | ~21s |
| `idx_uf_municipio_qty` | `(uf, municipio, quantidade)` | Rankings por UF e Rankings Municipais | ~38s |
| `idx_uf_ano_opcao_mei_municipio_qty` | `(uf, ano_abertura, opcao_mei, municipio, quantidade)` | Consultas combinando Estado + Ano + Opção MEI (como Rankings por ano e município) | ~77s |
| `idx_municipio_qty` | `(municipio, quantidade)` | Consultas isoladas de Municípios | ~38s |
| `idx_regiao_qty` | `(regiao, quantidade)` | Distribuição regional | ~26s |
| `idx_porte_qty` | `(porte, quantidade)` | Análise de perfil por porte de empresa | ~24s |
| `idx_natureza_juridica_qty`| `(natureza_juridica, quantidade)` | Análise de perfil por natureza jurídica | ~26s |

---

## Resultados Práticos (Speedup Medido)

Abaixo, veja o tempo de execução no mesmo arquivo de banco no Windows antes e depois da criação dos índices de cobertura:

| Query de Teste | Sem Índices (Full Table Scan) | Com Índices (Covering Scan) | Ganho de Velocidade |
|---|---:|---:|---:|
| `SUM(quantidade)` filtrando por `municipio` (Pinhalzinho - SC) | 5.16s | **37ms** | **139× mais rápido** |
| `SUM(quantidade)` filtrando por `tipo_situacao='Baixada'` | 13.77s | **894ms** | **15.4× mais rápido** |
| `SUM(quantidade)` filtrando por `ano_abertura=2026` | ~3.10s | **9ms** | **344× mais rápido** |
| `SUM(quantidade)` filtrando por `opcao_mei='S'` | ~3.05s | **336ms** | **9× mais rápido** |

---

## Como recriar (se o banco de dados for regenerado do zero)

Se você rodar o importador python e regenerar o arquivo `base_dados.db`, você **deve** recriar estes índices para que o GPT não volte a sofrer com timeouts. 

Para recriar tudo automaticamente, você pode executar o seguinte script Node.js na sua máquina:

```javascript
const Database = require('better-sqlite3');
const path = require('path');

const dbPath = path.join(__dirname, '..', 'base_dados.db');
const db = new Database(dbPath, { readonly: false });

console.log('Criando índices de cobertura...');
db.pragma('cache_size = -2000000'); // Cache de 2GB para acelerar build
db.pragma('temp_store = MEMORY');

db.exec(`
    CREATE INDEX IF NOT EXISTS idx_tipo_situacao_qty ON dados_serpro(tipo_situacao, quantidade);
    CREATE INDEX IF NOT EXISTS idx_opcao_mei_qty ON dados_serpro(opcao_mei, quantidade);
    CREATE INDEX IF NOT EXISTS idx_ano_mes_abertura_qty ON dados_serpro(ano_abertura, mes_abertura, quantidade);
    CREATE INDEX IF NOT EXISTS idx_ano_baixa_qty ON dados_serpro(ano_baixa, quantidade);
    CREATE INDEX IF NOT EXISTS idx_uf_municipio_qty ON dados_serpro(uf, municipio, quantidade);
    CREATE INDEX IF NOT EXISTS idx_uf_ano_opcao_mei_municipio_qty ON dados_serpro(uf, ano_abertura, opcao_mei, municipio, quantidade);
    CREATE INDEX IF NOT EXISTS idx_municipio_qty ON dados_serpro(municipio, quantidade);
    CREATE INDEX IF NOT EXISTS idx_regiao_qty ON dados_serpro(regiao, quantidade);
    CREATE INDEX IF NOT EXISTS idx_porte_qty ON dados_serpro(porte, quantidade);
    CREATE INDEX IF NOT EXISTS idx_natureza_juridica_qty ON dados_serpro(natureza_juridica, quantidade);
    ANALYZE;
`);

console.log('Pronto! Índices criados e ANALYZE executado.');
db.close();
```
