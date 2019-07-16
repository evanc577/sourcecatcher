#!/bin/bash

idx=0

for dir in $(find backups/* -type d | sort -r); do
  if [ $idx -lt 10 ]; then
    ((++idx))
  else
    rm -rf $dir
  fi
done
