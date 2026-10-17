// 用 Node 执行 dashboard.html 的渲染 JS（mock 最小 DOM + Chart），定位运行时错误
// 用法: node tools/verify_dashboard.js [dashboard.html 路径]（默认 report/dashboard.html）
const fs = require('fs');
const path = process.argv[2] || 'report/dashboard.html';
const html = fs.readFileSync(path, 'utf-8');
const parts = html.split('<script>');
const render = parts[2].split('</script>')[0];
const errors = [];
let chartCount = 0;
const elCache = {};
global.document = {
  getElementById: id => {
    if (!elCache[id]) elCache[id] = { textContent: '', innerHTML: '', id };
    return elCache[id];
  }
};
global.Chart = function (ctx, cfg) {
  chartCount++;
  if (!ctx) errors.push('Chart ctx null #' + chartCount);
};
try {
  eval(render);
  console.log('执行完成 | Chart实例:', chartCount, '| 错误:', errors.length ? errors : '无');
} catch (e) {
  console.log('JS 执行抛错:', e.constructor.name + ':', e.message);
  console.log(e.stack.split('\n').slice(0, 6).join('\n'));
  process.exit(1);
}
