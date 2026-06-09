# Índices do banco `base_dados.db`

Banco: ~5.5 GB, ~21M registros. Servido por `server-mapa-empresas.js`.

## idx_mei_situacao_uf

```sql
CREATE INDEX idx_mei_situacao_uf ON dados_serpro(opcao_mei, tipo_situacao, uf);
```

- Criado em: 2026-06-09
- Tempo de criação: 70.8s
- Tamanho adicionado: ~220 MB
- Banco: 4.57 GB → 4.91 GB

### Speedup medido

| Query | Antes | Depois | Speedup |
|---|---:|---:|---:|
| `COUNT(*)` com `opcao_mei='S' AND tipo_situacao='Ativa'` | 3.01s | 36ms | **83×** |
| `SUM(quantidade)` mesmo filtro | 3.03s | 710ms | 4.3× |
| `GROUP BY uf` mesmo filtro | 3.31s | 671ms | 4.9× |

## idx_situacao_mei

```sql
CREATE INDEX idx_situacao_mei ON dados_serpro(tipo_situacao, opcao_mei);
```

- Criado em: 2026-06-09
- Tempo de criação: 14.9s
- Tamanho adicionado: ~385 MB
- Banco: 5.15 GB → 5.53 GB
- **Requer `ANALYZE`** após criação para o query planner usar (rode automaticamente na primeira conexão read-write)

### Speedup medido (após ANALYZE)

| Query | Antes (scan) | Depois | Plano |
|---|---:|---:|---|
| `COUNT(*)` com `tipo_situacao='Ativa'` | 1.71s | **125ms** | idx_situacao_mei (13×) |
| `SUM(quantidade)` mesmo filtro | 1.55s | 1.7s | idx_situacao_mei (mantém) |
| `SUM(quantidade)` `tipo_situacao='Ativa' AND opcao_mei='S'` | timeout | 616ms | idx_situacao_mei |

## Como recriar (se o banco for regenerado)

```javascript
const Database = require('better-sqlite3');
const db = new Database('../base_dados.db', { readonly: false });
db.exec('CREATE INDEX IF NOT EXISTS idx_mei_situacao_uf ON dados_serpro(opcao_mei, tipo_situacao, uf)');
db.exec('CREATE INDEX IF NOT EXISTS idx_situacao_mei  ON dados_serpro(tipo_situacao, opcao_mei)');
db.exec('ANALYZE'); // crucial para o query planner usar os indices
db.close();
```

## Cache de stats (server)

Endpoint `/api/stats-resumo` faz cache em memória (TTL 5 min) por filtro. Para 21M registros no OneDrive, a query agregada com CASE WHEN leva 1.7-5.4s na primeira chamada, depois 2-3ms (cache hit).

## Nota

- O banco é read-only quando servido pelo `server-mapa-empresas.js`
- Para criar índices/rodar ANALYZE: parar o server, abrir DB em read-write, criar, ANALYZE, fechar, reiniciar
- Cada novo mês importado pelo `exportador_dados_serpro.py` adiciona ~150k registros; índices continuam válidos
