// Sample the vendored gen4randombattle team generator offline and tally what it
// actually emits: species, ability, item, moves, level, role, forme strings.
// The design docs' item universe (40) and ability universe (101) are STATIC
// reachability reads of teams.ts; this is the empirical marginal the docs mark
// [live] (mechanics_delta.md §17). Needs the built server (dist/ present).
//
//   nice -n 19 node scripts/gen4_sample_generator.js showdown 20000 data/gen4_tapes/generator_sample.json
//
// Args: <showdown root> <n teams> <out json> [seed]. Reproducible: fixed PRNG seed.
'use strict';
const fs = require('fs');
const path = require('path');

const root = process.argv[2] || 'showdown';
const nTeams = parseInt(process.argv[3] || '20000', 10);
const outPath = process.argv[4] || 'generator_sample.json';
const seedArg = process.argv[5] || '1,2,3,4';

const sim = require(path.resolve(root, 'dist/sim'));
const {Teams, Dex} = sim;
const commit = fs.readFileSync(path.resolve(root, '.git/HEAD'), 'utf8').trim();

const seed = seedArg.split(',').map(Number);
const gen = Teams.getGenerator('gen4randombattle', seed);
const dex = Dex.forFormat('gen4randombattle');

const tally = (m, k) => { m[k] = (m[k] || 0) + 1; };
const species = {}, formeStrings = {}, abilities = {}, items = {}, moves = {}, roles = {}, levels = {};
const abilityBySpecies = {}, itemBySpecies = {}, levelBySpecies = {};
const hpTypes = {}, teamSizes = {};
const setSamples = {};  // species -> {'m1,m2,m3,m4|ability|item': count}
let nSets = 0, stealthRock = 0, shiny = 0, natureField = 0;

for (let i = 0; i < nTeams; i++) {
  const team = gen.getTeam();
  tally(teamSizes, team.length);
  for (const set of team) {
    nSets++;
    const sid = dex.species.get(set.species).id;
    tally(species, sid);
    if (set.species !== dex.species.get(set.species).name) tally(formeStrings, set.species);
    const ab = dex.abilities.get(set.ability).id;
    tally(abilities, ab);
    (abilityBySpecies[sid] = abilityBySpecies[sid] || {})[ab] = (abilityBySpecies[sid][ab] || 0) + 1;
    const it = set.item ? dex.items.get(set.item).id : '(none)';
    tally(items, it);
    (itemBySpecies[sid] = itemBySpecies[sid] || {})[it] = (itemBySpecies[sid][it] || 0) + 1;
    tally(levels, set.level);
    (levelBySpecies[sid] = levelBySpecies[sid] || {})[set.level] = (levelBySpecies[sid][set.level] || 0) + 1;
    if (set.role) tally(roles, set.role);
    const mids = set.moves.map(mv => dex.moves.get(mv).id === 'hiddenpower' ? String(mv).toLowerCase().replace(/[^a-z0-9]/g, '') : dex.moves.get(mv).id).sort();
    const key = mids.join(',') + '|' + ab + '|' + it;
    (setSamples[sid] = setSamples[sid] || {})[key] = (setSamples[sid][key] || 0) + 1;
    if (set.nature) natureField++;
    if (set.shiny) shiny++;
    for (const mv of set.moves) {
      const mid = dex.moves.get(mv).id === 'hiddenpower' ? String(mv).toLowerCase().replace(/[^a-z0-9]/g, '') : dex.moves.get(mv).id;
      tally(moves, mid);
      if (mid === 'stealthrock') stealthRock++;
      if (mid.startsWith('hiddenpower')) tally(hpTypes, mid);
    }
  }
}

const sortObj = (o) => Object.fromEntries(Object.entries(o).sort((a, b) => b[1] - a[1]));
const out = {
  showdown_commit: commit,
  seed,
  n_teams: nTeams,
  n_sets: nSets,
  team_sizes: teamSizes,
  distinct: {
    species: Object.keys(species).length,
    forme_strings: Object.keys(formeStrings).length,
    abilities: Object.keys(abilities).length,
    items: Object.keys(items).length,
    moves: Object.keys(moves).length,
    levels: Object.keys(levels).length,
    roles: Object.keys(roles).length,
  },
  stealth_rock_sets: stealthRock,
  shiny_sets: shiny,
  sets_with_nature_field: natureField,
  species: sortObj(species),
  forme_strings: sortObj(formeStrings),
  abilities: sortObj(abilities),
  items: sortObj(items),
  moves: sortObj(moves),
  hidden_power_types: sortObj(hpTypes),
  levels: sortObj(levels),
  roles: sortObj(roles),
  ability_by_species: abilityBySpecies,
  item_by_species: itemBySpecies,
  level_by_species: levelBySpecies,
};
fs.writeFileSync(outPath, JSON.stringify(out, null, 1));
const setsOut = outPath.replace(/\.json$/, '') + '.sets.json';
fs.writeFileSync(setsOut, JSON.stringify({showdown_commit: commit, seed, n_teams: nTeams, n_sets: nSets, generator: 'scripts/gen4_sample_generator.js', level_by_species: levelBySpecies, set_samples: setSamples}));
console.log('set samples ->', setsOut, 'distinct keys', Object.values(setSamples).reduce((a, m) => a + Object.keys(m).length, 0));
console.log(JSON.stringify({commit, nTeams, nSets, distinct: out.distinct, stealthRock, shiny, natureField, teamSizes}));
