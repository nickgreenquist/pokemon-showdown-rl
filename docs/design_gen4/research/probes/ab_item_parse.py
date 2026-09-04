# Parses PS data files (text only, no imports of PS). Produces per-ability/per-item facts.
import json, re, sys, os
SD='/Users/nickgreenquist/Documents/Projects/pokemon-showdown-rl/showdown/data'

def blocks(path):
    """Return {id: (startline, endline, text)} for top-level `\tid: {` ... `\t},` blocks."""
    lines=open(path).read().split('\n')
    out={}
    i=0
    while i < len(lines):
        m=re.match(r'^\t([a-z0-9]+): \{\s*$', lines[i])
        if m:
            key=m.group(1); start=i
            j=i+1
            while j < len(lines) and not re.match(r'^\t\},?\s*$', lines[j]):
                j+=1
            out[key]=(start+1, j+1, '\n'.join(lines[start:j+1]))
            i=j+1
        else:
            i+=1
    return out

def handlers(text):
    return sorted(set(re.findall(r'^\t\t(on[A-Za-z]+|condition|flags|isBreakable|suppressWeather|isPermanent)\b', text, re.M)))

def removed(text):
    return sorted(set(re.findall(r'^\t\t(on[A-Za-z]+): undefined', text, re.M)))

def msgs(text):
    out=set()
    for m in re.findall(r"this\.add\(\s*'(-?[a-z]+)'([^\n]*)", text):
        tag=m[0]
        extra=re.findall(r"'([^']+)'", m[1])
        out.add((tag, tuple(extra[:2])))
    return sorted(out)

base_ab=blocks(SD+'/abilities.ts')
g4_ab=blocks(SD+'/mods/gen4/abilities.ts')
base_it=blocks(SD+'/items.ts')
g4_it=blocks(SD+'/mods/gen4/items.ts')
# text descriptions
txt_ab=blocks(SD+'/text/abilities.ts')
txt_it=blocks(SD+'/text/items.ts')

def shortdesc(tb, key):
    if key not in tb: return None
    t=tb[key][2]
    g4=re.search(r'gen4: \{(.*?)\n\t\t\},', t, re.S)
    if g4:
        sd=re.search(r'shortDesc: "([^"]*)"', g4.group(1))
        if sd: return ('gen4', sd.group(1))
    # gen5/6/7 blocks apply to <= that gen; take the lowest-gen block >= 4? use gen4 else gen5 else base
    for g in ('gen5','gen6','gen7'):
        gm=re.search(g+r': \{(.*?)\n\t\t\},', t, re.S)
        if gm:
            sd=re.search(r'shortDesc: "([^"]*)"', gm.group(1))
            if sd: return (g, sd.group(1))
    sd=re.search(r'^\t\tshortDesc: "([^"]*)"', t, re.M)
    return ('base', sd.group(1)) if sd else None

mode=sys.argv[1]
names=json.load(open(sys.argv[2]))
BB = base_ab if mode=='ab' else base_it
GG = g4_ab if mode=='ab' else g4_it
TT = txt_ab if mode=='ab' else txt_it
FB = '/abilities.ts' if mode=='ab' else '/items.ts'
FG = '/mods/gen4/abilities.ts' if mode=='ab' else '/mods/gen4/items.ts'
for n in names:
    k=re.sub(r'[^a-z0-9]','',n.lower())
    b=BB.get(k); g=GG.get(k)
    print('###', n, '|', k)
    if b: print('  base', FB+':%d-%d'%(b[0],b[1]), 'handlers=', handlers(b[2]))
    else: print('  base MISSING')
    if g:
        print('  gen4', FG+':%d-%d'%(g[0],g[1]), 'handlers=', handlers(g[2]), 'REMOVED=', removed(g[2]))
    sd=shortdesc(TT,k)
    if sd: print('  desc[%s]: %s'%sd)
    mm = msgs(g[2]) if g else []
    mb = msgs(b[2]) if b else []
    print('  msgs_base=', mb)
    if g: print('  msgs_gen4=', mm)
