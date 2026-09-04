// Pure data parser: builds gen1 and gen4 typecharts from vendored Showdown TS
// by stripping the TS type annotation and eval'ing the object literal, then
// applying the mod inherit chain gen4 <- gen5 <- gen6 <- gen7 <- gen8 <- base.
// No network, no server. Run under nice -n 19.
const fs = require('fs');
const ROOT = '/Users/nickgreenquist/Documents/Projects/pokemon-showdown-rl/showdown/data';
function load(p) {
  if (!fs.existsSync(p)) return {};
  let t = fs.readFileSync(p, 'utf8');
  t = t.replace(/^export const TypeChart[^=]*=/m, 'module.exports =');
  const m = require('module');
  const fn = new Function('module', 'exports', t + '\n');
  const mod = { exports: {} };
  fn(mod, mod.exports);
  return mod.exports;
}
const base = load(ROOT + '/typechart.ts');
function merge(acc, mod) {
  const out = {};
  for (const k of new Set([...Object.keys(acc), ...Object.keys(mod)])) {
    if (!(k in mod)) { out[k] = acc[k]; continue; }
    const m = mod[k];
    if (m.inherit && acc[k]) {
      out[k] = Object.assign({}, acc[k], m);
      if (m.damageTaken) out[k].damageTaken = m.damageTaken; // full replace
    } else {
      out[k] = m;
    }
  }
  return out;
}
// gen4 = base <- gen8 <- gen7 <- gen6 <- gen5 <- gen4
let g = base;
for (const d of ['gen8', 'gen7', 'gen6', 'gen5', 'gen4']) g = merge(g, load(`${ROOT}/mods/${d}/typechart.ts`));
const gen4 = g;
// gen1 = gen4 <- gen3 <- gen2 <- gen1
let h = gen4;
for (const d of ['gen3', 'gen2', 'gen1']) h = merge(h, load(`${ROOT}/mods/${d}/typechart.ts`));
const gen1 = h;
function eff(chart, atk, def) {
  const td = chart[def.toLowerCase()];
  if (!td) return 'ABSENT';
  const v = td.damageTaken[atk];
  return v === 1 ? 2 : v === 2 ? 0.5 : v === 3 ? 0 : 1;
}
function live(chart) {
  return Object.keys(chart).filter(k => chart[k].isNonstandard !== 'Future' && chart[k].damageTaken && k !== 'stellar');
}
const g4types = live(gen4), g1types = live(gen1);
console.log('GEN4 types (' + g4types.length + '):', g4types.join(','));
console.log('GEN1 types (' + g1types.length + '):', g1types.join(','));
const cap = s => s[0].toUpperCase() + s.slice(1);
console.log('\n--- CELLS DIFFERING gen1 -> gen4 (attacker x defender), restricted to types present in BOTH ---');
const both = g4types.filter(t => g1types.includes(t));
for (const a of both) for (const d of both) {
  const e1 = eff(gen1, cap(a), d), e4 = eff(gen4, cap(a), d);
  if (e1 !== e4) console.log(`${cap(a)} -> ${cap(d)}: gen1=${e1}x  gen4=${e4}x`);
}
console.log('\n--- gen4 rows for Dark and Steel (new types) ---');
for (const d of ['dark', 'steel']) {
  const row = [];
  for (const a of g4types) row.push(`${cap(a)}=${eff(gen4, cap(a), d)}`);
  console.log(`vs ${cap(d)}: ` + row.join(' '));
}
for (const a of ['dark', 'steel']) {
  const row = [];
  for (const d of g4types) row.push(`${cap(d)}=${eff(gen4, cap(a), d)}`);
  console.log(`${cap(a)} attacking: ` + row.join(' '));
}
console.log('\n--- non-type damageTaken keys in gen4 (status/effect immunities) ---');
for (const t of g4types) {
  const ks = Object.keys(gen4[t].damageTaken).filter(k => k[0] === k[0].toLowerCase());
  if (ks.length) console.log(t, ks.map(k => k + '=' + gen4[t].damageTaken[k]).join(','));
}
console.log('\n--- same for gen1 ---');
for (const t of g1types) {
  const ks = Object.keys(gen1[t].damageTaken).filter(k => k[0] === k[0].toLowerCase());
  if (ks.length) console.log(t, ks.map(k => k + '=' + gen1[t].damageTaken[k]).join(','));
}
