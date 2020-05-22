#!/bin/bash

idx=0

if [[ -z "${SOURCECATCHER_NUM_BACKUPS}" ]]; then
  NUM_BACKUPS="10"
else
  NUM_BACKUPS="${SOURCECATCHER_NUM_BACKUPS}"
fi

for backup in $(find backups/ -mindepth 1 -maxdepth 1 | sort -r); do
  if [ $idx -lt ${NUM_BACKUPS} ]; then
    ((++idx))
  else
    echo "Removing backup $backup"
    rm -rf $backup
  fi
done
