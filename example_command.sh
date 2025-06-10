#!/bin/bash

# Script di esempio per testare la funzionalità comandi
# Questo script mostra informazioni di sistema di base

echo "=== Informazioni Sistema ==="
echo "Data e ora: $(date)"
echo "Uptime: $(uptime -p)"
echo "Utente corrente: $(whoami)"
echo "Directory corrente: $(pwd)"
echo ""
echo "=== Utilizzo Memoria ==="
free -h
echo ""
echo "=== Spazio Disco ==="
df -h | head -5
echo ""
echo "=== Processi Top 5 ==="
ps aux --sort=-%cpu | head -6
echo ""
echo "Script eseguito con successo!"