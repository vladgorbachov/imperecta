#!/bin/sh
# stdin/stdout filter for git filter-branch / filter-repo message rewrites.
sed -E '/^[[:space:]]*Made-with:[[:space:]]*Cursor[[:space:]]*$/Id'
sed -E '/^[[:space:]]*Co-authored-by:[[:space:]]*Cursor[[:space:]]*<cursoragent@cursor\.com>[[:space:]]*$/Id'
sed -E '/cursoragent@cursor\.com/Id'
