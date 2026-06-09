// Testa a pagina /relatorio - verifica que:
// 1. /relatorio?q=... serve a pagina com a query no textarea
// 2. /api/relatorio?q=... retorna os dados corretos que a pagina vai consumir
// 3. /relatorio sem ?q= serve a pagina com empty state

const http = require('http');

function get(path) {
    return new Promise((resolve, reject) => {
        const start = Date.now();
        http.get(`http://localhost:3000${path}`, (res) => {
            let body = '';
            res.on('data', c => body += c);
            res.on('end', () => {
                resolve({ status: res.statusCode, body, ms: Date.now() - start, headers: res.headers });
            });
        }).on('error', reject);
    });
}

(async () => {
    let pass = 0, fail = 0;
    const check = (name, cond) => {
        if (cond) { pass++; console.log(`  [PASS] ${name}`); }
        else { fail++; console.log(`  [FAIL] ${name}`); }
    };

    console.log('Teste 1: /relatorio (sem query)');
    let r = await get('/relatorio');
    check('Status 200', r.status === 200);
    check('Content-Type text/html', r.headers['content-type'] && r.headers['content-type'].includes('text/html'));
    check('Contem titulo "Relatrio SERPRO" (com ou sem encoding)', r.body.includes('SERPRO'));
    check('Contem textarea de query', r.body.includes('<textarea id="query"'));
    check('Contem div de tabela', r.body.includes('id="table"'));
    check('Contem botao Executar', r.body.includes('btn-run'));
    check('Contem botao CSV', r.body.includes('btn-csv'));
    check('Contem botao JSON', r.body.includes('btn-copy-json'));
    check('Contem toggle de densidade', r.body.includes('density-toggle'));
    check('Contem Grid.js CDN', r.body.includes('gridjs@6.2.0'));
    check('Contem funcao runQuery', r.body.includes('async function runQuery'));
    check('Contem query-stats element', r.body.includes('id="query-stats"'));

    console.log('\nTeste 2: /relatorio?q=SELECT... (com query)');
    const q = encodeURIComponent("SELECT * FROM dados_serpro WHERE opcao_mei='S' AND municipio='Pinhalzinho - SC' AND ano_abertura=2026");
    r = await get(`/relatorio?q=${q}`);
    check('Status 200', r.status === 200);
    check('Mesma pagina (relatorio.html)', r.body.includes('id="table"'));

    console.log('\nTeste 3: /api/relatorio com query que sera executada pela pagina');
    const apiQ = encodeURIComponent("SELECT uf, SUM(quantidade) AS total FROM dados_serpro WHERE tipo_situacao='Ativa' GROUP BY uf ORDER BY total DESC");
    r = await get(`/api/relatorio?q=${apiQ}`);
    const j = JSON.parse(r.body);
    check('Status 200', r.status === 200);
    check('success=true', j.success === true);
    check('Tem 28 UFs', j.data.row_count === 28);
    check('Top UF = SP', j.data.rows[0].uf === 'SP');
    check('Total de SP = 7.630.729', j.data.rows[0].total === 7630729);
    check('Tem colunas (uf, total)', j.data.columns.includes('uf') && j.data.columns.includes('total'));
    check('Tem sql_aplicado', j.data.sql_aplicado && j.data.sql_aplicado.includes('LIMIT 100'));

    console.log('\nTeste 4: pagina tem os IDs que o JS espera');
    r = await get('/relatorio');
    const requiredIds = ['query', 'btn-run', 'btn-clear', 'btn-example', 'btn-copy-json', 'btn-csv',
                         'table-search', 'm-rows', 'm-cols', 'm-query-ms', 'm-total-ms',
                         'badge-status', 'sql-applied', 'toast', 'table'];
    let missingIds = requiredIds.filter(id => !r.body.includes(`id="${id}"`));
    check(`Todos os IDs necessarios presentes (faltam: ${missingIds.join(',') || 'nenhum'})`, missingIds.length === 0);

    console.log('\nTeste 5: CSP/security - pagina nao tem inline event handlers perigosos');
    const dangerousOnclick = /onclick\s*=\s*["'][^"']*(?:eval|document\.cookie|window\.location\s*=)/i;
    check('Sem onclick perigoso', !dangerousOnclick.test(r.body));

    console.log(`\n${pass} PASS, ${fail} FAIL`);
    process.exit(fail > 0 ? 1 : 0);
})().catch(e => { console.error('Test error:', e); process.exit(1); });
