// Pure data dump of the vendored Showdown Dex, resolved for the gen4 mod.
// No Battle objects, no server, no network.
const path = '/Users/nickgreenquist/Documents/Projects/pokemon-showdown-rl/showdown';
const { Dex } = require(path + '/dist/sim');
const fs = require('fs');
const OUT = '/private/tmp/claude-501/-Users-nickgreenquist-Documents-Projects-pokemon-showdown-rl/b1478b5b-c556-4e2e-9100-b0db7e234069/scratchpad/research/_gen4_dexdump.json';

const dex4 = Dex.mod('gen4');
const dex1 = Dex.mod('gen1');
const out = { gen4: {}, gen1: {} };

function typechart(dex) {
	const t = {};
	for (const ty of dex.types.all()) {
		if (ty.isNonstandard) continue;
		t[ty.name] = ty.damageTaken;
	}
	return t;
}
out.gen4.types = typechart(dex4);
out.gen1.types = typechart(dex1);

const KEYS = ['id', 'name', 'num', 'type', 'category', 'basePower', 'accuracy', 'pp', 'priority', 'critRatio', 'target',
	'flags', 'volatileStatus', 'sideCondition', 'slotCondition', 'pseudoWeather', 'weather', 'terrain', 'selfSwitch',
	'forceSwitch', 'multihit', 'multiaccuracy', 'recoil', 'drain', 'ohko', 'selfdestruct', 'sleepUsable', 'thawsTarget',
	'breaksProtect', 'stallingMove', 'willCrit', 'ignoreDefensive', 'ignoreOffensive', 'ignoreEvasion', 'ignoreAccuracy',
	'ignoreImmunity', 'boosts', 'heal', 'damage', 'status', 'hasCrashDamage', 'struggleRecoil', 'secondary', 'secondaries',
	'self', 'selfBoost', 'overrideOffensiveStat', 'overrideDefensiveStat', 'overrideOffensivePokemon',
	'overrideDefensivePokemon', 'forceSTAB', 'noPPBoosts', 'nonGhostTarget', 'alwaysHit', 'hasSheerForce', 'mindBlownRecoil',
	'isNonstandard', 'gen'];
function moveRow(m) {
	const r = {};
	for (const k of KEYS) if (m[k] !== undefined) r[k] = m[k];
	r.cb = {};
	for (const k of ['basePowerCallback', 'damageCallback', 'onTryMove', 'onTry', 'onTryHit', 'onTryImmunity', 'onPrepareHit',
		'beforeTurnCallback', 'priorityChargeCallback', 'beforeMoveCallback', 'onModifyMove', 'onModifyType', 'onHit',
		'onAfterHit', 'onAfterMove', 'onMoveFail', 'onEffectiveness', 'onModifyPriority', 'onDisableMove', 'onAfterSubDamage', 'onHitField', 'onHitSide']) {
		if (m[k]) r.cb[k] = true;
	}
	if (m.condition) {
		r.condition = { keys: Object.keys(m.condition), duration: m.condition.duration, noCopy: m.condition.noCopy,
			counterMax: m.condition.counterMax };
	}
	return r;
}
out.gen4.moves = [];
for (const m of dex4.moves.all()) {
	if (!(m.num > 0 && m.num <= 467)) continue;
	if (m.isNonstandard && m.isNonstandard !== 'Unobtainable') continue;
	out.gen4.moves.push(moveRow(m));
}
out.gen1.moves = [];
for (const m of dex1.moves.all()) {
	if (!(m.num > 0 && m.num <= 165)) continue;
	if (m.isNonstandard && m.isNonstandard !== 'Unobtainable') continue;
	out.gen1.moves.push(moveRow(m));
}

// conditions of interest (data fields only; functions dropped)
const CONDS = ['brn', 'par', 'slp', 'frz', 'psn', 'tox', 'confusion', 'flinch', 'trapped', 'trapper', 'partiallytrapped',
	'lockedmove', 'twoturnmove', 'choicelock', 'mustrecharge', 'futuremove', 'stall', 'raindance', 'sunnyday', 'sandstorm',
	'hail', 'substitutebroken', 'arceus'];
out.gen4.conditions = {};
for (const c of CONDS) {
	const cd = dex4.conditions.get(c);
	out.gen4.conditions[c] = { exists: cd.exists, keys: Object.keys(cd).filter(k => typeof cd[k] !== 'function'),
		fnKeys: Object.keys(cd).filter(k => typeof cd[k] === 'function'), duration: cd.duration, counterMax: cd.counterMax,
		noCopy: cd.noCopy, onResidualOrder: cd.onResidualOrder, onFieldResidualOrder: cd.onFieldResidualOrder };
}

// random battle species pool: types / base stats / abilities
const sets = require(path + '/data/random-battles/gen4/sets.json');
out.gen4.species = {};
for (const id of Object.keys(sets)) {
	const s = dex4.species.get(id);
	out.gen4.species[id] = { name: s.name, types: s.types, baseStats: s.baseStats, abilities: s.abilities,
		weightkg: s.weightkg, num: s.num, sets: sets[id].sets.map(x => ({ role: x.role, movepool: x.movepool, abilities: x.abilities, preferredTypes: x.preferredTypes })) };
}

// hidden power derivation samples
out.gen4.hiddenpower = {};
for (const ty of dex4.types.all()) {
	if (ty.isNonstandard || !ty.HPivs) continue;
	const ivs = { hp: 31, atk: 31, def: 31, spa: 31, spd: 31, spe: 31, ...ty.HPivs };
	const hp = dex4.getHiddenPower(ivs);
	const ivs2 = { ...ivs, atk: (ivs.atk || 31) - 28 };
	const hp2 = dex4.getHiddenPower(ivs2);
	const ivs3 = { ...ivs, spe: (ivs.spe || 31) - 28 };
	const hp3 = dex4.getHiddenPower(ivs3);
	out.gen4.hiddenpower[ty.name] = { ivs, hp, atkMinus28: hp2, speMinus28: hp3 };
}

// format + rule table
const fmt = dex4.formats.get('gen4randombattle');
out.gen4.format = { name: fmt.name, mod: fmt.mod, team: fmt.team, ruleset: fmt.ruleset, gameType: fmt.gameType };
try {
	const rt = dex4.formats.getRuleTable(fmt);
	out.gen4.format.ruleTableKeys = Array.from(rt.keys());
} catch (e) { out.gen4.format.ruleTableError = String(e); }

// priority list for gen4-legal moves
out.gen4.priority = out.gen4.moves.filter(m => m.priority).map(m => [m.id, m.priority]).sort((a, b) => b[1] - a[1]);

fs.writeFileSync(OUT, JSON.stringify(out, null, 1));
console.log('wrote', OUT, 'moves', out.gen4.moves.length, 'species', Object.keys(out.gen4.species).length);
