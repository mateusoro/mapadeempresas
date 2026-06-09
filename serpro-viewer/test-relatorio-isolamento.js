// Testa timeout: query lenta que deve estourar 15s
const http = require('http');

function get(path) {
    return new Promise((resolve) => {
        const start = Date.now();
        http.get(`http://localhost:3000${path}`, (res) => {
            let body = '';
            res.on('data', c => body += c);
            res.on('end', () => {
                let parsed;
                try { parsed = JSON.parse(body); } catch (e) { parsed = body; }
                resolve({ status: res.statusCode, body: parsed, ms: Date.now() - start });
            });
        }).on('error', (e) => resolve({ status: 0, body: e.message, ms: Date.now() - start }));
    });
}

(async () => {
    console.log('Teste 1: COUNT(*) simples - rapido, nao deve dar timeout');
    let r = await get('/api/relatorio?q=' + encodeURIComponent('SELECT COUNT(*) AS total FROM dados_serpro'));
    console.log(`  -> ${r.status} em ${r.ms}ms`);
    console.log(`  total: ${r.body && r.body.data ? r.body.data.rows[0].total : '?'}`);

    console.log('\nTeste 2: query complexa GROUP BY - deve levar ~2-3s');
    r = await get('/api/relatorio?q=' + encodeURIComponent(
        "SELECT uf, tipo_situacao, SUM(quantidade) AS total FROM dados_serpro GROUP BY uf, tipo_situacao ORDER BY total DESC"
    ));
    const rowCount = r.body && r.body.data ? r.body.data.row_count : 'N/A';
    console.log(`  -> ${r.status} em ${r.ms}ms (rows=${rowCount})`);
    if (r.body && r.body.error) console.log(`  error: ${r.body.error}`);

    console.log('\nTeste 3: durante o teste 2, /api/health continua respondendo?');
    const t0 = Date.now();
    r = await get('/api/health');
    console.log(`  /api/health -> ${r.status} em ${r.ms}ms (esperado < 200ms)`);

    console.log('\nTeste 4: durante query lenta, /api/stats-resumo continua funcionando?');
    r = await get('/api/stats-resumo');
    console.log(`  /api/stats-resumo -> ${r.status} em ${r.ms}ms (esperado < 1000ms)`);

    console.log('\nTeste 5: /api/dados (paginado, usa index) - rapido');
    r = await get('/api/dados?page=1&limit=10');
    console.log(`  /api/dados -> ${r.status} em ${r.ms}ms (rows=${r.body.data ? r.body.data.length : '?'})`);

    console.log('\nTeste 6: stats-resumo apos cache (deve ser < 50ms)');
    r = await get('/api/stats-resumo');
    console.log(`  /api/stats-resumo (cache hit) -> ${r.status} em ${r.ms}ms (cached=${r.body.cached})`);
})();
