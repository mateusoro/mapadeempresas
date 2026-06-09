// Visualizador de dados SERPRO - API + static
// Usa better-sqlite3 (acesso direto ao arquivo, sem carregar em memória)
// Suporta banco de 4.9 GB com 21M+ registros via paginação server-side.

const express = require('express');
const Database = require('better-sqlite3');
const path = require('path');
const { Worker } = require('worker_threads');

const app = express();
const PORT = process.env.PORT || 3000;

// Banco de dados: aponta para ../base_dados.db (banco principal do projeto)
const DB_PATH = process.env.DB_PATH || path.join(__dirname, '..', 'base_dados.db');

// Conexão read-only com SQLite. Streaming direto do arquivo -> sem carregar 4.9GB em RAM.
let db;
try {
    db = new Database(DB_PATH, { readonly: true, fileMustExist: true });
    // Em read-only não se pode mudar journal_mode (precisa de escrita). SQLite usa o modo do arquivo.
    console.log(`[OK] Banco conectado (read-only): ${DB_PATH}`);
} catch (err) {
    console.error(`[ERRO] Falha ao abrir banco: ${err.message}`);
    console.error(`       Verifique se o caminho existe: ${DB_PATH}`);
    process.exit(1);
}

// Schema atual (pós-otimização): NÃO tem des_secao
// Colunas: id, ano_abertura, mes_abertura, ano_baixa, mes_baixa,
//          regiao, uf, municipio, natureza_juridica, tipo_situacao,
//          porte, opcao_mei, quantidade
const COLUNAS_ORDENAVEIS = new Set([
    'id', 'ano_abertura', 'mes_abertura', 'ano_baixa', 'mes_baixa',
    'regiao', 'uf', 'municipio', 'natureza_juridica', 'tipo_situacao',
    'porte', 'opcao_mei', 'quantidade'
]);

// Colunas filtráveis (mesmas, exceto id)
const COLUNAS_FILTRAVEIS = new Set([...COLUNAS_ORDENAVEIS].filter(c => c !== 'id'));

// Limite máximo de paginação (proteção)
const MAX_LIMIT = 500;

// Middleware
app.use(express.json());

// ========== HELPERS ==========

function parseIntParam(value, defaultValue) {
    if (value === undefined || value === null || value === '') return defaultValue;
    const n = parseInt(value, 10);
    return Number.isFinite(n) ? n : defaultValue;
}

function parseFilters(filtersJson) {
    // Devolve { whereClause, params } onde whereClause ja vem com 'WHERE ' (ou '' se vazio).
    if (!filtersJson) return { whereClause: '', params: [] };
    let filters;
    try {
        filters = JSON.parse(filtersJson);
    } catch (e) {
        return { whereClause: '', params: [] };
    }
    const conditions = [];
    const params = [];
    for (const [key, value] of Object.entries(filters)) {
        if (!COLUNAS_FILTRAVEIS.has(key)) continue;
        if (value === null || value === undefined || value === '') continue;
        const strValue = String(value);
        if (strValue.includes('|')) {
            const values = strValue.split('|').map(v => v.trim()).filter(Boolean);
            if (values.length > 0) {
                const placeholders = values.map(() => '?').join(',');
                conditions.push(`${key} IN (${placeholders})`);
                values.forEach(v => params.push(v));
            }
        } else {
            conditions.push(`${key} LIKE ?`);
            params.push(`%${strValue}%`);
        }
    }
    const whereClause = conditions.length > 0 ? 'WHERE ' + conditions.join(' AND ') : '';
    return { whereClause, params };
}

function buildOrderBy(sortBy, sortOrder) {
    if (!COLUNAS_ORDENAVEIS.has(sortBy)) return 'ORDER BY id ASC';
    const order = (sortOrder && sortOrder.toUpperCase() === 'DESC') ? 'DESC' : 'ASC';
    return `ORDER BY ${sortBy} ${order}`;
}

// ========== API ROUTES ==========

// Health check
app.get('/api/health', (req, res) => {
    try {
        const count = db.prepare('SELECT COUNT(*) as c FROM dados_serpro').get();
        res.json({
            success: true,
            db_path: DB_PATH,
            total_registros: count.c,
            timestamp: new Date().toISOString()
        });
    } catch (err) {
        res.status(500).json({ success: false, error: err.message });
    }
});

// Listar dados com paginação
app.get('/api/dados', (req, res) => {
    try {
        const page = Math.max(1, parseIntParam(req.query.page, 1));
        const limit = Math.min(MAX_LIMIT, Math.max(1, parseIntParam(req.query.limit, 100)));
        const offset = (page - 1) * limit;
        const sortBy = req.query.sortBy || 'id';
        const sortOrder = req.query.sortOrder || 'ASC';

        const { whereClause, params } = parseFilters(req.query.filters);
        const orderBy = buildOrderBy(sortBy, sortOrder);

        // COUNT(*) no SQLite em 21M registros é rápido (índice/id scan)
        const total = db.prepare(`SELECT COUNT(*) as c FROM dados_serpro ${whereClause}`).get(...params).c;

        const dados = db.prepare(`
            SELECT * FROM dados_serpro
            ${whereClause}
            ${orderBy}
            LIMIT ? OFFSET ?
        `).all(...params, limit, offset);

        res.json({
            success: true,
            data: dados,
            pagination: {
                page,
                limit,
                total,
                totalPages: Math.ceil(total / limit),
                hasNext: offset + limit < total,
                hasPrev: page > 1
            }
        });
    } catch (err) {
        console.error('[ERRO] /api/dados:', err);
        res.status(500).json({ success: false, error: err.message });
    }
});

// NOTA: endpoints de estatística (GROUP BY) foram removidos.
// Em 21M registros, GROUP BY no SQLite sem índices dedicados leva >90s e
// estoura timeout. Para stats pesados, crie uma tabela pré-agregada ou
// use ferramentas de BI externas. Mantemos só listagem paginada + schema.

// Resumo rapido: 4 valores (Ativas, Baixadas, MEI Ativas, MEI Baixadas)
// Acompanha os mesmos filtros de /api/dados. Query agregada (1 SQL) +
// cache em memoria com TTL de 5 min para nao estourar a UI em filtros
// repetidos (a query no OneDrive leva 1-5s).
const STATS_CACHE = new Map(); // key: filtersJson -> { data, ts }
const STATS_CACHE_TTL_MS = 5 * 60 * 1000;

app.get('/api/stats-resumo', (req, res) => {
    try {
        const filtersJson = req.query.filters || '{}';
        const cached = STATS_CACHE.get(filtersJson);
        if (cached && Date.now() - cached.ts < STATS_CACHE_TTL_MS) {
            return res.json({ success: true, data: cached.data, cached: true });
        }

        const { whereClause, params } = parseFilters(filtersJson);

        // Uma unica query com CASE WHEN: 4 SUM em 1 scan so (3x mais rapido que 4).
        const t0 = Date.now();
        const row = db.prepare(`
            SELECT
                COALESCE(SUM(CASE WHEN tipo_situacao='Ativa'   THEN quantidade ELSE 0 END), 0) as ativas,
                COALESCE(SUM(CASE WHEN tipo_situacao='Baixada' THEN quantidade ELSE 0 END), 0) as baixadas,
                COALESCE(SUM(CASE WHEN tipo_situacao='Ativa'   AND opcao_mei='S' THEN quantidade ELSE 0 END), 0) as meiAtivas,
                COALESCE(SUM(CASE WHEN tipo_situacao='Baixada' AND opcao_mei='S' THEN quantidade ELSE 0 END), 0) as meiBaixadas
            FROM dados_serpro
            ${whereClause}
        `).get(...params);
        const t1 = Date.now();

        const data = {
            ativas: row.ativas,
            baixadas: row.baixadas,
            meiAtivas: row.meiAtivas,
            meiBaixadas: row.meiBaixadas
        };

        STATS_CACHE.set(filtersJson, { data, ts: Date.now() });

        res.json({
            success: true,
            data,
            query_ms: t1 - t0,
            cached: false
        });
    } catch (err) {
        console.error('[ERRO] /api/stats-resumo:', err);
        res.status(500).json({ success: false, error: err.message });
    }
});

// Schema da tabela
app.get('/api/colunas', (req, res) => {
    try {
        const colunas = db.prepare("PRAGMA table_info(dados_serpro)").all();
        res.json({ success: true, data: colunas });
    } catch (err) {
        console.error('[ERRO] /api/colunas:', err);
        res.status(500).json({ success: false, error: err.message });
    }
});

// ========== /api/relatorio ==========
// Executor de SELECT arbitrário com 3 proteções:
//   1) Whitelist de keywords (somente SELECT / WITH permitidos; resto é rejeitado)
//   2) Auto-LIMIT 100 (remove qualquer LIMIT do usuário e injeta o nosso)
//   3) Timeout via worker_threads (query roda em thread isolada, é morta se passar do limite)
//
// GET /api/relatorio?q=<SELECT ...>
const RELATORIO_MAX_LIMIT = 100;
const RELATORIO_TIMEOUT_MS = 15_000;

function sanitizeSelect(rawSql) {
    // Recebe a query crua, devolve { ok, sql, error }
    if (typeof rawSql !== 'string' || !rawSql.trim()) {
        return { ok: false, error: 'Query vazia. Use ?q=<SELECT ...>' };
    }

    // Tamanho máximo razoável (10KB evita payloads absurdos)
    if (rawSql.length > 10_000) {
        return { ok: false, error: 'Query muito longa (máx 10KB)' };
    }

    // Remove /* ... */ e -- ... (com cuidado pra não comer conteúdo de string)
    // Estratégia: varre char a char, alterna estados string/ident.
    let cleaned = '';
    let i = 0;
    const n = rawSql.length;
    let inSingle = false, inDouble = false, inBracket = false;
    while (i < n) {
        const c = rawSql[i], nx = rawSql[i + 1];
        if (!inSingle && !inDouble && !inBracket && c === '-' && nx === '-') {
            // comentário até fim da linha
            while (i < n && rawSql[i] !== '\n') i++;
            continue;
        }
        if (!inSingle && !inDouble && !inBracket && c === '/' && nx === '*') {
            i += 2;
            while (i < n && !(rawSql[i] === '*' && rawSql[i + 1] === '/')) i++;
            i += 2;
            continue;
        }
        if (c === "'" && !inDouble && !inBracket) {
            // string single-quote: copiar até próximo ' não escapado ('' é escape)
            cleaned += c; i++;
            while (i < n) {
                if (rawSql[i] === "'" && rawSql[i + 1] === "'") {
                    // '' = aspas escapadas dentro da string
                    cleaned += "''"; i += 2; continue;
                }
                if (rawSql[i] === "'") {
                    cleaned += c; i++; break;
                }
                cleaned += rawSql[i]; i++;
            }
            continue;
        }
        if (c === '"' && !inSingle && !inBracket) {
            cleaned += c; i++;
            while (i < n) {
                if (rawSql[i] === '"' && rawSql[i + 1] === '"') {
                    cleaned += '""'; i += 2; continue;
                }
                if (rawSql[i] === '"') {
                    cleaned += c; i++; break;
                }
                cleaned += rawSql[i]; i++;
            }
            continue;
        }
        if (c === '[' && !inSingle && !inDouble) { inBracket = true; cleaned += c; i++; continue; }
        if (c === ']' && inBracket) { inBracket = false; cleaned += c; i++; continue; }
        cleaned += c; i++;
    }

    const stripped = cleaned.trim().replace(/;\s*$/, '');

    // Rejeita múltiplas sentenças (vírgula-eu-sei mas `;` no meio é suspeito)
    // Como não há `;` restantes (removidos acima), qualquer `;` aqui significa que havia mais.
    // Já cortamos trailing, mas e `SELECT 1; SELECT 2` ? checa se tinha `;` antes do strip.
    // Heurística: se a raw original tinha `;` e o stripped não termina com nada após, é multi.
    // Mais simples: rejeita qualquer `;` na stripped.
    if (/;/.test(stripped)) {
        return { ok: false, error: 'Múltiplas sentenças não são permitidas (apenas 1 SELECT)' };
    }

    // Primeira keyword significativa
    const headMatch = stripped.match(/^(\s*(?:--[^\n]*\n|\/\*[\s\S]*?\*\/\s)*)*(WITH|SELECT)\b/i);
    if (!headMatch) {
        return { ok: false, error: 'Apenas queries SELECT (ou WITH ... SELECT) são permitidas' };
    }

    // Whitelist de keywords perigosas (case-insensitive, palavra inteira)
    const forbidden = /\b(ATTACH|DETACH|PRAGMA|LOAD_EXTENSION|VACUUM|REINDEX|UPDATE|DELETE|INSERT|REPLACE|DROP|ALTER|CREATE|TRUNCATE|RENAME|GRANT|REVOKE)\b/i;
    const fmatch = stripped.match(forbidden);
    if (fmatch) {
        return { ok: false, error: `Keyword proibida: ${fmatch[1].toUpperCase()}` };
    }

    // Auto-LIMIT: remove qualquer LIMIT existente (com OFFSET opcional) e injeta o nosso
    // Suporta: LIMIT <n>, LIMIT <n> OFFSET <m>, LIMIT <m>, <n>  (variante "offset, count")
    let withLimit = stripped
        .replace(/\bLIMIT\s+\d+\s*,\s*\d+\b/gi, '')           // LIMIT m, n  (offset, count)
        .replace(/\bLIMIT\s+\d+(\s+OFFSET\s+\d+)?\b/gi, '');   // LIMIT n [OFFSET m]
    const finalSql = withLimit.trim() + `\nLIMIT ${RELATORIO_MAX_LIMIT}`;

    return { ok: true, sql: finalSql };
}

function runRelatorioWorker(dbPath, sql, timeoutMs) {
    // Roda a query num worker thread. Resolve:
    //   { ok: true, rows, columns, elapsed_ms }
    //   { ok: false, error, timed_out }
    return new Promise((resolve) => {
        const worker = new Worker(path.join(__dirname, 'relatorio-worker.js'), {
            workerData: { dbPath, sql, timeoutMs }
        });
        let settled = false;
        const t0 = Date.now();

        const finish = (result) => {
            if (settled) return;
            settled = true;
            clearTimeout(killer);
            worker.terminate().catch(() => {});
            resolve(result);
        };

        const killer = setTimeout(() => {
            finish({ ok: false, error: `Timeout: query excedeu ${timeoutMs}ms`, timed_out: true, elapsed_ms: Date.now() - t0 });
        }, timeoutMs);

        worker.on('message', (msg) => {
            if (msg.ok) {
                finish({ ok: true, rows: msg.rows, columns: msg.columns, elapsed_ms: msg.elapsed_ms });
            } else {
                finish({ ok: false, error: msg.error, elapsed_ms: msg.elapsed_ms || (Date.now() - t0) });
            }
        });
        worker.on('error', (err) => {
            finish({ ok: false, error: `Worker erro: ${err.message}`, elapsed_ms: Date.now() - t0 });
        });
        worker.on('exit', (code) => {
            if (!settled && code !== 0) {
                finish({ ok: false, error: `Worker saiu com código ${code}`, elapsed_ms: Date.now() - t0 });
            }
        });
    });
}

app.get('/api/relatorio', async (req, res) => {
    const raw = req.query.q;
    const t0 = Date.now();
    try {
        const sanitized = sanitizeSelect(raw);
        if (!sanitized.ok) {
            return res.status(400).json({ success: false, error: sanitized.error });
        }

        const result = await runRelatorioWorker(DB_PATH, sanitized.sql, RELATORIO_TIMEOUT_MS);

        if (!result.ok) {
            const status = result.timed_out ? 408 : 400;
            return res.status(status).json({
                success: false,
                error: result.error,
                timed_out: !!result.timed_out,
                sql_aplicado: sanitized.sql,
                elapsed_ms: result.elapsed_ms
            });
        }

        res.json({
            success: true,
            data: {
                rows: result.rows,
                columns: result.columns,
                row_count: result.rows.length,
                max_rows: RELATORIO_MAX_LIMIT,
                sql_aplicado: sanitized.sql,
                query_ms: result.elapsed_ms,
                total_ms: Date.now() - t0
            }
        });
    } catch (err) {
        console.error('[ERRO] /api/relatorio:', err);
        res.status(500).json({ success: false, error: err.message });
    }
});

// ========== STATIC FILES ==========

// Rota dedicada para /relatorio (resolve antes do static, que não auto-resolve .html em /relatorio)
app.get('/relatorio', (req, res) => {
    res.sendFile(path.join(__dirname, 'public', 'relatorio.html'));
});

app.use(express.static(path.join(__dirname, 'public')));

// 404 para rotas /api/ inexistentes (antes do fallback SPA).
// Express 4 não suporta '/api/*' em app.use; checamos manualmente.
app.use((req, res, next) => {
    if (req.path.startsWith('/api/')) {
        return res.status(404).json({ success: false, error: `Endpoint não encontrado: ${req.path}` });
    }
    next();
});

// Fallback SPA -> index.html (apenas para rotas não-/api/)
app.get('*', (req, res) => {
    res.sendFile(path.join(__dirname, 'public', 'index.html'));
});

// Iniciar servidor
app.listen(PORT, () => {
    console.log(`\n[SERVIDOR] http://localhost:${PORT}`);
    console.log(`[API]      http://localhost:${PORT}/api/health`);
    console.log(`[BANCO]    ${DB_PATH}\n`);
});
