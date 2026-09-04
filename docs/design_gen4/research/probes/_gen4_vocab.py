# Data-only: reads poke-env's gen4 static tables + the vendored gen4 randbats sets.json.
# No Player/Env/PSClient, no network, no server.
import json, collections
from poke_env.data import GenData
SD = '/Users/nickgreenquist/Documents/Projects/pokemon-showdown-rl/showdown'
sets = json.load(open(SD + '/data/random-battles/gen4/sets.json'))
gd = GenData.from_gen(4)
dex, mv = gd.pokedex, gd.moves
out = {}
keys = list(sets)
out['pool_species_keys'] = len(keys)
nums = [dex[k]['num'] for k in keys]
out['pool_species_distinct_nums'] = len(set(nums))
out['pool_species_max_num'] = max(nums)
coll = collections.Counter(nums)
out['species_num_collisions'] = {n: sorted(k for k in keys if dex[k]['num'] == n) for n, c in coll.items() if c > 1}
moves = sorted({m for k in keys for s in sets[k]['sets'] for m in s['movepool']})
out['pool_moves'] = len(moves)
mnums = [mv[m]['num'] for m in moves]
out['pool_moves_distinct_nums'] = len(set(mnums))
out['pool_moves_max_num'] = max(mnums)
mc = collections.Counter(mnums)
out['move_num_collisions'] = {n: sorted(m for m in moves if mv[m]['num'] == n) for n, c in mc.items() if c > 1}
out['struggle_num'] = mv['struggle']['num']
out['pokedex_entries'] = len(dex)
out['moves_entries'] = len(mv)
out['gastrodoneast_num'] = dex.get('gastrodoneast', {}).get('num')
for k in ('castformsunny','castformrainy','castformsnowy','cherrimsunshine'):
    out[k + '_num'] = dex.get(k, {}).get('num')
out['rotom_nums'] = {k: dex[k]['num'] for k in ('rotom','rotomheat','rotomwash','rotomfrost','rotomfan','rotommow')}
out['deoxys_nums'] = {k: dex[k]['num'] for k in ('deoxys','deoxysattack','deoxysdefense','deoxysspeed')}
abil = sorted({a for k in keys for s in sets[k]['sets'] for a in s['abilities']})
out['pool_abilities'] = len(abil)
out['pool_abilities_list'] = abil
print(json.dumps(out, indent=1))
