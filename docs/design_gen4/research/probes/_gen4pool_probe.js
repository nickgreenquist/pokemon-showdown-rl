// Offline data probe: loads the vendored Showdown Dex (gen4 mod) and the gen4 randbats sets.json.
// No server, no battle, no network. Run under nice -n 19.
const SD = '/Users/nickgreenquist/Documents/Projects/pokemon-showdown-rl/showdown';
const { Dex } = require(SD + '/dist/sim/dex');
const sets = require(SD + '/data/random-battles/gen4/sets.json');
const dex = Dex.mod('gen4');
const out = {};
const keys = Object.keys(sets);
out.genOfMod = dex.gen;
out.nKeys = keys.length;
const bySpecies = keys.map(k => dex.species.get(k));
out.missingSpecies = bySpecies.filter(s => !s.exists).map(s => s.id);
out.nonstandardSpecies = bySpecies.filter(s => s.isNonstandard).map(s => [s.id, s.isNonstandard, s.gen]);
out.speciesGenGt4 = bySpecies.filter(s => s.gen > 4).map(s => s.id);
out.nBaseSpecies = new Set(bySpecies.map(s => s.baseSpecies)).size;
const pool = {};
for (const s of bySpecies) (pool[s.baseSpecies] = pool[s.baseSpecies] || []).push(s.id);
out.multiFormeBases = Object.entries(pool).filter(([b, l]) => l.length > 1).map(([b, l]) => [b, l.length, Math.min(Math.ceil(l.length / 3), 3)]);
out.baseSpeciesPoolLen = Object.values(pool).reduce((a, l) => a + Math.min(Math.ceil(l.length / 3), 3), 0);
out.cosmetic = bySpecies.filter(s => s.cosmeticFormes).map(s => [s.id, s.cosmeticFormes]);
out.otherFormes = bySpecies.filter(s => s.otherFormes).map(s => [s.id, s.otherFormes.map(f => { const fs = dex.species.get(f); return [fs.name, fs.battleOnly || null, fs.types, fs.isNonstandard || null, fs.gen]; })]);
out.battleOnlyKeys = bySpecies.filter(s => s.battleOnly).map(s => [s.id, s.battleOnly]);
out.requiredItems = bySpecies.filter(s => s.requiredItems).map(s => [s.id, s.requiredItems]);
out.maxDexNum = Math.max(...bySpecies.map(s => s.num));
out.typeCounts = {}; for (const s of bySpecies) for (const t of s.types) out.typeCounts[t] = (out.typeCounts[t] || 0) + 1;
out.rotomTypes = ['rotom', 'rotomheat', 'rotomwash', 'rotomfrost', 'rotomfan', 'rotommow'].map(k => [k, dex.species.get(k).types]);
out.wormadam = ['wormadam', 'wormadamsandy', 'wormadamtrash'].map(k => [k, dex.species.get(k).types, dex.species.get(k).baseSpecies, dex.species.get(k).forme]);
out.gastrodon = [dex.species.get('gastrodon').cosmeticFormes, dex.species.get('gastrodoneast').exists, dex.species.get('gastrodoneast').name, dex.species.get('gastrodoneast').isNonstandard || null];
out.castformFormes = ['castformsunny', 'castformrainy', 'castformsnowy', 'cherrimsunshine'].map(k => { const s = dex.species.get(k); return [k, s.exists, s.types, s.battleOnly, s.isNonstandard || null, s.gen]; });
out.speciesGender = bySpecies.filter(s => s.gender).length;
// moves
const moves = new Set(); for (const k of keys) for (const st of sets[k].sets) for (const m of st.movepool) moves.add(m);
out.nMoves = moves.size;
const mv = [...moves].map(m => dex.moves.get(m));
out.movesMissing = mv.filter(m => !m.exists).map(m => m.id);
out.movesGenGt4 = mv.filter(m => m.gen > 4).map(m => [m.id, m.gen]);
out.movesNonstandard = mv.filter(m => m.isNonstandard).map(m => [m.id, m.isNonstandard]);
out.hpMoves = [...moves].filter(m => m.startsWith('hiddenpower')).map(m => { const x = dex.moves.get(m); return [m, x.id, x.name, x.type, x.basePower, x.category, x.placeholderFor || null]; });
out.moveCats = {}; for (const m of mv) out.moveCats[m.category] = (out.moveCats[m.category] || 0) + 1;
out.moveTypes = {}; for (const m of mv) out.moveTypes[m.type] = (out.moveTypes[m.type] || 0) + 1;
out.maxMoveNum = Math.max(...mv.map(m => m.num));
out.struggle = [dex.moves.get('struggle').num, dex.moves.get('struggle').exists, dex.moves.get('struggle').gen];
out.moveIdsDistinctFromKey = [...moves].filter(m => dex.moves.get(m).id !== m).map(m => [m, dex.moves.get(m).id]);
// abilities
const abs = new Set(); for (const k of keys) for (const st of sets[k].sets) for (const a of st.abilities) abs.add(a);
out.nAbilities = abs.size;
const ab = [...abs].map(a => dex.abilities.get(a));
out.abilitiesMissing = ab.filter(a => !a.exists).map(a => a.name);
out.abilitiesGenGt4 = ab.filter(a => a.gen > 4).map(a => [a.name, a.gen]);
out.abilitiesNonstandard = ab.filter(a => a.isNonstandard).map(a => [a.name, a.isNonstandard]);
out.maxAbilityNum = Math.max(...ab.map(a => a.num));
out.abilityMismatch = [];
for (const k of keys) { const s = dex.species.get(k); const legal = Object.values(s.abilities); for (const st of sets[k].sets) for (const a of st.abilities) if (!legal.includes(a)) out.abilityMismatch.push([k, a, legal]); }
// items
const items = ['Soul Dew', 'Thick Club', 'Light Ball', 'Focus Sash', 'Custap Berry', 'Choice Scarf', 'Quick Powder', 'Sitrus Berry', 'Life Orb', 'Leftovers', 'Toxic Orb', 'Choice Band', 'Choice Specs', 'Light Clay', 'Damp Rock', 'Chesto Berry', 'Black Glasses', 'Silk Scarf', 'Lustrous Orb', 'Stick', 'Lum Berry', 'Expert Belt', 'Black Sludge', 'Griseous Orb', 'Flame Plate', 'Insect Plate', 'Dread Plate', 'Draco Plate', 'Zap Plate', 'Fist Plate', 'Sky Plate', 'Spooky Plate', 'Meadow Plate', 'Earth Plate', 'Icicle Plate', 'Toxic Plate', 'Mind Plate', 'Stone Plate', 'Iron Plate', 'Splash Plate', 'Pixie Plate', 'Buginium Z', 'Griseous Core', 'Eviolite', 'Rocky Helmet', 'Flying Gem', 'Fighting Gem', 'White Herb', 'Flame Orb', 'Adamant Orb'];
out.items = items.map(i => { const it = dex.items.get(i); return [i, it.exists, it.gen, it.isNonstandard || null, it.num]; });
// universe sizes in gen4 mod
const allSp = dex.species.all().filter(s => s.exists && !s.isNonstandard);
out.universeSpeciesEntries = allSp.length;
out.universeSpeciesGenLe4 = allSp.filter(s => s.gen <= 4).length;
out.universeBaseSpecies = new Set(allSp.map(s => s.baseSpecies)).size;
out.universeSpeciesMaxNum = Math.max(...allSp.map(s => s.num));
const allMv = dex.moves.all().filter(m => m.exists && !m.isNonstandard);
out.universeMoves = allMv.length;
out.universeMovesNoHPplaceholders = allMv.filter(m => !m.placeholderFor).length;
out.universeMovesMaxNum = Math.max(...allMv.map(m => m.num));
const allAb = dex.abilities.all().filter(a => a.exists && !a.isNonstandard);
out.universeAbilities = allAb.length;
out.universeAbilitiesMaxNum = Math.max(...allAb.map(a => a.num));
const allIt = dex.items.all().filter(i => i.exists && !i.isNonstandard);
out.universeItems = allIt.length;
out.universeTypes = dex.types.names();
// hidden power ivs and power
out.hpivs = dex.types.all().filter(t => t.HPivs && Object.keys(t.HPivs).length).map(t => { const ivs = Object.assign({ hp: 31, atk: 31, def: 31, spa: 31, spd: 31, spe: 31 }, t.HPivs); const hp = dex.getHiddenPower(ivs); const ivs2 = Object.assign({}, ivs, { atk: (ivs.atk || 31) - 28 }); const hp2 = dex.getHiddenPower(ivs2); return [t.name, t.HPivs, hp, hp2]; });
out.natureEmpty = [dex.natures.get('').exists, dex.natures.get('').name, dex.natures.get('').plus || null, dex.natures.get('').minus || null];
console.log(JSON.stringify(out, null, 1));
