document.addEventListener('DOMContentLoaded', function() {
    // Funzione per ottenere traduzioni
    function getTranslation(key) {
        const keys = key.split('.');
        let value = window.translations;
        
        for (const k of keys) {
            if (value && typeof value === 'object' && k in value) {
                value = value[k];
            } else {
                return key; // Ritorna la chiave se non trova la traduzione
            }
        }
        
        return value;
    }
    
    // Toggle del monitoraggio
    const monitorToggle = document.getElementById('monitorToggle');
    const statusText = document.getElementById('statusText');
    
    // Toggle della visibilità per i campi password
    const toggleBotToken = document.getElementById('toggleBotToken');
    const toggleChatId = document.getElementById('toggleChatId');
    const botTokenInput = document.getElementById('botToken');
    const chatIdInput = document.getElementById('chatId');
    
    // Pulsanti azione
    const testConnectionBtn = document.getElementById('testConnection');
    const telegramForm = document.getElementById('telegramForm');
    
    // Elementi per la gestione dei punti di mount upload
    const uploadMountPointsContainer = document.getElementById('uploadMountPoints');
    const newUploadMountPathInput = document.getElementById('newUploadMountPath');
    const addUploadMountPointBtn = document.getElementById('addUploadMountPoint');
    const saveUploadMountPointsBtn = document.getElementById('saveUploadMountPoints');
    
    // Elementi per la gestione dei punti di mount download
    const downloadMountPointsContainer = document.getElementById('downloadMountPoints');
    const newDownloadMountPathInput = document.getElementById('newDownloadMountPath');
    const addDownloadMountPointBtn = document.getElementById('addDownloadMountPoint');
    const saveDownloadMountPointsBtn = document.getElementById('saveDownloadMountPoints');
    
    // Alert per i messaggi
    const alertMessage = document.getElementById('alertMessage');
    
    // Variabili per i punti di mount
    let mountPoints = [];
    
    // Funzione per mostrare messaggi
    function showMessage(message, type = 'info') {
        alertMessage.textContent = message;
        alertMessage.className = `alert alert-${type} mt-4`;
        alertMessage.classList.remove('d-none');
        
        // Nascondi il messaggio dopo 5 secondi
        setTimeout(() => {
            alertMessage.classList.add('d-none');
        }, 5000);
    }
    
    // Toggle del monitoraggio
    if (monitorToggle) {
        monitorToggle.addEventListener('change', function() {
            const isEnabled = this.checked;
            
            // Aggiorna l'interfaccia
            statusText.textContent = isEnabled ? 'Attivo' : 'Disattivato';
            statusText.className = isEnabled ? 'text-success' : 'text-danger';
            
            // Invia la richiesta API
            fetch('/api/monitor', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ enabled: isEnabled })
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    showMessage(`Monitoraggio ${isEnabled ? 'attivato' : 'disattivato'} con successo`, 'success');
                } else {
                    showMessage(`Errore: ${data.message}`, 'danger');
                    // Ripristina lo stato del toggle in caso di errore
                    this.checked = !isEnabled;
                }
            })
            .catch(error => {
                console.error('Error:', error);
                showMessage('Errore di connessione al server', 'danger');
                // Ripristina lo stato del toggle in caso di errore
                this.checked = !isEnabled;
            });
        });
    }
    
    // Toggle della visibilità dei campi password
    if (toggleBotToken) {
        toggleBotToken.addEventListener('click', function() {
            const type = botTokenInput.getAttribute('type') === 'password' ? 'text' : 'password';
            botTokenInput.setAttribute('type', type);
            this.querySelector('i').className = type === 'password' ? 'bi bi-eye' : 'bi bi-eye-slash';
        });
    }
    
    if (toggleChatId) {
        toggleChatId.addEventListener('click', function() {
            const type = chatIdInput.getAttribute('type') === 'password' ? 'text' : 'password';
            chatIdInput.setAttribute('type', type);
            this.querySelector('i').className = type === 'password' ? 'bi bi-eye' : 'bi bi-eye-slash';
        });
    }
    
    // Test della connessione Telegram
    if (testConnectionBtn) {
        testConnectionBtn.addEventListener('click', function() {
            const botToken = botTokenInput.value.trim();
            const chatId = chatIdInput.value.trim();
            
            if (!botToken || !chatId) {
                showMessage('Inserisci sia il Bot Token che il Chat ID', 'warning');
                return;
            }
            
            // Mostra messaggio di caricamento
            showMessage('Test in corso...', 'info');
            
            // Disabilita il pulsante durante il test
            this.disabled = true;
            
            // Invia la richiesta API
            fetch('/api/test-telegram', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ bot_token: botToken, chat_id: chatId })
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    showMessage('Connessione Telegram riuscita! Verifica il messaggio di test ricevuto sul tuo dispositivo.', 'success');
                } else {
                    showMessage(`Errore: ${data.message}`, 'danger');
                }
            })
            .catch(error => {
                console.error('Error:', error);
                showMessage('Errore di connessione al server', 'danger');
            })
            .finally(() => {
                // Riabilita il pulsante
                this.disabled = false;
            });
        });
    }
    
    // Salvataggio delle credenziali Telegram
    if (telegramForm) {
        telegramForm.addEventListener('submit', function(e) {
            e.preventDefault();
            
            const botToken = botTokenInput.value.trim();
            const chatId = chatIdInput.value.trim();
            
            if (!botToken || !chatId) {
                showMessage('Inserisci sia il Bot Token che il Chat ID', 'warning');
                return;
            }
            
            // Invia la richiesta API
            fetch('/api/telegram', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ bot_token: botToken, chat_id: chatId })
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    showMessage('Credenziali Telegram salvate con successo', 'success');
                    
                    // Maschera i valori dopo il salvataggio
                    setTimeout(() => {
                        botTokenInput.type = 'password';
                        chatIdInput.type = 'password';
                        toggleBotToken.querySelector('i').className = 'bi bi-eye';
                        toggleChatId.querySelector('i').className = 'bi bi-eye';
                    }, 1000);
                    
                    // Riavvia il bot Telegram
                    restartTelegramBot();
                } else {
                    showMessage(`Errore: ${data.message}`, 'danger');
                }
            })
            .catch(error => {
                console.error('Error:', error);
                showMessage('Errore di connessione al server', 'danger');
            });
        });
    }
    
    // Riavvia il bot Telegram
    function restartTelegramBot() {
        fetch('/api/restart-telegram-bot', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            }
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                console.log('Bot Telegram riavviato con successo');
            } else {
                console.error('Errore nel riavvio del bot Telegram:', data.message);
            }
        })
        .catch(error => {
            console.error('Errore nella richiesta di riavvio del bot Telegram:', error);
        });
    }
    
    // Funzioni per la gestione dei punti di mount
    
    // Carica i punti di mount esistenti
    function loadMountPoints() {
        // Per compatibilità, usa uploadMountPointsContainer se mountPointsContainer non esiste
        const container = document.getElementById('mountPoints') || uploadMountPointsContainer;
        if (!container) return;
        
        fetch('/api/mount-points')
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    mountPoints = data.mount_points || [];
                    renderMountPoints(container);
                } else {
                    showMessage('Errore nel caricamento dei punti di mount', 'danger');
                }
            })
            .catch(error => {
                console.error('Error:', error);
                showMessage('Errore di connessione al server', 'danger');
            });
    }
    
    // Renderizza i punti di mount nell'interfaccia
    function renderMountPoints(container) {
        const mountContainer = container || document.getElementById('mountPoints') || uploadMountPointsContainer;
        if (!mountContainer) return;
        
        mountContainer.innerHTML = '';
        
        if (mountPoints.length === 0) {
            mountContainer.innerHTML = '<div class="alert alert-info">Nessun punto di mount configurato. Aggiungine uno sotto.</div>';
            return;
        }
        
        const list = document.createElement('div');
        list.className = 'list-group mb-3';
        
        mountPoints.forEach((mount, index) => {
            const item = document.createElement('div');
            item.className = 'list-group-item d-flex justify-content-between align-items-center';
            
            const pathSpan = document.createElement('span');
            pathSpan.textContent = mount.path;
            
            const deleteBtn = document.createElement('button');
            deleteBtn.className = 'btn btn-sm btn-danger';
            deleteBtn.innerHTML = '<i class="bi bi-trash"></i>';
            deleteBtn.setAttribute('data-index', index);
            deleteBtn.addEventListener('click', function() {
                mountPoints.splice(index, 1);
                renderMountPoints(mountContainer);
            });
            
            item.appendChild(pathSpan);
            item.appendChild(deleteBtn);
            list.appendChild(item);
        });
        
        mountContainer.appendChild(list);
    }
    
    // Aggiunge un nuovo punto di mount
    const addBtn = document.getElementById('addMountPoint') || addUploadMountPointBtn;
    const pathInput = document.getElementById('newMountPath') || newUploadMountPathInput;
    
    if (addBtn && pathInput) {
        addBtn.addEventListener('click', function() {
            const path = pathInput.value.trim();
            
            if (!path) {
                showMessage('Inserisci un percorso valido', 'warning');
                return;
            }
            
            // Controlla se il percorso esiste già
            const exists = mountPoints.some(mount => mount.path === path);
            if (exists) {
                showMessage('Questo percorso è già configurato', 'warning');
                return;
            }
            
            mountPoints.push({ path });
            pathInput.value = '';
            renderMountPoints();
            showMessage('Punto di mount aggiunto', 'success');
        });
    }
    
    // Salva i punti di mount
    const saveBtn = document.getElementById('saveMountPoints') || saveUploadMountPointsBtn;
    if (saveBtn) {
        saveBtn.addEventListener('click', function() {
            fetch('/api/mount-points', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ mount_points: mountPoints })
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    showMessage('Punti di mount salvati con successo', 'success');
                    // Riavvia il bot Telegram per applicare le modifiche
                    restartTelegramBot();
                } else {
                    showMessage(`Errore: ${data.message}`, 'danger');
                }
            })
            .catch(error => {
                console.error('Error:', error);
                showMessage('Errore di connessione al server', 'danger');
            });
        });
    }
    
    // ========== GESTIONE MOUNT POINTS DOWNLOAD ==========
    
    // Variabili per download mount points
    let downloadMountPoints = [];
    
    // Carica i punti di mount download
    function loadDownloadMountPoints() {
        if (!downloadMountPointsContainer) return;
        
        fetch('/api/download-mount-points')
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    downloadMountPoints = data.mount_points || [];
                    renderDownloadMountPoints();
                } else {
                    showMessage('Errore nel caricamento dei punti di mount download', 'danger');
                }
            })
            .catch(error => {
                console.error('Error:', error);
                showMessage('Errore di connessione al server', 'danger');
            });
    }
    
    // Renderizza i punti di mount download
    function renderDownloadMountPoints() {
        if (!downloadMountPointsContainer) return;
        
        downloadMountPointsContainer.innerHTML = '';
        
        if (downloadMountPoints.length === 0) {
            downloadMountPointsContainer.innerHTML = '<div class="alert alert-info">' + getTranslation('mount_points.no_download_mounts') + '</div>';
            return;
        }
        
        const list = document.createElement('div');
        list.className = 'list-group mb-3';
        
        downloadMountPoints.forEach((mount, index) => {
            const item = document.createElement('div');
            item.className = 'list-group-item d-flex justify-content-between align-items-center';
            
            const pathSpan = document.createElement('span');
            pathSpan.textContent = mount.path;
            
            const deleteBtn = document.createElement('button');
            deleteBtn.className = 'btn btn-sm btn-danger';
            deleteBtn.innerHTML = '<i class="bi bi-trash"></i>';
            deleteBtn.setAttribute('data-index', index);
            deleteBtn.addEventListener('click', function() {
                downloadMountPoints.splice(index, 1);
                renderDownloadMountPoints();
            });
            
            item.appendChild(pathSpan);
            item.appendChild(deleteBtn);
            list.appendChild(item);
        });
        
        downloadMountPointsContainer.appendChild(list);
    }
    
    // Gestione pulsante aggiungi download mount point
    if (addDownloadMountPointBtn && newDownloadMountPathInput) {
        addDownloadMountPointBtn.addEventListener('click', function() {
            const path = newDownloadMountPathInput.value.trim();
            
            if (!path) {
                showMessage(getTranslation('mount_points.path_required') || 'Inserisci un percorso valido', 'warning');
                return;
            }
            
            // Controlla se il percorso esiste già
            if (downloadMountPoints.some(mount => mount.path === path)) {
                showMessage(getTranslation('mount_points.path_exists') || 'Questo percorso è già configurato', 'warning');
                return;
            }
            
            downloadMountPoints.push({path: path});
            renderDownloadMountPoints();
            newDownloadMountPathInput.value = '';
            showMessage(getTranslation('mount_points.download_mount_added') || 'Punto di mount download aggiunto', 'success');
        });
    }
    
    // Gestione pulsante salva download mount points
    if (saveDownloadMountPointsBtn) {
        saveDownloadMountPointsBtn.addEventListener('click', function() {
            fetch('/api/download-mount-points', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    mount_points: downloadMountPoints
                })
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    showMessage(getTranslation('mount_points.download_mounts_saved') || 'Punti di mount download salvati con successo', 'success');
                } else {
                    showMessage(data.message || 'Errore nel salvataggio', 'danger');
                }
            })
            .catch(error => {
                console.error('Error:', error);
                showMessage('Errore di connessione al server', 'danger');
            });
        });
    }

    // Inizializzazione - Compatibilità versioni
    if (typeof loadMountPoints === 'function') {
        loadMountPoints();
    }
    
    // Carica i mount points download se la sezione esiste
    if (downloadMountPointsContainer) {
        loadDownloadMountPoints();
    }
    
    // Gestione dei tab
    const tabs = document.querySelectorAll('.nav-link');
    tabs.forEach(tab => {
        tab.addEventListener('click', function(e) {
            e.preventDefault();
            // Rimuovi la classe active da tutti i tab
            tabs.forEach(t => t.classList.remove('active'));
            // Aggiungi la classe active al tab cliccato
            this.classList.add('active');
            
            // Mostra il contenuto del tab
            const target = document.querySelector(this.getAttribute('href'));
            document.querySelectorAll('.tab-pane').forEach(pane => pane.classList.remove('show', 'active'));
            target.classList.add('show', 'active');
            
            // Se è il tab del sistema alert, carica i dati
            if (this.getAttribute('href') === '#alerts') {
                loadMonitoringConfig();
                loadCurrentMetrics();
            }
        });
    });
    
    // ========== SISTEMA DI MONITORAGGIO ==========
    
    // Elementi per il sistema di monitoraggio
    const globalMonitoringToggle = document.getElementById('globalMonitoringToggle');
    const globalMonitoringStatus = document.getElementById('globalMonitoringStatus');
    const monitoringInterval = document.getElementById('monitoringInterval');
    const saveMonitoringConfigBtn = document.getElementById('saveMonitoringConfig');
    const resetMonitoringConfigBtn = document.getElementById('resetMonitoringConfig');
    const refreshMetricsBtn = document.getElementById('refreshMetrics');
    
    // Variabile per memorizzare la configurazione del monitoraggio
    let monitoringConfig = {};
    let availableMountPoints = [];
    
    // Toggle del sistema di monitoraggio globale
    if (globalMonitoringToggle) {
        globalMonitoringToggle.addEventListener('change', function() {
            const isEnabled = this.checked;
            
            // Aggiorna l'interfaccia
            globalMonitoringStatus.textContent = isEnabled ? getTranslation('alerts.global_status.enabled') : getTranslation('alerts.global_status.disabled');
            globalMonitoringStatus.className = isEnabled ? 'text-success' : 'text-danger';
            
            // Invia la richiesta API
            fetch('/api/monitoring-status', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ enabled: isEnabled })
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    const statusText = isEnabled ? getTranslation('alerts.status_messages.enabled') : getTranslation('alerts.status_messages.disabled');
                    showMessage(getTranslation('alerts.status_messages.toggle_success').replace('{status}', statusText), 'success');
                } else {
                    showMessage(`Errore: ${data.message}`, 'danger');
                    // Ripristina lo stato del toggle in caso di errore
                    this.checked = !isEnabled;
                    globalMonitoringStatus.textContent = !isEnabled ? getTranslation('alerts.global_status.enabled') : getTranslation('alerts.global_status.disabled');
                    globalMonitoringStatus.className = !isEnabled ? 'text-success' : 'text-danger';
                }
            })
            .catch(error => {
                console.error('Error:', error);
                showMessage('Errore di connessione al server', 'danger');
                // Ripristina lo stato del toggle in caso di errore
                this.checked = !isEnabled;
                globalMonitoringStatus.textContent = !isEnabled ? getTranslation('alerts.global_status.enabled') : getTranslation('alerts.global_status.disabled');
                globalMonitoringStatus.className = !isEnabled ? 'text-success' : 'text-danger';
            });
        });
    }
    
    // Carica la configurazione del monitoraggio
    function loadMonitoringConfig() {
        fetch('/api/monitoring-config')
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    monitoringConfig = data.config;
                    availableMountPoints = data.available_mount_points || [];
                    populateMonitoringForm();
                    renderDiskConfigurations();
                } else {
                    showMessage('Errore nel caricamento della configurazione monitoraggio', 'danger');
                }
            })
            .catch(error => {
                console.error('Error:', error);
                showMessage('Errore di connessione al server', 'danger');
            });
    }
    
    // Popola il form con i dati della configurazione
    function populateMonitoringForm() {
        // Stato globale
        if (globalMonitoringToggle) {
            globalMonitoringToggle.checked = monitoringConfig.global_enabled || false;
            globalMonitoringStatus.textContent = monitoringConfig.global_enabled ? getTranslation('alerts.global_status.enabled') : getTranslation('alerts.global_status.disabled');
            globalMonitoringStatus.className = monitoringConfig.global_enabled ? 'text-success' : 'text-danger';
        }
        
        if (monitoringInterval) {
            monitoringInterval.value = monitoringConfig.monitoring_interval || 60;
        }
        
        // CPU
        document.getElementById('cpuEnabled').checked = monitoringConfig.cpu_usage?.enabled || false;
        document.getElementById('cpuThreshold').value = monitoringConfig.cpu_usage?.threshold || 80;
        document.getElementById('cpuReminderEnabled').checked = monitoringConfig.cpu_usage?.reminder_enabled || false;
        document.getElementById('cpuReminderInterval').value = monitoringConfig.cpu_usage?.reminder_interval || 300;
        document.getElementById('cpuReminderUnit').value = monitoringConfig.cpu_usage?.reminder_unit || 'seconds';
        
        // RAM
        document.getElementById('ramEnabled').checked = monitoringConfig.ram_usage?.enabled || false;
        document.getElementById('ramThreshold').value = monitoringConfig.ram_usage?.threshold || 85;
        document.getElementById('ramReminderEnabled').checked = monitoringConfig.ram_usage?.reminder_enabled || false;
        document.getElementById('ramReminderInterval').value = monitoringConfig.ram_usage?.reminder_interval || 300;
        document.getElementById('ramReminderUnit').value = monitoringConfig.ram_usage?.reminder_unit || 'seconds';
        
        // Temperatura
        document.getElementById('tempEnabled').checked = monitoringConfig.cpu_temperature?.enabled || false;
        document.getElementById('tempThreshold').value = monitoringConfig.cpu_temperature?.threshold || 70;
        document.getElementById('tempReminderEnabled').checked = monitoringConfig.cpu_temperature?.reminder_enabled || false;
        document.getElementById('tempReminderInterval').value = monitoringConfig.cpu_temperature?.reminder_interval || 600;
        document.getElementById('tempReminderUnit').value = monitoringConfig.cpu_temperature?.reminder_unit || 'seconds';
        
        // Rete
        document.getElementById('networkTestHost').value = monitoringConfig.network_connection?.test_host || '8.8.8.8';
        document.getElementById('networkTestTimeout').value = monitoringConfig.network_connection?.test_timeout || 5;
        document.getElementById('networkReconnectEnabled').checked = monitoringConfig.network_connection?.reconnect_alert || false;
    }
    
    // Renderizza le configurazioni dei dischi
    function renderDiskConfigurations() {
        const container = document.getElementById('diskConfigurations');
        if (!container) return;
        
        container.innerHTML = '';
        
        if (availableMountPoints.length === 0) {
            container.innerHTML = '<div class="alert alert-warning">Nessun punto di mount configurato. Configura i punti di mount nella sezione "Punti di Mount".</div>';
            return;
        }
        
        availableMountPoints.forEach(mountPoint => {
            const diskConfig = monitoringConfig.disk_usage?.[mountPoint] || {
                enabled: false,
                threshold: 85,
                reminder_enabled: false,
                reminder_interval: 300,
                reminder_unit: 'seconds'
            };
            
            const configDiv = document.createElement('div');
            configDiv.className = 'monitoring-config';
            configDiv.innerHTML = `
                <h6><i class="bi bi-hdd"></i> ${mountPoint}</h6>
                <div class="row">
                    <div class="col-md-2">
                        <div class="form-check form-switch">
                            <input class="form-check-input disk-enabled" type="checkbox" data-mount="${mountPoint}" ${diskConfig.enabled ? 'checked' : ''}>
                            <label class="form-check-label">${getTranslation('alerts.enabled')}</label>
                        </div>
                    </div>
                    <div class="col-md-3">
                        <label class="form-label">${getTranslation('alerts.threshold')} (%)</label>
                        <input type="number" class="form-control disk-threshold" data-mount="${mountPoint}" value="${diskConfig.threshold}" min="1" max="100">
                    </div>
                    <div class="col-md-2">
                        <div class="form-check form-switch">
                            <input class="form-check-input disk-reminder-enabled" type="checkbox" data-mount="${mountPoint}" ${diskConfig.reminder_enabled ? 'checked' : ''}>
                            <label class="form-check-label">${getTranslation('alerts.reminder')}</label>
                        </div>
                    </div>
                    <div class="col-md-2">
                        <label class="form-label">${getTranslation('alerts.interval')}</label>
                        <input type="number" class="form-control disk-reminder-interval" data-mount="${mountPoint}" value="${diskConfig.reminder_interval}" min="60">
                    </div>
                    <div class="col-md-2">
                        <label class="form-label">${getTranslation('alerts.unit')}</label>
                        <select class="form-select disk-reminder-unit" data-mount="${mountPoint}">
                            <option value="seconds" ${diskConfig.reminder_unit === 'seconds' ? 'selected' : ''}>${getTranslation('alerts.units.seconds')}</option>
                            <option value="minutes" ${diskConfig.reminder_unit === 'minutes' ? 'selected' : ''}>${getTranslation('alerts.units.minutes')}</option>
                            <option value="hours" ${diskConfig.reminder_unit === 'hours' ? 'selected' : ''}>${getTranslation('alerts.units.hours')}</option>
                            <option value="days" ${diskConfig.reminder_unit === 'days' ? 'selected' : ''}>${getTranslation('alerts.units.days')}</option>
                        </select>
                    </div>
                    <div class="col-md-1">
                        <button type="button" class="btn btn-outline-info btn-sm mt-4" onclick="testAlert('disk_usage')">
                            <i class="bi bi-play"></i> ${getTranslation('alerts.test')}
                        </button>
                    </div>
                </div>
            `;
            container.appendChild(configDiv);
        });
    }
    
    // Salva la configurazione del monitoraggio
    if (saveMonitoringConfigBtn) {
        saveMonitoringConfigBtn.addEventListener('click', function() {
            // Raccogli i dati dal form
            const config = {
                global_enabled: globalMonitoringToggle.checked,
                monitoring_interval: parseInt(monitoringInterval.value),
                cpu_usage: {
                    enabled: document.getElementById('cpuEnabled').checked,
                    threshold: parseFloat(document.getElementById('cpuThreshold').value),
                    reminder_enabled: document.getElementById('cpuReminderEnabled').checked,
                    reminder_interval: parseInt(document.getElementById('cpuReminderInterval').value),
                    reminder_unit: document.getElementById('cpuReminderUnit').value
                },
                ram_usage: {
                    enabled: document.getElementById('ramEnabled').checked,
                    threshold: parseFloat(document.getElementById('ramThreshold').value),
                    reminder_enabled: document.getElementById('ramReminderEnabled').checked,
                    reminder_interval: parseInt(document.getElementById('ramReminderInterval').value),
                    reminder_unit: document.getElementById('ramReminderUnit').value
                },
                cpu_temperature: {
                    enabled: document.getElementById('tempEnabled').checked,
                    threshold: parseFloat(document.getElementById('tempThreshold').value),
                    reminder_enabled: document.getElementById('tempReminderEnabled').checked,
                    reminder_interval: parseInt(document.getElementById('tempReminderInterval').value),
                    reminder_unit: document.getElementById('tempReminderUnit').value
                },
                network_connection: {
                    test_host: document.getElementById('networkTestHost').value,
                    test_timeout: parseInt(document.getElementById('networkTestTimeout').value),
                    reconnect_alert: document.getElementById('networkReconnectEnabled').checked
                },
                disk_usage: {}
            };
            
            // Raccogli le configurazioni dei dischi
            availableMountPoints.forEach(mountPoint => {
                const enabled = document.querySelector(`.disk-enabled[data-mount="${mountPoint}"]`)?.checked || false;
                const threshold = parseFloat(document.querySelector(`.disk-threshold[data-mount="${mountPoint}"]`)?.value || 85);
                const reminderEnabled = document.querySelector(`.disk-reminder-enabled[data-mount="${mountPoint}"]`)?.checked || false;
                const reminderInterval = parseInt(document.querySelector(`.disk-reminder-interval[data-mount="${mountPoint}"]`)?.value || 300);
                const reminderUnit = document.querySelector(`.disk-reminder-unit[data-mount="${mountPoint}"]`)?.value || 'seconds';
                
                config.disk_usage[mountPoint] = {
                    enabled,
                    threshold,
                    reminder_enabled: reminderEnabled,
                    reminder_interval: reminderInterval,
                    reminder_unit: reminderUnit
                };
            });
            
            // Invia la configurazione
            fetch('/api/monitoring-config', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ config })
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    showMessage(getTranslation('alerts.config_saved'), 'success');
                    monitoringConfig = config;
                } else {
                    showMessage(`Errore: ${data.message}`, 'danger');
                }
            })
            .catch(error => {
                console.error('Error:', error);
                showMessage('Errore di connessione al server', 'danger');
            });
        });
    }
    
    // Ripristina configurazione predefinita
    if (resetMonitoringConfigBtn) {
        resetMonitoringConfigBtn.addEventListener('click', function() {
            if (confirm(getTranslation('alerts.config_reset_confirm'))) {
                // Carica configurazione predefinita
                fetch('/api/monitoring-config', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({ config: null }) // null triggera il reset
                })
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        showMessage(getTranslation('alerts.config_reset'), 'success');
                        loadMonitoringConfig(); // Ricarica i dati
                    } else {
                        showMessage(`Errore: ${data.message}`, 'danger');
                    }
                })
                .catch(error => {
                    console.error('Error:', error);
                    showMessage('Errore di connessione al server', 'danger');
                });
            }
        });
    }
    
    // Carica metriche correnti
    function loadCurrentMetrics() {
        fetch('/api/current-metrics')
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    updateMetricsDisplay(data.metrics);
                } else {
                    showMessage('Errore nel caricamento delle metriche', 'danger');
                }
            })
            .catch(error => {
                console.error('Error:', error);
                showMessage('Errore di connessione al server', 'danger');
            });
    }
    
    // Aggiorna la visualizzazione delle metriche
    function updateMetricsDisplay(metrics) {
        // CPU
        const cpuElement = document.getElementById('currentCpu');
        if (cpuElement && metrics.cpu_usage !== null) {
            cpuElement.textContent = `${metrics.cpu_usage.toFixed(1)}%`;
            cpuElement.className = 'metric-value';
            if (metrics.cpu_usage > 80) cpuElement.classList.add('danger');
            else if (metrics.cpu_usage > 60) cpuElement.classList.add('warning');
            else cpuElement.classList.add('success');
        }
        
        // RAM
        const ramElement = document.getElementById('currentRam');
        if (ramElement && metrics.ram_usage !== null) {
            ramElement.textContent = `${metrics.ram_usage.toFixed(1)}%`;
            ramElement.className = 'metric-value';
            if (metrics.ram_usage > 85) ramElement.classList.add('danger');
            else if (metrics.ram_usage > 70) ramElement.classList.add('warning');
            else ramElement.classList.add('success');
        }
        
        // Temperatura
        const tempElement = document.getElementById('currentTemp');
        if (tempElement) {
            if (metrics.cpu_temperature !== null) {
                tempElement.textContent = `${metrics.cpu_temperature.toFixed(1)}°C`;
                tempElement.className = 'metric-value';
                if (metrics.cpu_temperature > 70) tempElement.classList.add('danger');
                else if (metrics.cpu_temperature > 60) tempElement.classList.add('warning');
                else tempElement.classList.add('success');
            } else {
                tempElement.textContent = 'N/A';
                tempElement.className = 'metric-value';
            }
        }
        
        // Disk Usage
        const diskMetricsContainer = document.getElementById('diskMetrics');
        if (diskMetricsContainer && metrics.disk_usage) {
            diskMetricsContainer.innerHTML = '';
            Object.entries(metrics.disk_usage).forEach(([mountPoint, usage]) => {
                if (usage !== null) {
                    const diskDiv = document.createElement('div');
                    diskDiv.className = 'col-md-3';
                    diskDiv.innerHTML = `
                        <div class="metric-card">
                            <div class="metric-title">${mountPoint}</div>
                            <div class="metric-value ${usage > 90 ? 'danger' : usage > 80 ? 'warning' : 'success'}">${usage.toFixed(1)}%</div>
                        </div>
                    `;
                    diskMetricsContainer.appendChild(diskDiv);
                }
            });
        }
    }
    
    // Refresh metriche
    if (refreshMetricsBtn) {
        refreshMetricsBtn.addEventListener('click', function() {
            loadCurrentMetrics();
            showMessage(getTranslation('alerts.metrics_updated'), 'info');
        });
    }
    
    // Funzione globale per testare gli alert
    window.testAlert = function(parameter) {
        fetch('/api/monitoring-test', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({ parameter })
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                showMessage(getTranslation('alerts.test_sent').replace('{parameter}', parameter), 'success');
            } else {
                showMessage(`Errore nell'invio del test: ${data.message}`, 'danger');
            }
        })
        .catch(error => {
            console.error('Error:', error);
            showMessage('Errore di connessione al server', 'danger');
        });
    };
    
    // Test alert rete
    const testNetworkAlertBtn = document.getElementById('testNetworkAlert');
    if (testNetworkAlertBtn) {
        testNetworkAlertBtn.addEventListener('click', function() {
            testAlert('network');
        });
    }
    
    // ========== GESTIONE LINGUA ==========
    
    // Selettore di lingua
    const languageSelector = document.getElementById('languageSelector');
    
    if (languageSelector) {
        languageSelector.addEventListener('change', function() {
            const selectedLanguage = this.value;
            
            // Invia la richiesta per cambiare lingua
            fetch('/api/language', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({ language: selectedLanguage })
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    // Ricarica la pagina per applicare la nuova lingua
                    location.reload();
                } else {
                    showMessage(`Errore nel cambio lingua: ${data.message}`, 'danger');
                    // Ripristina la selezione precedente
                    this.value = this.getAttribute('data-previous') || 'it';
                }
            })
            .catch(error => {
                console.error('Error:', error);
                showMessage('Errore di connessione al server', 'danger');
                // Ripristina la selezione precedente
                this.value = this.getAttribute('data-previous') || 'it';
            });
        });
        
        // Memorizza il valore precedente per eventuale ripristino
        languageSelector.addEventListener('focus', function() {
            this.setAttribute('data-previous', this.value);
        });
    }
    
    // ========== GESTIONE LINGUE ==========
    
    function loadAvailableLanguages() {
        fetch('/api/languages')
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    displayAvailableLanguages(data.languages);
                } else {
                    console.error('Errore nel caricamento delle lingue:', data.error);
                }
            })
            .catch(error => {
                console.error('Errore:', error);
            });
    }
    
    function displayAvailableLanguages(languages) {
        const container = document.getElementById('availableLanguages');
        if (!container) return;
        
        container.innerHTML = '';
        
        languages.forEach(lang => {
            const langElement = document.createElement('div');
            langElement.className = 'card mb-2';
            langElement.innerHTML = `
                <div class="card-body d-flex justify-content-between align-items-center">
                    <div>
                        <h6 class="mb-1">${lang.name} (${lang.code.toUpperCase()})</h6>
                        <small class="text-muted">
                            ${lang.file} - ${(lang.size / 1024).toFixed(1)} KB
                            ${lang.is_default ? `<span class="badge bg-primary ms-2">${getTranslation('languages.default_badge')}</span>` : ''}
                        </small>
                    </div>
                    <div>
                        ${!lang.is_default ? `<button class="btn btn-sm btn-outline-danger" onclick="deleteLanguage('${lang.code}')">
                            <i class="bi bi-trash"></i> ${getTranslation('languages.delete_language')}
                        </button>` : ''}
                    </div>
                </div>
            `;
            container.appendChild(langElement);
        });
    }
    
    function setupLanguageUpload() {
        const form = document.getElementById('languageUploadForm');
        if (!form) return;
        
        form.addEventListener('submit', function(e) {
            e.preventDefault();
            
            const formData = new FormData();
            const languageCode = document.getElementById('languageCode').value.toLowerCase().trim();
            const languageName = document.getElementById('languageName').value.trim();
            const translationFile = document.getElementById('translationFile').files[0];
            
            if (!languageCode || !languageName || !translationFile) {
                showMessage(getTranslation('languages.all_fields_required'), 'warning');
                return;
            }
            
            if (languageCode.length !== 2) {
                showMessage(getTranslation('languages.code_length_error'), 'warning');
                return;
            }
            
            formData.append('languageCode', languageCode);
            formData.append('languageName', languageName);
            formData.append('translationFile', translationFile);
            
            // Mostra loading
            const submitBtn = form.querySelector('button[type="submit"]');
            const originalText = submitBtn.innerHTML;
            submitBtn.innerHTML = `<i class="bi bi-hourglass-split"></i> ${getTranslation('languages.uploading')}`;
            submitBtn.disabled = true;
            
            fetch('/api/languages', {
                method: 'POST',
                body: formData
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    showMessage(data.message, 'success');
                    form.reset();
                    loadAvailableLanguages();
                    
                    // Aggiorna il selettore di lingua nel header
                    setTimeout(() => {
                        location.reload();
                    }, 1500);
                } else {
                    showMessage(data.error || getTranslation('languages.upload_error'), 'danger');
                }
            })
            .catch(error => {
                console.error('Errore:', error);
                showMessage('Errore di connessione', 'danger');
            })
            .finally(() => {
                submitBtn.innerHTML = originalText;
                submitBtn.disabled = false;
            });
        });
    }
    
    // Funzione globale per eliminare lingua (chiamata dal onclick)
    window.deleteLanguage = function(languageCode) {
        const confirmMsg = getTranslation('languages.delete_confirm').replace('{language}', languageCode.toUpperCase());
        if (!confirm(confirmMsg)) {
            return;
        }
        
        fetch(`/api/languages/${languageCode}`, {
            method: 'DELETE'
        })
        .then(response => response.json())
        .then(data => {
            if (data.success) {
                showMessage(data.message, 'success');
                loadAvailableLanguages();
            } else {
                showMessage(data.error || getTranslation('languages.upload_error'), 'danger');
            }
        })
        .catch(error => {
            console.error('Errore:', error);
            showMessage('Errore di connessione', 'danger');
        });
    };
    
    // Carica le lingue disponibili al caricamento della pagina
    if (document.getElementById('availableLanguages')) {
        loadAvailableLanguages();
    }
    
    // Setup upload lingua al caricamento della pagina
    if (document.getElementById('languageUploadForm')) {
        setupLanguageUpload();
    }
    
    // ========== GESTIONE TEMA ========== 
    
    // Inizializza il tema
    initializeTheme();
    
    // Setup del toggle tema
    setupThemeToggle();
    
    function initializeTheme() {
        // Controlla se c'è una preferenza salvata
        const savedTheme = localStorage.getItem('theme');
        const prefersDark = window.matchMedia('(prefers-color-scheme: dark)').matches;
        
        // Usa tema salvato o preferenza sistema
        const currentTheme = savedTheme || (prefersDark ? 'dark' : 'light');
        
        // Applica il tema
        applyTheme(currentTheme);
        
        // Ascolta i cambiamenti nelle preferenze del sistema
        window.matchMedia('(prefers-color-scheme: dark)').addEventListener('change', (e) => {
            if (!localStorage.getItem('theme')) {
                applyTheme(e.matches ? 'dark' : 'light');
            }
        });
    }
    
    function applyTheme(theme) {
        document.documentElement.setAttribute('data-theme', theme);
        updateThemeIcon(theme);
        updateThemeTooltip(theme);
        
        // Salva la preferenza
        localStorage.setItem('theme', theme);
    }
    
    function updateThemeIcon(theme) {
        const themeIcon = document.getElementById('themeIcon');
        if (themeIcon) {
            if (theme === 'dark') {
                themeIcon.className = 'bi bi-sun-fill';
            } else {
                themeIcon.className = 'bi bi-moon-fill';
            }
        }
    }
    
    function updateThemeTooltip(theme) {
        const themeToggle = document.getElementById('themeToggle');
        if (themeToggle) {
            const tooltipText = theme === 'dark' 
                ? getTranslation('theme.switch_to_light') 
                : getTranslation('theme.switch_to_dark');
            themeToggle.setAttribute('title', tooltipText);
        }
    }
    
    function toggleTheme() {
        const currentTheme = document.documentElement.getAttribute('data-theme');
        const newTheme = currentTheme === 'dark' ? 'light' : 'dark';
        applyTheme(newTheme);
        
        // Feedback visivo
        const themeToggle = document.getElementById('themeToggle');
        if (themeToggle) {
            // Piccola animazione di feedback
            themeToggle.style.transform = 'scale(1.2)';
            setTimeout(() => {
                themeToggle.style.transform = 'scale(1)';
            }, 150);
        }
    }
    
    function setupThemeToggle() {
        const themeToggle = document.getElementById('themeToggle');
        if (themeToggle) {
            themeToggle.addEventListener('click', toggleTheme);
            
            // Aggiungi supporto per tastiera
            themeToggle.addEventListener('keydown', (e) => {
                if (e.key === 'Enter' || e.key === ' ') {
                    e.preventDefault();
                    toggleTheme();
                }
            });
        }
    }
    
    // Funzione globale per ottenere il tema corrente
    window.getCurrentTheme = function() {
        return document.documentElement.getAttribute('data-theme') || 'light';
    };
    
    // Funzione globale per impostare il tema
    window.setTheme = function(theme) {
        if (theme === 'light' || theme === 'dark') {
            applyTheme(theme);
        }
    };
});
