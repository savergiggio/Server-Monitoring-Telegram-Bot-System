#!/bin/bash
set -e

# Assicurati che le directory necessarie esistano e siano scrivibili
mkdir -p /etc/ssh_monitor
mkdir -p /var/lib/ssh_monitor

# Verifica se ci sono le variabili d'ambiente e crea config.ini
if [ -n "$TELEGRAM_BOT_TOKEN" ] && [ -n "$TELEGRAM_CHAT_ID" ]; then
    echo "Creazione configurazione da variabili d'ambiente..."
    cat > /etc/ssh_monitor/config.ini << EOF
[Telegram]
bot_token = $TELEGRAM_BOT_TOKEN
chat_id = $TELEGRAM_CHAT_ID

[Monitor]
check_interval = ${CHECK_INTERVAL:-10}
hostname = ${HOSTNAME:-$(hostname)}
local_ip = ${LOCAL_IP:-$(hostname -I | awk '{print $1}')}

[Logs]
auth_log = ${AUTH_LOG:-/var/log/auth.log}
fail_log = ${FAIL_LOG:-/var/log/faillog}
EOF
else
    # Verifica se esiste già un file config.ini
    if [ ! -f /etc/ssh_monitor/config.ini ]; then
        echo "ATTENZIONE: Variabili d'ambiente TELEGRAM_BOT_TOKEN e TELEGRAM_CHAT_ID non impostate."
        echo "Verrà creato un file config.ini di default che dovrà essere modificato tramite l'interfaccia web."
        
        # Crea config.ini di default
        cat > /etc/ssh_monitor/config.ini << EOF
[Telegram]
bot_token = 
chat_id = 

[Monitor]
check_interval = 10
hostname = $(hostname)
local_ip = $(hostname -I | awk '{print $1}')

[Logs]
auth_log = /var/log/auth.log
fail_log = /var/log/faillog
EOF
    fi
fi

# Verifica se esiste il file di stato del monitoraggio
if [ ! -f /var/lib/ssh_monitor/monitor_status.json ]; then
    echo "Creazione file di stato del monitoraggio..."
    echo '{"enabled": true}' > /var/lib/ssh_monitor/monitor_status.json
fi

echo "Avvio server web e monitoraggio SSH..."
# Esegui l'applicazione
exec gunicorn --bind 0.0.0.0:5000 --workers 1 --threads 2 app:app