#!/bin/bash
# usage: extract_block.sh FILE id1 id2 ...  -- prints each top-level "\tid: {" ... "\t}," block with line numbers
FILE="$1"; shift
for id in "$@"; do
  awk -v id="$id" -v file="$FILE" '
    BEGIN { p=0 }
    p==0 && $0 ~ ("^\t" id ": \\{") { p=1; start=NR }
    p==1 { printf "%d\t%s\n", NR, $0 }
    p==1 && $0 ~ /^\t\},?$/ { printf "=== end %s (%s:%d-%d) ===\n", id, file, start, NR; p=2 }
    END { if (p==0) printf "=== NOT FOUND: %s in %s ===\n", id, file }
  ' "$FILE"
done
