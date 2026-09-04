// Pure data parser. Builds the effective gen4 move table by evaluating the
// vendored Showdown data/moves.js and the mod overrides along gen4's inherit
// chain (gen4 <- gen5 <- gen6 <- gen7 <- gen8 <- base), shallow-merging each
// override onto the accumulated table (that is how sim/dex.ts loadDataFile +
// inheritance behaves for top-level move fields). Also builds gen1's table the
// same way for comparison. No network, no server, no battle objects.
const fs = require('fs');
const ROOT = '/Users/nickgreenquist/Documents/Projects/pokemon-showdown-rl/showdown/dist/data';
function load(p) {
  if (!fs.existsSync(p)) return {};
  return require(p).Moves || {};
}
const base = load(ROOT + '/moves.js');
function merge(acc, mod) {
  const out = Object.assign({}, acc);
  for (const k of Object.keys(mod)) {
    const m = mod[k];
    out[k] = (m.inherit && acc[k]) ? Object.assign({}, acc[k], m) : m;
  }
  return out;
}
let g = base;
for (const d of ['gen8', 'gen7', 'gen6', 'gen5', 'gen4']) g = merge(g, load(`${ROOT}/mods/${d}/moves.js`));
const gen4 = g;
let h = gen4;
for (const d of ['gen3', 'gen2', 'gen1']) h = merge(h, load(`${ROOT}/mods/${d}/moves.js`));
const gen1 = h;

const mode = process.argv[2];
if (mode === 'priority') {
  const rows = [];
  for (const k of Object.keys(gen4)) {
    const m = gen4[k];
    if (m.isNonstandard) continue;
    if (m.num > 467 || m.num <= 0) continue; // gen4 = move numbers 1..467
    if ((m.priority || 0) !== 0) rows.push([m.priority, k, m.category, m.basePower]);
  }
  rows.sort((a, b) => b[0] - a[0]);
  for (const r of rows) console.log(r.join('\t'));
} else if (mode === 'category') {
  // physical/special split: which gen4 moves change category vs the gen1-3 by-type rule
  const specialTypes = ['Fire', 'Water', 'Grass', 'Ice', 'Electric', 'Dark', 'Psychic', 'Dragon'];
  let flipP = [], flipS = [];
  for (const k of Object.keys(gen4)) {
    const m = gen4[k];
    if (m.isNonstandard || m.num > 467 || m.num <= 0) continue;
    if (m.category === 'Status') continue;
    const byType = specialTypes.includes(m.type) ? 'Special' : 'Physical';
    if (byType !== m.category) (m.category === 'Physical' ? flipP : flipS).push(`${k}(${m.type},${m.basePower})`);
  }
  console.log('PHYSICAL in gen4 but SPECIAL by the gen1-3 type rule (' + flipP.length + '):\n' + flipP.join(' '));
  console.log('\nSPECIAL in gen4 but PHYSICAL by the gen1-3 type rule (' + flipS.length + '):\n' + flipS.join(' '));
} else if (mode === 'crit') {
  const rows = [];
  for (const k of Object.keys(gen4)) {
    const m = gen4[k];
    if (m.isNonstandard || m.num > 467 || m.num <= 0) continue;
    if (m.critRatio && m.critRatio !== 1) rows.push(`${k}(critRatio=${m.critRatio})`);
    if (m.willCrit) rows.push(`${k}(willCrit)`);
  }
  console.log('gen4 high-crit moves: ' + rows.join(' '));
} else if (mode === 'named') {
  for (const k of process.argv.slice(3)) {
    const m4 = gen4[k], m1 = gen1[k];
    const pick = o => o ? JSON.stringify({
      num: o.num, bp: o.basePower, acc: o.accuracy, cat: o.category, type: o.type, pp: o.pp,
      pri: o.priority, crit: o.critRatio, flags: o.flags, target: o.target,
      vol: o.volatileStatus, side: o.sideCondition, slot: o.slotCondition, status: o.status,
      self: o.self && Object.keys(o.self), secondary: o.secondary, boosts: o.boosts,
      drain: o.drain, recoil: o.recoil, multihit: o.multihit, ohko: o.ohko,
      forceSwitch: o.forceSwitch, selfSwitch: o.selfSwitch, sleepUsable: o.sleepUsable,
      breaksProtect: o.breaksProtect, thawsTarget: o.thawsTarget, stallingMove: o.stallingMove,
      hasCallback: !!(o.damageCallback || o.basePowerCallback),
    }) : 'ABSENT';
    console.log(`### ${k}\n  gen4: ${pick(m4)}\n  gen1: ${pick(m1)}`);
  }
} else if (mode === 'flag') {
  const flag = process.argv[3];
  const hits = [];
  for (const k of Object.keys(gen4)) {
    const m = gen4[k];
    if (m.isNonstandard || m.num > 467 || m.num <= 0) continue;
    if (m.flags && m.flags[flag]) hits.push(k);
  }
  console.log(`gen4 moves with flag ${flag} (${hits.length}): ` + hits.join(' '));
} else if (mode === 'field') {
  const f = process.argv[3];
  const hits = [];
  for (const k of Object.keys(gen4)) {
    const m = gen4[k];
    if (m.isNonstandard || m.num > 467 || m.num <= 0) continue;
    if (m[f] !== undefined) hits.push(`${k}=${JSON.stringify(m[f])}`);
  }
  console.log(`gen4 moves with ${f} (${hits.length}): ` + hits.join(' '));
}
