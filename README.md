## 🟢⚪🔴 *Per la versione italiana, clicca qui:* [README Italiano](README.it.md) 

# 🖥️ Telegram Server Monitor  
**Dockerized WebApp + Telegram Bot for Remote Server Monitoring and Control**

Telegram Server Monitor is a fully containerized application that provides a web-based GUI and a Telegram bot to monitor and manage your Linux server. It delivers real-time notifications about SSH/SFTP access, system resource usage, internet connectivity, and Docker container management. The solution enables both remote monitoring and control directly from your browser or Telegram.

---
## 🛠️ Requirements

- Docker and Docker Compose installed on a Linux server (Debian/Ubuntu recommended).
- Telegram Bot Token (create one via [@BotFather](https://t.me/BotFather)).
- Telegram ChatID (get from [@myidbot](https://t.me/IDBot))
---  
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

---
## 🌐 Web GUI Features

The GUI is organized into tabs for simple and clear management:

<div align="center">
   
 ## 📸 CLICK   TO   VIEW  GUI SCREENSHOTS
<details>
   <img src="Screen/Screenshot (19).png" alt="Monitoring Tab Screenshot" style="width:100%;" />
</details>
</div>

### 📊 Monitoring
- Tracks SSH/SFTP connections.
- Sends instant Telegram notifications for each new login, including details such as the external IP address, username, host name, internal IP, timestamp, and a link to more information about the IP (via ipinfo.io).
  
<div align="center">
   
 ## 📸 CLICK   TO   VIEW  GUI SCREENSHOTS
<details>
   <img src="Screen/Screenshot (17).png" alt="Monitoring Tab Screenshot" style="width:100%;" />
</details>
</div>
<div align="center">
   
 ## 📸 CLICK   TO   VIEW  BOT SCREENSHOTS
<details>
   <img src="Screen/IMG_20250525_233124_LI.jpg" alt="Monitoring Tab Screenshot" style="width:50%;" />
</details>
</div>

### 🤖 Telegram
- Set the Telegram Bot Token and Chat ID.
- View the complete list of supported commands.
  
<div align="center">
   
 ## 📸 CLICK   TO   VIEW  GUI SCREENSHOTS
<details>
   <img src="Screen/Screenshot (18).png" alt="Monitoring Tab Screenshot" style="width:100%;" />
</details>
</div>

### 🚨 System Alert
- Enable/disable system monitoring.
- View live metrics: CPU, RAM, CPU temperature, mount point status.
- Configure alert thresholds for CPU, RAM, CPU temperature, and disk space.
- Enable reminders for persistent alert states.
- Sends a new notification when a previously exceeded threshold returns to normal.
- Monitor internet connection with disconnection/reconnection notifications.

<div align="center">
   
 ## 📸 CLICK   TO   VIEW GUI SCREENSHOTS
<details>
   <img src="Screen/Screenshot (19).png" alt="Monitoring Tab Screenshot" style="width:80%" />
</details>
</div>
<div align="center">
   
 ## 📸 CLICK   TO   VIEW GUI SCREENSHOTS
<details>
   <img src="Screen/Screenshot (20).png" alt="Monitoring Tab Screenshot" style="width:80%;" />
</details>
</div>
<div align="center">
   
 ## 📸 CLICK   TO   VIEW GUI SCREENSHOTS
<details>
   <img src="Screen/Screenshot (21).png" alt="Monitoring Tab Screenshot" style="width:80%;" />
</details>
</div>

### 📂 Mount Points
- Manage mount points used by Telegram bot commands:
  - `/upload` (directory from which to upload files)
  - `/download` (directory where files are downloaded)
- Also used to monitor disk usage and trigger alerts when space thresholds are exceeded.

<div align="center">
   
 ## 📸 CLICK   TO   VIEW  GUI SCREENSHOTS
<details>
   <img src="Screen/Screenshot (22).png" alt="Monitoring Tab Screenshot" style="width:80%;" />
</details>
</div>

### 🌍 Languages
- Manage interface and bot languages.
- Upload JSON files to add new languages.
- Dynamically change the active language for both GUI and bot.
- All button labels and alert messages (in both the bot and the GUI) can be fully customized through the JSON language files.

<div align="center">
   
 ## 📸 CLICK   TO   VIEW  GUI SCREENSHOTS
<details>
   <img src="Screen/10.png" alt="Monitoring Tab Screenshot" style="width:80%;" />
</details>
</div>


---
## 🤖 Telegram Bot Features

### 🛡️ Notifications  
Receive real-time alerts for:  
- SSH/SFTP access  
- CPU, RAM, and temperature thresholds  
- Disk space usage  
- Internet connectivity restoration  

### 📊 System Monitoring Commands  
Get current CPU, RAM, disk usage, and network status via bot commands.

### 🐳 Docker Container Management  
- List running containers  
- Start, Pause and Stop containers
- View container configuration

### 📂 File Operations  
Upload and download files to/from the server via the configured mount points via the Telegram bot.

### 🔁 Server Control  
Reboot your server using a dedicated bot command.



