# Índices do banco `base_dados.db`

## idx_mei_situacao_uf

```sql
CREATE INDEX idx_mei_situacao_uf ON dados_serpro(opcao_mei, tipo_situacao, uf);
```

- Criado em: 2026-06-09
- Tempo de criação: 70.8s
- Tamanho adicionado: ~220 MB
- Tamanho do banco antes: 4.905 GB
- Tamanho do banco depois: 5.148 GB

### Speedup medido (21.065.344 registros)

| Query | Antes | Depois | Speedup |
|---|---:|---:|---:|
| `COUNT(*)` com `opcao_mei='S' AND tipo_situacao='Ativa'` | 3.01s | 36ms | **83×** |
| `SUM(quantidade)` mesmo filtro | 3.03s | 710ms | 4.3× |
| `GROUP BY uf` mesmo filtro | 3.31s | 671ms | 4.9× |

### Como recriar (se o banco for regenerado)

```javascript
const Database = require('better-sqlite3');
const db = new Database('../base_dados.db', { readonly: false });
db.exec('CREATE INDEX IF NOT EXISTS idx_mei_situacao_uf ON dados_serpro(opcao_mei, tipo_situacao, uf)');
db.close();
```

### Nota

- O banco é read-only quando servido pelo `server-mapa-empresas.js`
- Para criar índice é preciso abrir em read-write (parar o server antes)
- O índice ajuda especialmente queries MEI (opcao_mei='S'); para outras agregações, criar índices adicionais conforme demanda
