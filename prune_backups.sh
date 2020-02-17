#!/bin/bash

idx=0

for backup in $(find backups/ -mindepth 1 -maxdepth 1 | sort -r); do
  if [ $idx -lt 10 ]; then
    ((++idx))
  else
    echo "Removing backup $backup"
    rm -rf $backup
  fi
done
