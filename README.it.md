
## 🔵🔴*For the english version, check this:* [README English](README.md) 

# 🖥️ Telegram Server Monitor  
**WebApp Dockerizzata + Bot Telegram per il monitoraggio e il controllo remoto del server**

Telegram Server Monitor è un'applicazione completamente containerizzata che fornisce una GUI web e un bot Telegram per monitorare e gestire il tuo server Linux. Fornisce notifiche in tempo reale su accessi SSH/SFTP, utilizzo delle risorse di sistema, connettività internet e gestione dei container Docker. La soluzione consente sia il monitoraggio che il controllo remoto direttamente dal browser o da Telegram.

---
## 🌐 Funzionalità dell'interfaccia Web

La GUI è organizzata in schede per una gestione semplice e chiara:

### 📊 Monitoraggio
- Tiene traccia delle connessioni SSH/SFTP.
- Invia notifiche Telegram istantanee per ogni nuovo login, inclusi dettagli come l'indirizzo IP esterno, nome utente, nome host, IP interno, timestamp e un link per maggiori informazioni sull'IP (tramite ipinfo.io).
IMMAGINE
### 🤖 Telegram
- Imposta il Token del Bot Telegram e il Chat ID.
- Visualizza la lista completa dei comandi supportati.

### 🚨 Allarme di Sistema
- Attiva/disattiva il monitoraggio del sistema.
- Visualizza metriche in tempo reale: CPU, RAM, temperatura della CPU, stato dei punti di mount.
- Configura le soglie di allarme per CPU, RAM, temperatura della CPU e spazio su disco.
- Attiva promemoria per stati di allarme persistenti.
- Invia una nuova notifica quando una soglia precedentemente superata ritorna alla normalità.
- Monitora la connessione internet con notifiche di disconnessione/riconnessione.

### 📂 Punti di Mount
- Gestisci i punti di mount utilizzati dai comandi del bot Telegram:
  - `/upload` (directory da cui caricare i file)
  - `/download` (directory in cui vengono scaricati i file)
- Utilizzati anche per monitorare l'uso del disco e attivare allarmi quando vengono superate le soglie di spazio.

### 🌍 Lingue
- Gestisci le lingue dell'interfaccia e del bot.
- Carica file JSON per aggiungere nuove lingue.
- Cambia dinamicamente la lingua attiva sia per la GUI che per il bot.
- Tutte le etichette dei pulsanti e i messaggi di allarme (sia nel bot che nella GUI) possono essere completamente personalizzati tramite i file JSON delle lingue.

---
## 🤖 Funzionalità del Bot Telegram

### 🛡️ Notifiche  
Ricevi avvisi in tempo reale per:  
- Accessi SSH/SFTP  
- Superamento soglie di CPU, RAM e temperatura  
- Utilizzo dello spazio su disco  
- Ripristino della connettività internet  

### 📊 Comandi di Monitoraggio del Sistema  
Ottieni lo stato corrente di CPU, RAM, uso del disco e stato della rete tramite comandi del bot.

### 🐳 Gestione dei Container Docker  
- Elenca i container in esecuzione  
- Avvia, metti in pausa e ferma i container
- Visualizza la configurazione dei container

### 📂 Operazioni sui File  
Carica e scarica file da/sul server tramite i punti di mount configurati, utilizzando il bot Telegram.

### 🔁 Controllo del Server  
Riavvia il tuo server utilizzando un comando dedicato del bot.

---
## 🛠️ Requisiti

- Docker e Docker Compose installati su un server Linux (Debian/Ubuntu consigliati).
- Token del Bot Telegram (creane uno tramite [@BotFather](https://t.me/BotFather)).
- ChatID Telegram (ottienilo da [@myidbot](https://t.me/IDBot))
---  
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

