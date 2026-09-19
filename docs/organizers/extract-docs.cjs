const fs = require('fs');
const path = require('path');
const s = fs.readFileSync('index.js', 'utf8');
const outDir = process.argv[2];
fs.mkdirSync(outDir, { recursive: true });

// the docs registry: [{slug, title, blurb, markdown: <var>}]
const reg = [...s.matchAll(/\{slug:"([^"]+)",title:"([^"]+)",blurb:"([^"]*)",markdown:([A-Za-z_$][\w$]*)(,hidden:!0)?\}/g)]
  .map(m => ({ slug: m[1], title: m[2], blurb: m[3], v: m[4], hidden: !!m[5] }));
console.log('registry:', reg.map(r => `${r.slug}=${r.v}${r.hidden ? '(hidden)' : ''}`).join(', '));

function literalAt(i) {           // parse a JS string/template literal starting at s[i]
  const q = s[i];
  if (!['`', "'", '"'].includes(q)) return null;
  let j = i + 1;
  while (j < s.length) {
    if (s[j] === '\\') { j += 2; continue; }
    if (s[j] === q) break;
    j++;
  }
  return s.slice(i, j + 1);
}
function valueOf(v) {
  // find `<v>=` preceded by a separator, followed by a quote
  const re = new RegExp('[,;{ ]' + v.replace(/\$/g, '\\$') + '=([`\'"])', 'g');
  let m;
  while ((m = re.exec(s))) {
    const lit = literalAt(m.index + m[0].length - 1);
    if (lit && lit.length > 200) {
      if (lit[0] === '`' && /\$\{/.test(lit)) console.log(`  note: ${v} template has \${} expressions`);
      return (new Function('return ' + lit))();
    }
  }
  return null;
}
for (const r of reg) {
  const md = valueOf(r.v);
  if (!md) { console.log(`!! could not extract ${r.slug}`); continue; }
  const file = path.join(outDir, (r.hidden ? 'normalization-table' : r.slug) + '.md');
  fs.writeFileSync(file, md);
  console.log(`${r.slug}: ${md.length} chars -> ${path.basename(file)}`);
}
// public-cases.json
const cmIdx = s.indexOf('"public-cases.json":');
const cmVar = s.slice(cmIdx + 20, cmIdx + 40).match(/^([A-Za-z_$][\w$]*)/)[1];
console.log('public cases var:', cmVar);
const re2 = new RegExp('[,;{ ]' + cmVar.replace(/\$/g, '\\$') + '=(.{0,120})', 'g');
let m2; while ((m2 = re2.exec(s))) { console.log('  candidate:', JSON.stringify(m2[1].slice(0, 120))); }
