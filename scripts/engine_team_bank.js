// Generates gen1randombattle team PAIRS with Showdown itself, for the engine
// collector's team bank (docs/PKMN_ENGINE_RUST_PLAN.md §6.2).
//
// Borrowed: Pokémon Showdown (https://github.com/smogon/pokemon-showdown),
// MIT, vendored in this repo at showdown/ and pinned to 59da482e. Only
// `dist/sim` is loaded -- this starts NO server and opens NO socket.
//
// PAIRS, not single teams. `battleHasDitto` is a field on the TEAM GENERATOR,
// and PS creates exactly one generator per Battle and calls getTeam() twice
// (sim/battle.ts:3171-3177), so "at most one Ditto" is a property of the PAIR
// and is enforced by SKIPPING Ditto while picking the second team -- not by
// re-drawing it. Reusing one generator across many teams would silence Ditto
// after its first appearance; drawing the two teams independently would let two
// Dittos meet. Both are wrong, so the unit of the bank is the battle.
//
// Usage: node engine_team_bank.js <showdown_root> <n_pairs> <seed_hex_prefix>
// Writes one JSON line per pair to stdout: [[set,...],[set,...]]

'use strict';

const path = require('path');

const [, , showdownRoot, nPairsArg, seedPrefix] = process.argv;
if (!showdownRoot || !nPairsArg) {
	console.error('usage: engine_team_bank.js <showdown_root> <n_pairs> [seed_prefix]');
	process.exit(2);
}
const nPairs = parseInt(nPairsArg, 10);
const prefix = seedPrefix || 'e0e0';

const { Teams } = require(path.join(showdownRoot, 'dist/sim'));

// splitmix64, matching the Rust side's seed derivation (plan §7.5).
function splitmix64(x) {
	x = BigInt.asUintN(64, x + 0x9e3779b97f4a7c15n);
	let z = x;
	z = BigInt.asUintN(64, (z ^ (z >> 30n)) * 0xbf58476d1ce4e5b9n);
	z = BigInt.asUintN(64, (z ^ (z >> 27n)) * 0x94d049bb133111ebn);
	return BigInt.asUintN(64, z ^ (z >> 31n));
}

function slim(set) {
	return {
		s: set.species,
		l: set.level,
		m: set.moves,
		ia: set.ivs.atk,
		eh: set.evs.hp,
		ea: set.evs.atk,
	};
}

// BACKPRESSURE IS NOT OPTIONAL HERE. `process.stdout.write` to a pipe returns
// false when the kernel buffer is full, and ignoring that lets node queue the
// unwritten chunks on its own heap. At 5,000,000 pairs (~1.4 kB each) and a
// consumer that parses JSON, the queue outruns the default old-space limit and
// node dies MID-WRITE — which reaches the reader as a TRUNCATED LINE and a
// JSONDecodeError several hundred characters into a pair, not as an OOM
// message. That is exactly how the 2026-09-09 run failed at ~4 GB RSS.
// Awaiting 'drain' makes the generator run at the consumer's pace instead.
function write(chunk) {
	return new Promise((resolve) => {
		if (process.stdout.write(chunk)) resolve();
		else process.stdout.once('drain', resolve);
	});
}

async function main() {
	const out = [];
	for (let i = 0; i < nPairs; i++) {
		const h = splitmix64(BigInt(i)).toString(16).padStart(16, '0');
		const seed = `sodium,${prefix}${h}`;
		const gen = Teams.getGenerator('gen1randombattle', seed);
		const p1 = gen.getTeam().map(slim);
		const p2 = gen.getTeam().map(slim);
		out.push(JSON.stringify([p1, p2]));
		if (out.length >= 2000) {
			await write(out.join('\n') + '\n');
			out.length = 0;
		}
	}
	if (out.length) await write(out.join('\n') + '\n');
}

main().catch((e) => {
	console.error(e && e.stack ? e.stack : String(e));
	process.exit(1);
});
