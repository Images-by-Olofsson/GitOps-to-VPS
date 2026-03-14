#!/bin/sh
while true; do
    docker logs --tail 150 twitch-miner > /www/logs.txt 2>&1
    sleep 5
done
