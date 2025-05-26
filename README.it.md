
## 🔵🔴*For the english version, check this:* [README English](README.md) 

# 🖥️ Telegram Server Monitor  
**WebApp Dockerizzata + Bot Telegram per il monitoraggio e il controllo remoto del server**

Telegram Server Monitor è un'applicazione completamente containerizzata che fornisce una GUI web e un bot Telegram per monitorare e gestire il tuo server Linux. Fornisce notifiche in tempo reale su accessi SSH/SFTP, utilizzo delle risorse di sistema, connettività internet e gestione dei container Docker. La soluzione consente sia il monitoraggio che il controllo remoto direttamente dal browser o da Telegram.

---
## 🛠️ Requisiti

- Docker e Docker Compose installati su un server Linux (Debian/Ubuntu consigliati).
- Token del Bot Telegram (creane uno tramite [@BotFather](https://t.me/BotFather)).
- ChatID Telegram (ottienilo da [@myidbot](https://t.me/IDBot))
  
## 📦 Installazione

1. **Clona il repository:**:
   ```bash
   git clone https://github.com/savergiggio/Server-Monitoring-Telegram-Bot-System.git
   cd Server-Monitoring-Telegram-Bot-System

2. **Modifica docker-compose.yml prima di eseguire (altamente consigliato):**:
   
     - *Monta le tue directory locali da usare come punti di mount nell'app, per upload/download file:*
     - *Cambia il mapping della porta predefinita (es. 8082:5000) se necessario per evitare conflitti.*
     - *Imposta il tuo fuso orario nelle variabili d'ambiente:*
     - *Specifica il tuo IP locale nella configurazione o nell’ambiente, se richiesto per la comunicazione del bot.*
   
   ```bash
   
    volumes:
    #UPLOADS
       - /home/user/folder1_upload:/home/user/folder1_upload
    #DOWNLOADS
       - /home/user/folder2_download:/home/user/folder2_download
    environment:
       - TZ=Europe/Rome
       - LOCAL_IP=YOURLOCALIP
   
3. **Build e avvia l'app con Docker Compose:**:
   ```bash
   sudo docker-compose build
   sudo docker-compose up -d
4. **Accedi alla GUI Web nel tuo browser all’indirizzo:**:
   ```bash
   http://localhost:8082 (or your configured IP and port)



## 🌐 Funzionalità GUI Web

La GUI è suddivisa in tab per una gestione semplice e chiara:

### 📊 Monitoring
- Traccia connessioni SSH/SFTP.
- Invia notifiche Telegram immediate a ogni nuovo login.

### 🤖 Telegram
- Imposta Token Bot Telegram e Chat ID.
- Visualizza la lista completa dei comandi supportati.

### 🚨 System Alert
- Attiva/disattiva il monitoraggio di sistema.
- Visualizza metriche live: CPU, RAM, temperatura CPU, stato mount point.
- Configura soglie di allerta per CPU, RAM, temperatura CPU, spazio disco.
- Abilita promemoria per stati di allerta persistenti.
- Monitora connessione internet con notifiche di disconnessione/riconnessione.

### 📂 Mount Points
- Gestisci mount point usati dai comandi bot Telegram:
  - `/upload` (directory da cui caricare file)
  - `/download` (directory in cui scaricare file)
- Nessuna configurazione manuale backend necessaria.

### 🌍 Languages
- Gestisci lingue dell’interfaccia e del bot.
- Carica file JSON per aggiungere lingue.
- Cambia lingua attiva dinamicamente per GUI e bot.

### ℹ️ Info
- Informazioni generali su app, versione e sistema.
- Link a documentazione e supporto.



## 🤖 Funzionalità del Bot Telegram

### 🛡️ Notifiche  
Ricevi allarmi in tempo reale per:
- Accessi SSH/SFTP
- CPU, RAM, and temperatura thresholds  
- Utilizzo dello spazio su disco
- Perdita e ripristino della connettività internet

### 📊 Comandi di Monitoraggio
Ricevi lo stato attuale di CPU, RAM, spazio su disco e rete tramite comandi del bot.

### 🐳 Gestione dei Container Docker
- Elenca i container in esecuzione
- Avvia e ferma container
- Visualizza i log di specifici container 

### 🔁 Controllo del Server  
Riavvia il server con un comando dedicato del bot.

### 📂 Operazioni su File  
Carica e scarica file dai punti di mount configurati tramite bot Telegram.
