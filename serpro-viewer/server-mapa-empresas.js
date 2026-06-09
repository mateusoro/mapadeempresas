// Visualizador de dados SERPRO - API + static
// Usa better-sqlite3 (acesso direto ao arquivo, sem carregar em memória)
// Suporta banco de 4.9 GB com 21M+ registros via paginação server-side.

const express = require('express');
const Database = require('better-sqlite3');
const path = require('path');

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
    if (!filtersJson) return { where: '1=1', params: [] };
    let filters;
    try {
        filters = JSON.parse(filtersJson);
    } catch (e) {
        return { where: '1=1', params: [] };
    }
    const conditions = [];
    const params = {};
    for (const [key, value] of Object.entries(filters)) {
        if (!COLUNAS_FILTRAVEIS.has(key)) continue;
        if (value === null || value === undefined || value === '') continue;
        const strValue = String(value);
        // Filtro checkbox: valores separados por | -> IN (...)
        if (strValue.includes('|')) {
            const values = strValue.split('|').map(v => v.trim()).filter(Boolean);
            if (values.length > 0) {
                const placeholders = values.map(() => '?').join(',');
                conditions.push(`${key} IN (${placeholders})`);
                values.forEach(v => params[Object.keys(params).length] = v);
            }
        } else {
            // Filtro texto: LIKE
            conditions.push(`${key} LIKE ?`);
            params[Object.keys(params).length] = `%${strValue}%`;
        }
    }
    const where = conditions.length > 0 ? conditions.join(' AND ') : '1=1';
    return { where, params: Object.values(params) };
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

        const { where, params } = parseFilters(req.query.filters);
        const orderBy = buildOrderBy(sortBy, sortOrder);

        // COUNT(*) no SQLite em 21M registros é rápido (índice/id scan)
        const total = db.prepare(`SELECT COUNT(*) as c FROM dados_serpro WHERE ${where}`).get(...params).c;

        const dados = db.prepare(`
            SELECT * FROM dados_serpro
            WHERE ${where}
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

// ========== STATIC FILES ==========

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
