# 🖥️ Telegram Server Monitor  
**Dockerized WebApp + Telegram Bot for Remote Server Monitoring and Control**

Telegram Server Monitor is a fully containerized application that provides a web-based GUI and a Telegram bot to monitor and manage your Linux server. It delivers real-time notifications about SSH/SFTP access, system resource usage, internet connectivity, and Docker container management. The solution enables both remote monitoring and control directly from your browser or Telegram.

---
## 🛠️ Requirements

- Docker and Docker Compose installed on a Linux server (Debian/Ubuntu recommended).
- Telegram Bot Token (create one via [@BotFather](https://t.me/BotFather)).
- Telegram Chat ID (user or group) for receiving notifications.
- 
## 📦 Installation

1. **Clone the repository**:
   ```bash
   git clone https://github.com/savergiggio/Server-Monitoring-Telegram-Bot-System.git
   cd Server-Monitoring-Telegram-Bot-System

2. **Edit *docker-compose.yml* before running (highly recommended):**:
   
     - *Mount your local directories to be used as mount points in the app, for file upload/download:*
     - *Change the default port mapping (e.g., 8082:5000) if needed to avoid conflicts.*
     - *Set your timezone in the environment variables:*
     - *Specify your local IP address in the config or environment if required for bot communication.*
   
   ```bash
   
    volumes:
    #UPLOADS
       - /home/user/folder1_upload:/home/user/folder1_upload
    #DOWNLOADS
       - /home/user/folder2_download:/home/user/folder2_download
    environment:
       - TZ=Europe/Rome
       - LOCAL_IP=YOURLOCALIP
   
3. **Build and Start the app with Docker Compose:**:
   ```bash
   sudo docker-compose build
   sudo docker-compose up -d
4. **Access the Web GUI in your browser at:**:
   ```bash
   http://localhost:8082 (or your configured IP and port)



## 🌐 Web GUI Features

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



## 🤖 Telegram Bot Features

### 🛡️ Notifications  
Receive real-time alerts for:  
- SSH/SFTP access  
- CPU, RAM, and temperature thresholds  
- Disk space usage  
- Internet connectivity loss and restoration  

### 📊 System Monitoring Commands  
Get current CPU, RAM, disk usage, and network status via bot commands.

### 🐳 Docker Container Management  
- List running containers  
- Start and stop containers  
- View logs of specific containers  

### 🔁 Server Control  
Reboot your server using a dedicated bot command.

### 📂 File Operations  
Upload and download files to/from configured mount points via the Telegram bot.



