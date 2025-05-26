## 🟢⚪🔴 *Per la versione italiana, clicca qui:* [README Italiano](README.it.md) 

# 🖥️ Telegram Server Monitor  
**Dockerized WebApp + Telegram Bot for Remote Server Monitoring and Control**

Telegram Server Monitor is a fully containerized application that provides a web-based GUI and a Telegram bot to monitor and manage your Linux server. It delivers real-time notifications about SSH/SFTP access, system resource usage, internet connectivity, and Docker container management. The solution enables both remote monitoring and control directly from your browser or Telegram.

---
## 🛠️ Requirements

- Docker and Docker Compose installed on a Linux server (Debian/Ubuntu recommended).
- Telegram Bot Token (create one via [@BotFather](https://t.me/BotFather)).
- Telegram ChatID (get from [@myidbot](https://t.me/IDBot))
  
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

The GUI is organized into tabs for simple and clear management:

### 📊 Monitoring
- Tracks SSH/SFTP connections.
- Sends immediate Telegram notifications for each new login.

### 🤖 Telegram
- Set the Telegram Bot Token and Chat ID.
- View the complete list of supported commands.

### 🚨 System Alert
- Enable/disable system monitoring.
- View live metrics: CPU, RAM, CPU temperature, mount point status.
- Configure alert thresholds for CPU, RAM, CPU temperature, and disk space.
- Enable reminders for persistent alert states.
- Monitor internet connection with disconnection/reconnection notifications.

### 📂 Mount Points
- Manage mount points used by Telegram bot commands:
  - `/upload` (directory from which to upload files)
  - `/download` (directory where files are downloaded)
- No backend manual configuration required.

### 🌍 Languages
- Manage interface and bot languages.
- Upload JSON files to add new languages.
- Dynamically change the active language for both GUI and bot.

### ℹ️ Info
- General information about the app, version, and system.
- Links to documentation and support.




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



