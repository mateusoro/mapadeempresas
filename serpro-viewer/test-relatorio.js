// Testa /api/relatorio com varios cenarios
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

const cases = [
    { name: '1. SELECT simples (sem LIMIT)', q: "SELECT * FROM dados_serpro WHERE uf = 'SP'" },
    { name: '2. SELECT com LIMIT proprio (deve ser ignorado e usar 100)', q: "SELECT * FROM dados_serpro WHERE uf = 'SP' LIMIT 99999" },
    { name: '3. SELECT com COUNT', q: "SELECT COUNT(*) AS total, uf FROM dados_serpro WHERE tipo_situacao = 'Ativa' GROUP BY uf" },
    { name: '4. SELECT com string contendo aspas (escape \'\')', q: "SELECT 'it''s ok' AS msg, uf FROM dados_serpro LIMIT 5" },
    { name: '5. SELECT com -- comentário', q: "SELECT uf FROM dados_serpro -- isso e comentario\nWHERE uf = 'SP' LIMIT 5" },
    { name: '6. SELECT com /* comentario */', q: "SELECT /* comentario */ uf FROM dados_serpro WHERE uf = 'SP' LIMIT 5" },
    { name: '7. SELECT com ; trailing (deve ser removido)', q: "SELECT uf FROM dados_serpro WHERE uf = 'SP' LIMIT 5;" },
    { name: '8. SELECT com OFFSET (manter offset, remover so LIMIT)', q: "SELECT uf FROM dados_serpro WHERE uf = 'SP' LIMIT 5 OFFSET 10" },
    { name: '9. SELECT com WITH (CTE)', q: "WITH top_uf AS (SELECT uf, SUM(quantidade) AS total FROM dados_serpro WHERE tipo_situacao = 'Ativa' GROUP BY uf) SELECT * FROM top_uf ORDER BY total DESC" },
    { name: '10. Query vazia (deve rejeitar)', q: '' },
    { name: '11. DELETE (deve rejeitar)', q: 'DELETE FROM dados_serpro' },
    { name: '12. UPDATE (deve rejeitar)', q: "UPDATE dados_serpro SET uf = 'XX'" },
    { name: '13. DROP (deve rejeitar)', q: 'DROP TABLE dados_serpro' },
    { name: '14. INSERT (deve rejeitar)', q: "INSERT INTO dados_serpro VALUES (1, 2020, 1, null, null, 'S', 'SP', 'Sao Paulo', 'LTDA', 'Ativa', 'ME', 'S', 1)" },
    { name: '15. ATTACH (deve rejeitar)', q: "ATTACH DATABASE 'evil.db' AS evil" },
    { name: '16. PRAGMA (deve rejeitar)', q: 'PRAGMA table_info(dados_serpro)' },
    { name: '17. Multi-statement (deve rejeitar)', q: 'SELECT 1; SELECT 2' },
    { name: '18. SELECT com subquery usando UPDATE (deve rejeitar)', q: 'SELECT (DELETE FROM dados_serpro) AS x' },
    { name: '19. Query SQL invalida (deve dar erro do SQLite)', q: 'SELECT * FROM tabela_inexistente' },
    { name: '20. SELECT com LIMIT variante LIMIT a, b (deve remover)', q: "SELECT uf FROM dados_serpro WHERE uf = 'SP' LIMIT 10, 5" },
    { name: '21. SELECT no parametro q sem URL-encoding manual (smoke)', q: "SELECT 1 AS teste" },
    { name: '22. SELECT com acentos (UTF-8)', q: "SELECT 'São Paulo' AS cidade, uf FROM dados_serpro LIMIT 3" },
];

(async () => {
    let pass = 0, fail = 0;
    for (const c of cases) {
        const q = encodeURIComponent(c.q);
        const r = await get(`/api/relatorio?q=${q}`);
        const status = r.status;
        const ok = r.body && r.body.success === true;
        const isReject = status === 400;
        const isExpectedErr = (status >= 400 && status < 500);

        let verdict;
        // Define o que esperamos de cada caso
        const expect = {
            1: { ok: true }, 2: { ok: true, maxRows: 100 },
            3: { ok: true }, 4: { ok: true }, 5: { ok: true }, 6: { ok: true }, 7: { ok: true },
            8: { ok: true }, 9: { ok: true },
            10: { reject: true }, 11: { reject: true }, 12: { reject: true },
            13: { reject: true }, 14: { reject: true }, 15: { reject: true },
            16: { reject: true }, 17: { reject: true }, 18: { reject: true },
            19: { reject: true }, 20: { ok: true }
        };
        const num = c.name.split('.')[0];
        const exp = expect[num] || { ok: true };

        if (exp.ok) {
            verdict = (ok && r.body.data && r.body.data.row_count <= 100) ? 'PASS' : 'FAIL';
            if (verdict === 'PASS') {
                const colInfo = r.body.data.columns ? `[${r.body.data.columns.length} cols]` : '[no cols]';
                console.log(`  ${c.name} -> ${status} (${r.body.data.row_count} rows, ${colInfo}) [${r.ms}ms] ${verdict}`);
            } else {
                console.log(`  ${c.name} -> ${status} ${verdict} body=${JSON.stringify(r.body).substring(0,200)}`);
            }
        } else if (exp.reject) {
            verdict = isReject ? 'PASS' : 'FAIL';
            console.log(`  ${c.name} -> ${status} ${verdict} (esperado 400) - err=${r.body.error || JSON.stringify(r.body).substring(0,150)}`);
        } else {
            verdict = isExpectedErr ? 'PASS' : 'FAIL';
            console.log(`  ${c.name} -> ${status} ${verdict}`);
        }
        verdict === 'PASS' ? pass++ : fail++;
    }
    console.log(`\n${pass} PASS, ${fail} FAIL`);
    process.exit(fail > 0 ? 1 : 0);
})();
