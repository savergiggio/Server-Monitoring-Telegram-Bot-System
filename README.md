# SSH Connection Monitor con Web UI

Un'applicazione per il monitoraggio delle connessioni SSH con interfaccia web per la configurazione e notifiche Telegram.

## Caratteristiche

- Monitoraggio connessioni SSH e invio notifiche Telegram
- Interfaccia web per abilitare/disabilitare il monitoraggio
- Configurazione sicura delle credenziali Telegram
- Test della connessione Telegram
- Containerizzazione Docker per facilità di distribuzione

## Requisiti

- Docker
- Docker Compose

## Installazione e Avvio

1. Clona o scarica questo repository
2. Opzionalmente, modifica il file `.env` con le tue credenziali Telegram
3. Esegui il comando:

```bash
sudo docker-compose up -d
```

4. Accedi all'interfaccia web all'indirizzo `http://localhost:8080`

## Configurazione

È possibile configurare l'applicazione in due modi:

1. **Tramite interfaccia web**: inserisci il Bot Token e Chat ID di Telegram
2. **Tramite file .env**: modifica il file `.env` con le tue credenziali

## Comandi Utili

- **Avvio**: `sudo docker-compose up -d`
- **Stop**: `sudo docker-compose down`
- **Visualizzazione log**: `sudo docker-compose logs -f ssh-monitor`
- **Riavvio**: `sudo docker-compose restart ssh-monitor`