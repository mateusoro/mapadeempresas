// Worker thread para /api/relatorio
// Roda a query SELECT num thread isolado. Se o parent chamar worker.terminate()
// (o que acontece no timeout do server), o thread morre junto com a query.
//
// Recebe via workerData: { dbPath, sql, timeoutMs }
// Posta de volta: { ok: true, rows, columns, elapsed_ms }
//                 { ok: false, error }

const { parentPort, workerData } = require('worker_threads');
const Database = require('better-sqlite3');

(async () => {
    const { dbPath, sql, timeoutMs } = workerData;
    const t0 = Date.now();
    let db;
    try {
        db = new Database(dbPath, { readonly: true, fileMustExist: true });
        // busy_timeout em ms: se o banco estiver locked, tenta por até N ms antes de errar
        try { db.pragma(`busy_timeout = ${Math.min(timeoutMs, 5000)}`); } catch (_) {}

        const stmt = db.prepare(sql);
        const rows = stmt.all();
        const elapsed = Date.now() - t0;

        // Extrai nomes das colunas via stmt.columns() (better-sqlite3 7.4+)
        let columns = [];
        try { columns = stmt.columns().map(c => c.name); } catch (_) { columns = []; }

        parentPort.postMessage({ ok: true, rows, columns, elapsed_ms: elapsed });
    } catch (err) {
        parentPort.postMessage({ ok: false, error: err.message, elapsed_ms: Date.now() - t0 });
    } finally {
        try { if (db) db.close(); } catch (_) {}
    }
})();
