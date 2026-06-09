const initSqlJs = require('sql.js');
const fs = require('fs');
initSqlJs().then(SQL => {
    const db = new SQL.Database(fs.readFileSync('base_dados.db'));
    const tables = db.exec("SELECT name FROM sqlite_master WHERE type='table'");
    console.log(JSON.stringify(tables, null, 2));
});