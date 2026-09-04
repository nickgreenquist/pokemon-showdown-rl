// Offline generator sample: runs the vendored gen4 random-team generator N times with a fixed PRNG seed.
// No server, no battle, no network. Run under nice -n 19.
const SD = '/Users/nickgreenquist/Documents/Projects/pokemon-showdown-rl/showdown';
const { Teams } = require(SD + '/dist/sim/teams');
const N = parseInt(process.argv[2] || '2000', 10);
const gen = Teams.getGenerator('gen4randombattle', [1, 2, 3, 4]);
const cnt = { items: {}, species: {}, levels: {}, abilities: {}, moves: {}, roles: {}, natures: {}, nMoves: {}, evsHp: {}, ivsAtk: {}, ivsSpe: {}, shiny: 0, teamSize: {}, level100PerTeam: {}, gender: {} };
const bump = (o, k) => { o[k] = (o[k] || 0) + 1; };
let nMon = 0;
for (let i = 0; i < N; i++) {
	const team = gen.getTeam();
	bump(cnt.teamSize, team.length);
	let n100 = 0;
	for (const p of team) {
		nMon++;
		bump(cnt.items, p.item);
		bump(cnt.species, p.species);
		bump(cnt.levels, p.level);
		bump(cnt.abilities, p.ability);
		bump(cnt.roles, p.role);
		bump(cnt.natures, String(p.nature));
		bump(cnt.nMoves, p.moves.length);
		bump(cnt.evsHp, p.evs.hp);
		bump(cnt.ivsAtk, p.ivs.atk);
		bump(cnt.ivsSpe, p.ivs.spe);
		bump(cnt.gender, String(p.gender));
		if (p.shiny) cnt.shiny++;
		if (p.level === 100) n100++;
		for (const m of p.moves) bump(cnt.moves, m);
	}
	bump(cnt.level100PerTeam, n100);
}
const sortObj = o => Object.fromEntries(Object.entries(o).sort((a, b) => b[1] - a[1]));
const out = {
	N, nMon,
	teamSize: cnt.teamSize,
	nMoves: cnt.nMoves,
	natures: cnt.natures,
	shinyRate: cnt.shiny / nMon,
	level100PerTeam: cnt.level100PerTeam,
	evsHp: sortObj(cnt.evsHp),
	ivsAtk: sortObj(cnt.ivsAtk),
	ivsSpe: sortObj(cnt.ivsSpe),
	gender: cnt.gender,
	nDistinctItems: Object.keys(cnt.items).length,
	items: sortObj(cnt.items),
	nDistinctSpecies: Object.keys(cnt.species).length,
	nDistinctAbilities: Object.keys(cnt.abilities).length,
	nDistinctMoves: Object.keys(cnt.moves).length,
	roles: sortObj(cnt.roles),
	levels: Object.fromEntries(Object.entries(cnt.levels).sort((a, b) => a[0] - b[0])),
	speciesTop15: Object.entries(sortObj(cnt.species)).slice(0, 15),
	speciesBottom15: Object.entries(sortObj(cnt.species)).slice(-15),
	movesTop20: Object.entries(sortObj(cnt.moves)).slice(0, 20),
	hpMoves: Object.entries(cnt.moves).filter(([m]) => m.startsWith('hiddenpower')),
	formeSpecies: Object.entries(cnt.species).filter(([s]) => s.includes('-')),
};
console.log(JSON.stringify(out, null, 1));
