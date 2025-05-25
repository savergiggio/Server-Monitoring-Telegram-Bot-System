# Server Monitoring Telegram Bot System

## 📝 Descrizione
Server Monitoring Telegram Bot System è un'applicazione web che permette di monitorare lo stato del tuo server attraverso Telegram. Il sistema controlla costantemente i punti di mount specificati e ti avvisa tramite Telegram quando lo spazio disponibile scende sotto una soglia definita.

## ✨ Caratteristiche Principali

### 🔍 Monitoraggio Server
- Monitoraggio continuo dei punti di mount configurati
- Notifiche Telegram personalizzabili quando lo spazio disponibile è basso
- Possibilità di definire soglie di avviso personalizzate per ogni punto di mount
- Monitoraggio in tempo reale dello stato del sistema

### 🤖 Integrazione Telegram
- Configurazione semplice del bot Telegram
- Test di connessione integrato
- Notifiche immediate e affidabili
- Comandi bot per controllare lo stato del sistema

### 🌐 Interfaccia Web
- Dashboard intuitiva per la gestione del sistema
- Configurazione semplice dei punti di mount
- Gestione delle impostazioni di monitoraggio
- Supporto multi-lingua (Italiano e Inglese)
- Tema chiaro/scuro

### ⚙️ Configurazione Flessibile
- Gestione dei punti di mount tramite interfaccia web
- Configurazione delle soglie di avviso
- Personalizzazione delle notifiche
- Gestione delle lingue del sistema

## 🚀 Installazione

### Prerequisiti
- Docker e Docker Compose installati sul sistema
- Un bot Telegram (creato tramite @BotFather)
- Il token del bot e l'ID della chat Telegram dove ricevere le notifiche

### Installazione con Docker Compose

1. Clona il repository:
```bash
git clone https://github.com/tuouser/server-monitoring-telegram-bot.git
cd server-monitoring-telegram-bot
```

2. Build del container:
```bash
sudo docker-compose build
```

3. Avvia il container:
```bash
sudo docker-compose up -d
```

4. Accedi all'interfaccia web:
```
http://tuo_ip:8082
```

### Installazione con Portainer

1. Accedi alla tua istanza Portainer

2. Vai su "Stacks" e clicca "Add stack"

3. Dai un nome allo stack (es. "server-monitoring")

4. Copia e incolla il seguente codice di docker-compose.yml nel campo "Web editor":

5. Clicca "Deploy the stack"

6. Accedi all'interfaccia web:
```
http://tuo_ip:8082
```

## 📱 Configurazione Iniziale

1. Accedi all'interfaccia web
2. Inserisci il token del bot e l'ID della chat Telegram
3. Clicca "Test Connection" per verificare la connessione
4. Salva le impostazioni
5. Aggiungi i punti di mount da monitorare
6. Configura le soglie di avviso per ogni punto di mount

## 🛠️ Configurazione Avanzata

### Punti di Mount
- Aggiungi/rimuovi punti di mount da monitorare
- Imposta soglie personalizzate per ogni punto
- Configura messaggi di avviso personalizzati

### Notifiche
- Personalizza il formato dei messaggi
- Imposta la frequenza delle notifiche
- Configura le condizioni di trigger

### Sistema
- Cambia la lingua dell'interfaccia
- Attiva/disattiva il tema scuro
- Gestisci le impostazioni di sistema

## 🤝 Contribuire
Siamo aperti a contributi! Se vuoi migliorare questo progetto:

1. Fai un fork del repository
2. Crea un branch per la tua feature
3. Committa le tue modifiche
4. Apri una Pull Request

## 📄 Licenza
Questo progetto è distribuito sotto licenza MIT. Vedi il file `LICENSE` per maggiori dettagli.

## 📸 Screenshot
[Screenshots della GUI e del bot verranno aggiunti qui]
