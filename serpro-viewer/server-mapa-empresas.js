const express = require('express');
const initSqlJs = require('sql.js');
const path = require('path');
const fs = require('fs');

const app = express();
const PORT = 3000;

// Caminho do banco de dados
const DB_PATH = path.join(__dirname, 'base_dados.db');

// Middleware
app.use(express.json());

// Banco de dados em memória
let db;
let SQL;

// Inicializar banco
async function initDB() {
    try {
        SQL = await initSqlJs();
        
        // Carregar banco do disco
        const fileBuffer = fs.readFileSync(DB_PATH);
        db = new SQL.Database(fileBuffer);
        
        console.log('Banco de dados carregado com sucesso!');
    } catch (err) {
        console.error('Erro ao carregar banco:', err);
        process.exit(1);
    }
}

// Helper para executar queries
function runQuery(sql, params = []) {
    try {
        const stmt = db.prepare(sql);
        if (params.length > 0) {
            stmt.bind(params);
        }
        
        const results = [];
        while (stmt.step()) {
            results.push(stmt.getAsObject());
        }
        stmt.free();
        return results;
    } catch (err) {
        console.error('Erro na query:', err);
        throw err;
    }
}

function runExec(sql, params = []) {
    try {
        db.run(sql, params);
        return { changes: db.getRowsModified() };
    } catch (err) {
        console.error('Erro no exec:', err);
        throw err;
    }
}

// ========== API ROUTES (ANTES do static) ==========

// API: Listar todos os dados com paginação
app.get('/api/dados', (req, res) => {
    try {
        const page = parseInt(req.query.page) || 1;
        const limit = parseInt(req.query.limit) || 100;
        const offset = (page - 1) * limit;
        const sortBy = req.query.sortBy || 'id';
        const sortOrder = req.query.sortOrder || 'ASC';
        const filters = JSON.parse(req.query.filters || '{}');

        // Construir WHERE clause
        let whereClause = '';
        const params = [];
        const filterKeys = Object.keys(filters);

        if (filterKeys.length > 0) {
            const conditions = [];

            for (const key of filterKeys) {
                const value = filters[key];

                // Verificar se é um filtro de checkbox (pipe-separated)
                if (value.includes('|')) {
                    const values = value.split('|').map(v => v.trim()).filter(v => v);
                    if (values.length > 0) {
                        const placeholders = values.map(() => '?').join(', ');
                        conditions.push(`${key} IN (${placeholders})`);
                        params.push(...values);
                    }
                } else {
                    // Filtro de texto normal
                    params.push(`%${value}%`);
                    conditions.push(`${key} LIKE ?`);
                }
            }

            if (conditions.length > 0) {
                whereClause = 'WHERE ' + conditions.join(' AND ');
            }
        }

        // Validar coluna de ordenação
        const validColumns = ['id', 'ano_abertura', 'mes_abertura', 'ano_baixa', 'mes_baixa', 'regiao', 'uf', 'municipio', 'natureza_juridica', 'des_secao', 'tipo_situacao', 'porte', 'opcao_mei', 'quantidade'];
        const safeSortBy = validColumns.includes(sortBy) ? sortBy : 'id';
        const safeSortOrder = sortOrder.toUpperCase() === 'DESC' ? 'DESC' : 'ASC';

        // Total de registros
        const totalResult = runQuery(`SELECT COUNT(*) as total FROM dados_serpro ${whereClause}`, params);
        const total = totalResult[0]?.total || 0;

        // Dados paginados
        const dados = runQuery(`
            SELECT * FROM dados_serpro
            ${whereClause}
            ORDER BY ${safeSortBy} ${safeSortOrder}
            LIMIT ? OFFSET ?
        `, [...params, limit, offset]);

        res.json({
            success: true,
            data: dados,
            pagination: {
                page,
                limit,
                total,
                totalPages: Math.ceil(total / limit)
            }
        });
    } catch (err) {
        console.error('Erro na API /api/dados:', err);
        res.status(500).json({ success: false, error: err.message });
    }
});

// API: Estatísticas resumidas
app.get('/api/estatisticas', (req, res) => {
    try {
        const stats = {
            totalEmpresas: runQuery('SELECT SUM(quantidade) as total FROM dados_serpro')[0]?.total || 0,
            porRegiao: runQuery('SELECT regiao, SUM(quantidade) as total FROM dados_serpro GROUP BY regiao ORDER BY total DESC'),
            porUF: runQuery('SELECT uf, SUM(quantidade) as total FROM dados_serpro GROUP BY uf ORDER BY total DESC LIMIT 20'),
            porPorte: runQuery('SELECT porte, SUM(quantidade) as total FROM dados_serpro GROUP BY porte ORDER BY total DESC'),
            porAno: runQuery('SELECT ano_abertura, SUM(quantidade) as total FROM dados_serpro GROUP BY ano_abertura ORDER BY ano_abertura DESC LIMIT 10'),
            porTipoSituacao: runQuery('SELECT tipo_situacao, SUM(quantidade) as total FROM dados_serpro GROUP BY tipo_situacao ORDER BY total DESC'),
        };

        res.json({ success: true, data: stats });
    } catch (err) {
        console.error('Erro na API /api/estatisticas:', err);
        res.status(500).json({ success: false, error: err.message });
    }
});

// API: Estatísticas MEI com filtros (processa no servidor)
app.get('/api/estatisticas-mei', (req, res) => {
    try {
        const { data_inicio, data_fim, uf, municipio } = req.query;

        // Construir WHERE clause com filtros
        // A coluna opcao_mei tem valores 'MEI' ou 'Não-MEI'
        let conditions = ["opcao_mei = 'MEI'"];
        let params = [];

        if (uf) {
            conditions.push('uf = ?');
            params.push(uf);
        }

        if (municipio) {
            conditions.push('municipio LIKE ?');
            params.push(`%${municipio}%`);
        }

        if (data_inicio) {
            conditions.push('ano_abertura >= ?');
            params.push(parseInt(data_inicio.split('-')[0]));
        }

        if (data_fim) {
            conditions.push('ano_abertura <= ?');
            params.push(parseInt(data_fim.split('-')[0]));
        }

        const whereClause = 'WHERE ' + conditions.join(' AND ');

        // Estatísticas totais
        const statsAtivos = runQuery(`
            SELECT SUM(quantidade) as total
            FROM dados_serpro
            ${whereClause} AND tipo_situacao = 'Ativa'
        `, params);

        const statsBaixados = runQuery(`
            SELECT SUM(quantidade) as total
            FROM dados_serpro
            ${whereClause} AND tipo_situacao = 'Baixada'
        `, params);

        const statsTotal = runQuery(`
            SELECT SUM(quantidade) as total
            FROM dados_serpro
            ${whereClause}
        `, params);

        // Evolução por ano
        const evolucaoAnual = runQuery(`
            SELECT
                ano_abertura as ano,
                SUM(CASE WHEN tipo_situacao = 'Ativa' THEN quantidade ELSE 0 END) as aberturas,
                SUM(CASE WHEN tipo_situacao = 'Baixada' THEN quantidade ELSE 0 END) as baixas,
                SUM(quantidade) as ativos
            FROM dados_serpro
            ${whereClause}
            GROUP BY ano_abertura
            ORDER BY ano_abertura ASC
        `, params);

        res.json({
            success: true,
            data: {
                meiAtivos: statsAtivos[0]?.total || 0,
                meiBaixados: statsBaixados[0]?.total || 0,
                meiTotal: statsTotal[0]?.total || 0,
                evolucaoAnual: evolucaoAnual
            }
        });
    } catch (err) {
        console.error('Erro na API /api/estatisticas-mei:', err);
        res.status(500).json({ success: false, error: err.message });
    }
});

// API: Colunas da tabela
app.get('/api/colunas', (req, res) => {
    try {
        const colunas = runQuery("PRAGMA table_info(dados_serpro)");
        res.json({ success: true, data: colunas });
    } catch (err) {
        console.error('Erro na API /api/colunas:', err);
        res.status(500).json({ success: false, error: err.message });
    }
});

// ========== STATIC FILES (DEPOIS das APIs) ==========
app.use(express.static(path.join(__dirname, 'public')));

// Fallback para index.html
app.get('*', (req, res) => {
    res.sendFile(path.join(__dirname, 'public', 'index.html'));
});

// Iniciar servidor
async function start() {
    await initDB();
    
    app.listen(PORT, () => {
        console.log(`\nServidor rodando em http://localhost:${PORT}`);
        console.log(`Acesse http://localhost:${PORT} no navegador\n`);
    });
}

start();