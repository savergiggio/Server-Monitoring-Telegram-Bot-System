#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import re
import json
import time
import socket
import logging
import threading
import subprocess
import configparser
import signal
import atexit
import shutil
from pathlib import Path
from datetime import datetime
from flask import Flask, render_template, request, jsonify
import requests

# Importa il modulo telegram_bot
from telegram_bot import (
    init_bot, stop_bot, start_bot_thread, stop_bot_thread,
    load_mount_points, save_mount_points,
    load_monitoring_config, save_monitoring_config, get_default_monitoring_config,
    start_monitoring, stop_monitoring, get_monitoring_status,
    set_bot_language, get_bot_language, send_telegram_message
)



# Importa il modulo AI detection se abilitato
AI_DETECTION_ENABLED = os.environ.get('ENABLE_AI_DETECTION', 'false').lower() == 'true'

if AI_DETECTION_ENABLED:
    try:
        from ai_detection import (
            load_ai_config, save_ai_config, get_default_ai_config,
            load_cameras_config, save_cameras_config, get_default_camera_config,
            start_all_detections, stop_all_detections, restart_all_detections,
            get_detection_status, start_camera_detection, stop_camera_detection
        )
    except ImportError as e:
        logger.error(f"Impossibile importare modulo AI detection: {e}")
        AI_DETECTION_ENABLED = False

# Configurazione percorsi
CONFIG_PATH = Path('/etc/ssh_monitor/config.ini')
LAST_POSITION_FILE = Path('/var/lib/ssh_monitor/last_position.json')
MONITOR_STATUS_FILE = Path('/var/lib/ssh_monitor/monitor_status.json')
LANGUAGE_CONFIG_FILE = Path('/etc/ssh_monitor/language_config.json')

# Configurazione logger
logger = logging.getLogger('app')
logger.setLevel(logging.INFO)
handler = logging.StreamHandler()
handler.setFormatter(logging.Formatter('%(asctime)s - %(name)s - %(levelname)s - %(message)s'))
logger.addHandler(handler)

# Thread globale per il monitoraggio
monitor_thread = None
stop_monitor = threading.Event()

# Crea l'app Flask
app = Flask(__name__)
app.config['SECRET_KEY'] = os.environ.get('SECRET_KEY', 'hard-to-guess-key')
app.config['LOG_TO_STDOUT'] = os.environ.get('LOG_TO_STDOUT', 'false').lower() == 'true'

# Configurazione logging
if app.config['LOG_TO_STDOUT']:
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.StreamHandler()
        ]
    )
else:
    os.makedirs('/var/log/ssh_monitor', exist_ok=True)
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        handlers=[
            logging.FileHandler('/var/log/ssh_monitor/ssh_monitor.log'),
            logging.StreamHandler()
        ]
    )

logger = logging.getLogger("SSH Monitor")

# Assicurarsi che le directory necessarie esistano
os.makedirs('/etc/ssh_monitor', exist_ok=True)
os.makedirs('/var/lib/ssh_monitor', exist_ok=True)

# ========== FUNZIONI PER LE TRADUZIONI ==========

# Cache delle traduzioni
translations_cache = {}

# ========== CARICAMENTO ANTICIPATO DELLE TRADUZIONI ==========
# Carica le traduzioni come prima operazione all'avvio
try:
    # Carica prima l'italiano come base
    app_dir = Path(__file__).parent.resolve()
    it_translation_file = app_dir / 'translations' / 'it.json'
    if it_translation_file.exists():
        with open(it_translation_file, 'r', encoding='utf-8') as f:
            translations_cache['it'] = json.load(f)
        logger.info("🚀 Traduzioni italiane precaricate all'avvio")
    
    # Carica anche l'inglese se disponibile
    en_translation_file = app_dir / 'translations' / 'en.json'
    if en_translation_file.exists():
        with open(en_translation_file, 'r', encoding='utf-8') as f:
            translations_cache['en'] = json.load(f)
        logger.info("🚀 Traduzioni inglesi precaricate all'avvio")
    
    logger.info(f"✅ Traduzioni precaricate per {len(translations_cache)} lingue: {list(translations_cache.keys())}")
except Exception as e:
    logger.error(f"❌ Errore nel precaricamento delle traduzioni: {e}")

def load_translations(language='it'):
    """Carica le traduzioni per la lingua specificata (usa cache precaricata)"""
    global translations_cache
    
    # Se la lingua è già nella cache precaricata, restituiscila
    if language in translations_cache:
        logger.info(f"📋 Traduzioni per {language} recuperate dalla cache precaricata")
        return translations_cache[language]
    
    # Se non è nella cache, prova a caricarla dinamicamente
    try:
        app_dir = Path(__file__).parent.resolve()
        translation_file = app_dir / 'translations' / f'{language}.json'
        
        if translation_file.exists():
            with open(translation_file, 'r', encoding='utf-8') as f:
                translations = json.load(f)
                translations_cache[language] = translations
                logger.info(f"📥 Traduzioni caricate dinamicamente per {language}")
                return translations
        else:
            logger.warning(f"⚠️ File di traduzione non trovato: {translation_file}")
            # Fallback all'italiano se disponibile nella cache
            if language != 'it' and 'it' in translations_cache:
                logger.info(f"🔄 Fallback all'italiano da {language}")
                return translations_cache['it']
            # Fallback all'inglese se disponibile nella cache
            elif 'en' in translations_cache:
                logger.info(f"🔄 Fallback all'inglese da {language}")
                return translations_cache['en']
            # Ultimo fallback con struttura base
            logger.warning("⚠️ Usando fallback con traduzioni vuote")
            fallback_translations = {
                'nav': {'monitoring': 'Monitoring', 'telegram': 'Telegram', 'alerts': 'Alerts', 'mount_points': 'Mount Points', 'info': 'Info'},
                'general': {'language': 'Italiano'},
                'monitoring': {'title': 'Monitoring', 'status': {'active': 'Active', 'inactive': 'Inactive'}},
                'telegram': {'title': 'Telegram Configuration'},
                'alerts': {'title': 'Alert System'},
                'mount_points': {'title': 'Mount Points'},
                'info': {'title': 'Information'}
            }
            translations_cache[language] = fallback_translations
            return fallback_translations
    except Exception as e:
        logger.error(f"❌ Errore nel caricamento delle traduzioni per {language}: {e}")
        # Fallback alla cache esistente o struttura base
        if 'it' in translations_cache:
            return translations_cache['it']
        elif 'en' in translations_cache:
            return translations_cache['en']
        # Ultimo fallback
        fallback_translations = {
            'nav': {'monitoring': 'Monitoring', 'telegram': 'Telegram', 'alerts': 'Alerts', 'mount_points': 'Mount Points', 'info': 'Info'},
            'general': {'language': 'Italiano'},
            'monitoring': {'title': 'Monitoring', 'status': {'active': 'Active', 'inactive': 'Inactive'}},
            'telegram': {'title': 'Telegram Configuration'},
            'alerts': {'title': 'Alert System'},
            'mount_points': {'title': 'Mount Points'},
            'info': {'title': 'Information'}
        }
        return fallback_translations

def get_translation(key, language='it', **kwargs):
    """Ottiene una traduzione specifica"""
    translations = load_translations(language)
    
    # Naviga attraverso i punti nella chiave (es. "nav.monitoring")
    keys = key.split('.')
    value = translations
    
    for k in keys:
        if isinstance(value, dict) and k in value:
            value = value[k]
        else:
            # Se la chiave non esiste, prova con l'italiano come fallback
            if language != 'it':
                return get_translation(key, 'it', **kwargs)
            return key  # Restituisce la chiave se non trova la traduzione
    
    # Se ci sono parametri, formatta la stringa
    if kwargs and isinstance(value, str):
        try:
            return value.format(**kwargs)
        except KeyError:
            return value
    
    return value

def get_current_language():
    """Ottiene la lingua corrente dalle configurazioni"""
    try:
        if LANGUAGE_CONFIG_FILE.exists():
            with open(LANGUAGE_CONFIG_FILE, 'r') as f:
                config = json.load(f)
                return config.get('language', 'it')
    except Exception as e:
        logger.error(f"Errore nel caricamento della configurazione lingua: {e}")
    
    return 'it'  # Default: italiano

def set_current_language(language):
    """Imposta la lingua corrente"""
    try:
        LANGUAGE_CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(LANGUAGE_CONFIG_FILE, 'w') as f:
            json.dump({'language': language}, f)
        return True
    except Exception as e:
        logger.error(f"Errore nel salvataggio della configurazione lingua: {e}")
        return False

def get_available_languages():
    """Restituisce le lingue disponibili"""
    app_dir = Path(__file__).parent.resolve()
    translations_dir = app_dir / 'translations'
    available = []
    
    for file in translations_dir.glob('*.json'):
        language_code = file.stem
        # Carica i nomi delle lingue
        translations = load_translations(language_code)
        language_name = translations.get('general', {}).get('language', language_code.upper())
        available.append({
            'code': language_code,
            'name': language_name
        })
    
    return available

# ========== FUNZIONI DI CONFIGURAZIONE ==========

def get_local_ip():
    """Ottieni l'indirizzo IP locale"""
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        s.connect(("8.8.8.8", 80))
        ip = s.getsockname()[0]
        s.close()
        return ip
    except:
        return "127.0.0.1"

def ensure_config():
    """Assicura che il file di configurazione esista con tutte le sezioni necessarie"""
    # Crea il file solo se non esiste
    if not CONFIG_PATH.exists():
        config = configparser.ConfigParser()
        config['Telegram'] = {
            'bot_token': os.environ.get('TELEGRAM_BOT_TOKEN', ''),
            'chat_id': os.environ.get('TELEGRAM_CHAT_ID', '')
        }
        config['Monitor'] = {
            'check_interval': os.environ.get('CHECK_INTERVAL', '10'),
            'hostname': os.environ.get('HOSTNAME', socket.gethostname()),
            'local_ip': os.environ.get('LOCAL_IP', get_local_ip())
        }
        config['Logs'] = {
            'auth_log': os.environ.get('AUTH_LOG', '/var/log/auth.log'),
            'fail_log': os.environ.get('FAIL_LOG', '/var/log/faillog')
        }
        
        os.makedirs(os.path.dirname(CONFIG_PATH), exist_ok=True)
        with open(CONFIG_PATH, 'w') as f:
            config.write(f)
        
        logger.info(f"Creato nuovo file di configurazione: {CONFIG_PATH}")
        return

def read_config():
    """Legge la configurazione dal file"""
    # Verifica se il file esiste prima di tentare di leggerlo
    if not CONFIG_PATH.exists():
        ensure_config()
    
    config = configparser.ConfigParser()
    if CONFIG_PATH.exists():
        config.read(CONFIG_PATH)
    
    return config

def update_config(section, key, value):
    """Aggiorna un valore nella configurazione preservando il file esistente"""
    # Verifica se il file esiste prima di tentare di leggerlo
    if not CONFIG_PATH.exists():
        ensure_config()
    
    # Leggi la configurazione esistente
    config = configparser.ConfigParser()
    config.read(CONFIG_PATH)
    
    # Aggiorna solo la sezione e la chiave specificate
    if section not in config:
        config[section] = {}
    
    # Verifica se il valore è cambiato
    old_value = config[section].get(key, None)
    if old_value == value:
        logger.debug(f"Valore non modificato per {section}.{key}: {value}")
        return
    
    # Aggiorna il valore
    config[section][key] = value
    
    # Crea una copia di backup del file di configurazione
    if CONFIG_PATH.exists():
        backup_path = str(CONFIG_PATH) + ".bak"
        try:
            shutil.copy2(CONFIG_PATH, backup_path)
            logger.debug(f"Creato backup della configurazione: {backup_path}")
        except Exception as e:
            logger.warning(f"Impossibile creare backup della configurazione: {e}")
    
    # Scrivi la configurazione aggiornata
    try:
        with open(CONFIG_PATH, 'w') as f:
            config.write(f)
        logger.debug(f"Aggiornato {section}.{key} = {value}")
    except Exception as e:
        logger.error(f"Errore nell'aggiornamento della configurazione: {e}")
        # Tenta di ripristinare il backup se disponibile
        if os.path.exists(backup_path):
            try:
                shutil.copy2(backup_path, CONFIG_PATH)
                logger.info(f"Ripristinato backup della configurazione")
            except Exception as restore_error:
                logger.error(f"Impossibile ripristinare il backup: {restore_error}")


def get_monitor_status():
    """Ottiene lo stato del monitoraggio (abilitato/disabilitato)"""
    if MONITOR_STATUS_FILE.exists():
        try:
            with open(MONITOR_STATUS_FILE, 'r') as f:
                data = json.load(f)
                return data.get('enabled', True)
        except:
            pass
    # Default: monitoraggio abilitato
    return True

def set_monitor_status(enabled):
    """Imposta lo stato del monitoraggio"""
    os.makedirs(os.path.dirname(MONITOR_STATUS_FILE), exist_ok=True)
    with open(MONITOR_STATUS_FILE, 'w') as f:
        json.dump({'enabled': enabled}, f)

def mask_value(value):
    """Maschera un valore sensibile per la visualizzazione"""
    if not value:
        return ""
    if len(value) <= 4:
        return "*" * len(value)
    return value[:4] + "*" * (len(value) - 4)

# ========== FUNZIONI TELEGRAM ==========

def send_telegram_message(message, bot_token=None, chat_id=None):
    """
    Invia un messaggio tramite Telegram
    
    Args:
        message (str): Il messaggio da inviare
        bot_token (str, optional): Token del bot Telegram
        chat_id (str, optional): ID della chat
        
    Returns:
        bool: True se l'invio è riuscito, False altrimenti
    """
    try:
        config = read_config()
        
        if not bot_token:
            bot_token = config['Telegram']['bot_token']
        if not chat_id:
            chat_id = config['Telegram']['chat_id']
        
        # Controllo token e chat_id
        if not bot_token or bot_token == 'YOUR_BOT_TOKEN' or not chat_id or chat_id == 'YOUR_CHAT_ID':
            logger.error("Token o Chat ID Telegram non configurati")
            return False, "Token o Chat ID Telegram non configurati"
        
        url = f"https://api.telegram.org/bot{bot_token}/sendMessage"
        data = {
            "chat_id": chat_id,
            "text": message,
            "parse_mode": "Markdown"
        }
        response = requests.post(url, data=data)
        
        if response.status_code != 200:
            error_msg = f"Errore nell'invio del messaggio Telegram: {response.text}"
            logger.error(error_msg)
            return False, error_msg
        
        return True, "Messaggio inviato con successo"
    
    except Exception as e:
        error_msg = f"Errore nell'invio del messaggio Telegram: {str(e)}"
        logger.error(error_msg)
        return False, error_msg

def test_telegram_connection(bot_token=None, chat_id=None):
    """
    Testa la connessione a Telegram inviando un messaggio di prova
    
    Args:
        bot_token (str, optional): Token del bot Telegram
        chat_id (str, optional): ID della chat
        
    Returns:
        tuple: (successo, messaggio)
    """
    current_language = get_current_language()
    test_message = get_translation("test_connection_message", current_language)
    return send_telegram_message(test_message, bot_token, chat_id)

# ========== FUNZIONI MONITORAGGIO SSH ==========

def save_last_position(positions):
    """Salva l'ultima posizione letta nei file di log"""
    with open(LAST_POSITION_FILE, 'w') as f:
        json.dump(positions, f)

def load_last_position():
    """Carica l'ultima posizione letta nei file di log"""
    if LAST_POSITION_FILE.exists():
        try:
            with open(LAST_POSITION_FILE, 'r') as f:
                return json.load(f)
        except:
            logger.error("Errore durante la lettura del file delle posizioni")
    return {}

def read_new_lines(file_path, last_position, skip_existing=False):
    """
    Legge le nuove righe dai file di log
    
    Args:
        file_path (str): Percorso del file di log
        last_position (dict): Dizionario con le posizioni attuali
        skip_existing (bool): Se True, ignora le righe esistenti e segna solo la posizione
        
    Returns:
        tuple: (lines, last_position)
    """
    lines = []
    current_position = last_position.get(file_path, 0)
    
    try:
        with open(file_path, 'r') as f:
            f.seek(0, os.SEEK_END)
            end_position = f.tell()
            
            if current_position > end_position:
                # Il file è stato ruotato o troncato
                current_position = 0
            
            # Se vogliamo saltare le righe esistenti, aggiorniamo solo la posizione
            if skip_existing:
                last_position[file_path] = end_position
                logger.info(f"Posizione iniziale salvata per {file_path}: {end_position}")
                return [], last_position
                
            f.seek(current_position)
            lines = f.readlines()
            last_position[file_path] = end_position
    except Exception as e:
        logger.error(f"Errore durante la lettura del file {file_path}: {str(e)}")
    
    return lines, last_position

def load_excluded_ips():
    """Carica la lista degli IP esclusi dal monitoraggio"""
    try:
        excluded_ips_file = Path('/etc/ssh_monitor/excluded_ips.json')
        if excluded_ips_file.exists():
            with open(excluded_ips_file, 'r') as f:
                data = json.load(f)
                return data.get('excluded_ips', [])
    except Exception as e:
        logger.error(f"Errore nel caricamento IP esclusi: {e}")
    return []

def is_ip_excluded(ip):
    """Controlla se un IP è nella lista degli esclusi (supporta anche CIDR)"""
    import ipaddress
    
    excluded_ips = load_excluded_ips()
    
    try:
        ip_obj = ipaddress.ip_address(ip)
        
        for excluded in excluded_ips:
            excluded = excluded.strip()
            if not excluded:
                continue
                
            try:
                # Controlla se è un singolo IP
                if '/' not in excluded:
                    if ip == excluded:
                        return True
                else:
                    # Controlla se è una rete CIDR
                    network = ipaddress.ip_network(excluded, strict=False)
                    if ip_obj in network:
                        return True
            except (ipaddress.AddressValueError, ipaddress.NetmaskValueError) as e:
                logger.warning(f"IP/rete non valida nella lista esclusi: {excluded} - {e}")
                continue
                
    except ipaddress.AddressValueError as e:
        logger.warning(f"IP non valido da controllare: {ip} - {e}")
        
    return False

def parse_ssh_connection(line):
    """Estrai le informazioni dalla riga di log"""
    # Debug: stampa la riga per verifica
    logger.debug(f"Analisi riga: {line.strip()}")
    
    # Connessione SSH accettata (pattern più generico)
    ssh_pattern = r'Accepted\s+(\w+)\s+for\s+([^\s]+)\s+from\s+(\d+\.\d+\.\d+\.\d+)'
    
    # Pattern alternativo per SSH
    ssh_alt_pattern = r'session opened for user\s+([^\s]+)\s+.*from\s+(\d+\.\d+\.\d+\.\d+)'
    
    # Connessione SFTP
    sftp_pattern = r'subsystem request for sftp.*from\s+(\d+\.\d+\.\d+\.\d+)'
    
    # Utente da riga SFTP (non sempre presente)
    user_pattern = r'for\s+([^\s]+)\s+from'
    
    # Prova il pattern SSH principale
    match = re.search(ssh_pattern, line)
    if match:
        auth_type, username, ip = match.groups()
        
        # Controlla se l'IP è escluso
        if is_ip_excluded(ip):
            logger.debug(f"IP {ip} escluso dal monitoraggio - connessione SSH ignorata")
            return None
            
        logger.info(f"Rilevata connessione SSH (pattern principale): {username}@{ip}")
        return {
            'type': 'SSH',
            'auth_type': auth_type,
            'username': username,
            'ip': ip
        }
    
    # Prova il pattern SSH alternativo
    match = re.search(ssh_alt_pattern, line)
    if match:
        username, ip = match.groups()
        
        # Controlla se l'IP è escluso
        if is_ip_excluded(ip):
            logger.debug(f"IP {ip} escluso dal monitoraggio - connessione SSH ignorata")
            return None
            
        logger.info(f"Rilevata connessione SSH (pattern alternativo): {username}@{ip}")
        return {
            'type': 'SSH',
            'auth_type': 'password',  # Valore predefinito
            'username': username,
            'ip': ip
        }

    # Prova il pattern SFTP
    match = re.search(sftp_pattern, line)
    if match:
        ip = match.group(1)
        
        # Controlla se l'IP è escluso
        if is_ip_excluded(ip):
            logger.debug(f"IP {ip} escluso dal monitoraggio - connessione SFTP ignorata")
            return None
            
        user_match = re.search(user_pattern, line)
        username = user_match.group(1) if user_match else "unknown"
        logger.info(f"Rilevata connessione SFTP: {username}@{ip}")
        return {
            'type': 'SFTP',
            'username': username,
            'ip': ip
        }

    return None

def format_notification(connection, config):
    """Formatta il messaggio di notifica"""
    conn_type = connection['type']
    username = connection['username']
    ip = connection['ip']
    hostname = config['Monitor']['hostname']
    local_ip = get_local_ip()  # IP aggiornato in tempo reale
    
    # Formatta la data
    now = datetime.now()
    date_str = now.strftime("%d %b %Y %H:%M")
    
    message = f"**{conn_type} Connection detected**\n"
    message += f"Connection from **{ip}** as {username} on **{hostname}** (**{local_ip}**)\n"
    message += f"Date: {date_str}\n"
    message += f"More informations: https://ipinfo.io/{ip}"
    
    return message

def parse_fail_log():
    """Analizza i log degli errori (faillog)"""
    try:
        result = subprocess.run(['faillog', '-a'], capture_output=True, text=True)
        if result.returncode == 0:
            lines = result.stdout.strip().split('\n')
            header_skipped = False
            recent_fails = []
            for line in lines:
                if not header_skipped:
                    # Salta l'intestazione
                    header_skipped = True
                    continue
                if len(line.strip()) == 0:
                    continue
                parts = line.split()
                if len(parts) < 4:
                    continue
                username = parts[0]
                failures = parts[1]
                if failures.isdigit() and int(failures) > 0:
                    recent_fails.append(line)
            return recent_fails
        return []
    except Exception as e:
        logger.error(f"Errore durante l'analisi dei faillog: {str(e)}")
        return []

def monitor_ssh_loop():
    """Funzione principale di monitoraggio"""
    logger.info("Avvio monitoraggio connessioni SSH e SFTP...")
    
    config = read_config()
    last_positions = load_last_position()
    check_interval = int(config['Monitor']['check_interval'])
    auth_log_path = config['Logs']['auth_log']
    
    # Inizializza le posizioni per monitorare solo nuove connessioni da adesso
    if os.path.exists(auth_log_path):
        _, last_positions = read_new_lines(auth_log_path, last_positions, skip_existing=True)
        save_last_position(last_positions)
        logger.info("Posizioni iniziali salvate: verranno monitorate solo le nuove connessioni SSH")
    
    # Flag per mostrare il messaggio di disabilitazione solo una volta
    disabled_message_shown = False
    
    while not stop_monitor.is_set():
        try:
            # Verifica se il monitoraggio è abilitato
            if not get_monitor_status():
                if not disabled_message_shown:
                    logger.info("Monitoraggio disabilitato, in attesa...")
                    disabled_message_shown = True
                time.sleep(check_interval)
                continue
            
            # Reset del flag quando il monitoraggio è riabilitato
            if disabled_message_shown:
                logger.info("Monitoraggio riabilitato")
                disabled_message_shown = False
            
            # Leggi nuove righe dal log di autenticazione
            if os.path.exists(auth_log_path):
                new_lines, last_positions = read_new_lines(auth_log_path, last_positions)
                
                for line in new_lines:
                    connection = parse_ssh_connection(line)
                    if connection:
                        message = format_notification(connection, config)
                        logger.info(f"Rilevata connessione {connection['type']} da {connection['ip']} come {connection['username']}")
                        send_telegram_message(message)
            else:
                logger.warning(f"File di log {auth_log_path} non trovato.")
            
            # Analizza i log degli errori (faillog) periodicamente
            fail_logs = parse_fail_log()
            if fail_logs:
                message = "**Failed login attempts detected**\n"
                message += "\n".join(fail_logs[:5])  # Limita a 5 per non creare messaggi troppo lunghi
                if len(fail_logs) > 5:
                    message += f"\n... and {len(fail_logs) - 5} more"
                
                send_telegram_message(message)
            
            # Salva le posizioni correnti
            save_last_position(last_positions)
            
            # Attendi prima del prossimo controllo
            time.sleep(check_interval)
        
        except Exception as e:
            logger.error(f"Errore durante il monitoraggio: {str(e)}")
            time.sleep(check_interval)

def init_monitor():
    """Inizializza il thread di monitoraggio"""
    global monitor_thread, stop_monitor
    
    if monitor_thread and monitor_thread.is_alive():
        logger.info("Monitor già in esecuzione")
        return
    
    logger.info("Inizializzazione monitor SSH")
    stop_monitor.clear()
    monitor_thread = threading.Thread(target=monitor_ssh_loop)
    monitor_thread.daemon = True
    monitor_thread.start()

def stop_monitor_thread():
    """Ferma il thread di monitoraggio"""
    global monitor_thread, stop_monitor
    
    if monitor_thread and monitor_thread.is_alive():
        logger.info("Arresto monitor SSH...")
        stop_monitor.set()
        try:
            monitor_thread.join(timeout=5)
            if monitor_thread.is_alive():
                logger.warning("Il thread di monitoraggio non si è arrestato correttamente")
            else:
                logger.info("Monitor SSH arrestato")
        except Exception as e:
            logger.error(f"Errore durante l'arresto del monitor: {str(e)}")

def restart_monitor():
    """Riavvia il thread di monitoraggio"""
    global monitor_thread, stop_monitor
    
    # Ferma completamente il thread corrente
    stop_monitor_thread()
    
    # Ricrea l'evento e il thread
    stop_monitor = threading.Event()
    monitor_thread = None
    
    # Inizializza un nuovo monitor
    init_monitor()
    
    # Registra che il monitor è stato riavviato
    logger.info("Thread di monitoraggio riavviato con successo")

# ========== ROUTES FLASK ==========

@app.route('/')
def index():
    """Pagina principale dell'applicazione"""
    config = read_config()
    monitor_status = get_monitor_status()
    
    # Maschera i valori sensibili
    bot_token = mask_value(config['Telegram']['bot_token'])
    chat_id = mask_value(config['Telegram']['chat_id'])
    
    # Verifica se è la prima configurazione
    is_configured = (config['Telegram']['bot_token'] and 
                    config['Telegram']['bot_token'] != 'YOUR_BOT_TOKEN' and
                    config['Telegram']['chat_id'] and 
                    config['Telegram']['chat_id'] != 'YOUR_CHAT_ID')
    
    # Ottieni lingua corrente e traduzioni
    current_language = get_current_language()
    translations = load_translations(current_language)
    available_languages = get_available_languages()
    
    return render_template('index.html', 
                          bot_token=bot_token,
                          chat_id=chat_id,
                          monitor_status=monitor_status,
                          is_configured=is_configured,
                          current_language=current_language,
                          translations=translations,
                          available_languages=available_languages,
                          ai_detection_enabled=AI_DETECTION_ENABLED)

@app.route('/api/monitor', methods=['POST'])
def toggle_monitor():
    """API per abilitare/disabilitare il monitoraggio"""
    data = request.get_json()
    enabled = data.get('enabled', True)
    
    # Verifica se lo stato è cambiato
    current_status = get_monitor_status()
    if current_status == enabled:
        return jsonify({
            'success': True,
            'enabled': enabled,
            'message': f"Monitoraggio già {'abilitato' if enabled else 'disabilitato'}"
        })
    
    # Aggiorna lo stato e riavvia il monitor
    set_monitor_status(enabled)
    restart_monitor()
    
    status_text = "abilitato" if enabled else "disabilitato"
    logger.info(f"Monitoraggio {status_text}")
    
    return jsonify({
        'success': True,
        'enabled': enabled,
        'message': f"Monitoraggio {status_text} con successo"
    })

@app.route('/api/telegram', methods=['POST'])
def update_telegram_config():
    """API per aggiornare le credenziali Telegram"""
    data = request.get_json()
    bot_token = data.get('bot_token')
    chat_id = data.get('chat_id')
    
    if bot_token:
        update_config('Telegram', 'bot_token', bot_token)
    
    if chat_id:
        update_config('Telegram', 'chat_id', chat_id)
    
    logger.info("Credenziali Telegram aggiornate")
    
    return jsonify({
        'success': True,
        'message': "Credenziali Telegram aggiornate con successo"
    })

@app.route('/api/test-telegram', methods=['POST'])
def test_telegram():
    """API per testare la connessione Telegram"""
    data = request.get_json()
    bot_token = data.get('bot_token')
    chat_id = data.get('chat_id')
    
    success, message = test_telegram_connection(bot_token, chat_id)
    
    return jsonify({
        'success': success,
        'message': message
    })

@app.route('/api/excluded-ips', methods=['GET'])
def get_excluded_ips():
    """API per ottenere la lista degli IP esclusi dal monitoraggio"""
    try:
        excluded_ips_file = Path('/etc/ssh_monitor/excluded_ips.json')
        if excluded_ips_file.exists():
            with open(excluded_ips_file, 'r') as f:
                data = json.load(f)
                excluded_ips = data.get('excluded_ips', [])
        else:
            excluded_ips = []
        
        return jsonify({
            'success': True,
            'excluded_ips': excluded_ips
        })
    except Exception as e:
        logger.error(f"Errore nel caricamento IP esclusi: {e}")
        return jsonify({
            'success': False,
            'message': 'Errore nel caricamento degli IP esclusi',
            'excluded_ips': []
        })

@app.route('/api/excluded-ips', methods=['POST'])
def save_excluded_ips():
    """API per salvare la lista degli IP esclusi dal monitoraggio"""
    try:
        data = request.get_json()
        excluded_ips = data.get('excluded_ips', [])
        
        # Valida gli IP (supporta anche CIDR)
        import ipaddress
        valid_ips = []
        for ip in excluded_ips:
            ip = ip.strip()
            if not ip:
                continue
                
            try:
                # Controlla se è un singolo IP
                if '/' not in ip:
                    ipaddress.ip_address(ip)
                    valid_ips.append(ip)
                else:
                    # Controlla se è una rete CIDR valida
                    ipaddress.ip_network(ip, strict=False)
                    valid_ips.append(ip)
            except (ipaddress.AddressValueError, ipaddress.NetmaskValueError):
                logger.warning(f"IP/rete non valida ignorata: {ip}")
                continue
        
        # Salva nel file
        excluded_ips_file = Path('/etc/ssh_monitor/excluded_ips.json')
        with open(excluded_ips_file, 'w') as f:
            json.dump({'excluded_ips': valid_ips}, f, indent=2)
        
        current_language = get_current_language()
        success_message = get_translation("monitoring.excluded_ips.save_success", current_language)
        
        logger.info(f"IP esclusi salvati: {valid_ips}")
        
        return jsonify({
            'success': True,
            'message': success_message,
            'excluded_ips': valid_ips
        })
    except Exception as e:
        logger.error(f"Errore nel salvataggio IP esclusi: {e}")
        current_language = get_current_language()
        error_message = get_translation("monitoring.excluded_ips.save_error", current_language)
        
        return jsonify({
            'success': False,
            'message': error_message
        })

# Inizializza il monitor e il bot Telegram all'avvio dell'applicazione
# Flask 2.2+ non supporta più before_first_request
@app.before_request
def initialize_services():
    # Controlla se è la prima richiesta
    if not hasattr(app, '_services_initialized'):
        # Carica le traduzioni come prima cosa
        try:
            current_language = get_current_language()
            load_translations(current_language)
            logger.info(f"✅ Traduzioni caricate per la lingua: {current_language}")
        except Exception as e:
            logger.error(f"❌ Errore nel caricamento delle traduzioni: {e}")
            # Fallback all'italiano
            try:
                load_translations('it')
                logger.info("✅ Traduzioni caricate con fallback all'italiano")
            except Exception as fallback_error:
                logger.error(f"❌ Errore anche nel fallback delle traduzioni: {fallback_error}")
        
        # Avvia il monitor SSH
        init_monitor()
        
        # Avvia il bot Telegram se configurato
        config = read_config()
        bot_token = config['Telegram']['bot_token']
        chat_id = config['Telegram']['chat_id']
        
        if bot_token and bot_token != 'YOUR_BOT_TOKEN' and chat_id and chat_id != 'YOUR_CHAT_ID':
            start_bot_thread(bot_token, chat_id)
            # Sincronizza la lingua del bot con la configurazione web
            try:
                current_language = get_current_language()
                set_bot_language(current_language)
                logger.info(f"Lingua del bot inizializzata a: {current_language}")
            except Exception as e:
                logger.error(f"Errore nell'inizializzazione della lingua del bot: {e}")
        
        # Segna che i servizi sono stati inizializzati
        app._services_initialized = True

# Rotte per la gestione dei mount points
@app.route('/api/mount-points', methods=['GET'])
def get_mount_points():
    """API per ottenere i punti di mount configurati"""
    mount_points = load_mount_points()
    return jsonify({
        'success': True,
        'mount_points': mount_points
    })

@app.route('/api/mount-points', methods=['POST'])
def update_mount_points():
    """API per aggiornare i punti di mount configurati"""
    data = request.get_json()
    mount_points = data.get('mount_points', [])
    
    # Valida i mount points
    valid_mount_points = []
    for mount in mount_points:
        if isinstance(mount, dict) and 'path' in mount:
            # Normalizza il path
            path = mount['path']
            if path:
                valid_mount_points.append({'path': path})
    
    # Salva i mount points
    success = save_mount_points(valid_mount_points)
    
    return jsonify({
        'success': success,
        'mount_points': valid_mount_points,
        'message': "Punti di mount aggiornati con successo" if success else "Errore nell'aggiornamento dei punti di mount"
    })

# Rotte per la gestione dei mount points download
@app.route('/api/download-mount-points', methods=['GET'])
def get_download_mount_points():
    """API per ottenere i punti di mount download"""
    try:
        from telegram_bot import load_download_mount_points
        mount_points = load_download_mount_points()
        return jsonify({
            'success': True,
            'mount_points': mount_points
        })
    except Exception as e:
        logger.error(f"Errore nel recupero dei punti di mount download: {e}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500

@app.route('/api/download-mount-points', methods=['POST'])
def update_download_mount_points():
    """API per aggiornare i punti di mount download"""
    try:
        data = request.get_json()
        mount_points = data.get('mount_points', [])
        
        # Valida i mount points
        valid_mount_points = []
        for mount in mount_points:
            if isinstance(mount, dict) and 'path' in mount:
                # Normalizza il path
                path = mount['path']
                if path:
                    valid_mount_points.append({'path': path})
        
        # Salva i mount points download
        from telegram_bot import save_download_mount_points
        success = save_download_mount_points(valid_mount_points)
        
        return jsonify({
            'success': success,
            'mount_points': valid_mount_points,
            'message': "Punti di mount download aggiornati con successo" if success else "Errore nell'aggiornamento dei punti di mount download"
        })
    except Exception as e:
        logger.error(f"Errore nell'aggiornamento dei punti di mount download: {e}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500

@app.route('/api/telegram-status', methods=['GET'])
def get_telegram_status():
    """API per verificare lo stato del bot Telegram"""
    config = read_config()
    bot_token = config['Telegram']['bot_token']
    chat_id = config['Telegram']['chat_id']
    
    # Verifica se il bot è configurato
    is_configured = (bot_token and bot_token != 'YOUR_BOT_TOKEN' and 
                     chat_id and chat_id != 'YOUR_CHAT_ID')
    
    return jsonify({
        'success': True,
        'is_configured': is_configured,
        'message': "Bot Telegram configurato" if is_configured else "Bot Telegram non configurato"
    })

@app.route('/api/restart-telegram-bot', methods=['POST'])
def restart_telegram_bot():
    """API per riavviare il bot Telegram"""
    # Ferma il bot se è in esecuzione
    stop_bot_thread()
    
    # Avvia il bot con le nuove credenziali
    config = read_config()
    bot_token = config['Telegram']['bot_token']
    chat_id = config['Telegram']['chat_id']
    
    # Verifica se il bot è configurato
    is_configured = (bot_token and bot_token != 'YOUR_BOT_TOKEN' and 
                     chat_id and chat_id != 'YOUR_CHAT_ID')
    
    if is_configured:
        start_bot_thread(bot_token, chat_id)
        # Sincronizza la lingua del bot con la configurazione web
        try:
            current_language = get_current_language()
            set_bot_language(current_language)
            logger.info(f"Lingua del bot riavviato a: {current_language}")
        except Exception as e:
            logger.error(f"Errore nell'aggiornamento della lingua del bot: {e}")
        success = True
        message = "Bot Telegram riavviato con successo"
    else:
        success = False
        message = "Bot Telegram non configurato"
    
    return jsonify({
        'success': success,
        'message': message
    })

# ========== API PER IL SISTEMA DI MONITORAGGIO ==========

@app.route('/api/monitoring-config', methods=['GET'])
def get_monitoring_config():
    """API per ottenere la configurazione del sistema di monitoraggio"""
    try:
        config = load_monitoring_config()
        
        # Aggiungi informazioni sui mount points disponibili
        mount_points = load_mount_points()
        available_mount_points = [mount['path'] for mount in mount_points if 'path' in mount]
        
        # Assicurati che tutti i mount points abbiano una configurazione
        for mount_point in available_mount_points:
            if mount_point not in config['disk_usage']:
                config['disk_usage'][mount_point] = {
                    "enabled": False,
                    "threshold": 85.0,
                    "reminder_enabled": False,
                    "reminder_interval": 300,
                    "reminder_unit": "seconds"
                }
        
        return jsonify({
            'success': True,
            'config': config,
            'available_mount_points': available_mount_points
        })
    except Exception as e:
        logger.error(f"Errore nel recupero della configurazione monitoraggio: {e}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500

@app.route('/api/monitoring-config', methods=['POST'])
def update_monitoring_config():
    """API per aggiornare la configurazione del sistema di monitoraggio"""
    try:
        data = request.get_json()
        config = data.get('config', {})
        
        # Valida la configurazione
        default_config = get_default_monitoring_config()
        
        # Merge con configurazione predefinita per assicurarsi che tutti i campi siano presenti
        for key, value in default_config.items():
            if key not in config:
                config[key] = value
        
        # Salva la configurazione
        success = save_monitoring_config(config)
        
        if success:
            logger.info("Configurazione monitoraggio aggiornata con successo")
            return jsonify({
                'success': True,
                'message': "Configurazione aggiornata con successo"
            })
        else:
            return jsonify({
                'success': False,
                'message': "Errore nel salvataggio della configurazione"
            }), 500
            
    except Exception as e:
        logger.error(f"Errore nell'aggiornamento della configurazione monitoraggio: {e}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500

@app.route('/api/monitoring-status', methods=['GET'])
def get_monitoring_status():
    """API per ottenere lo stato del sistema di monitoraggio"""
    try:
        config = load_monitoring_config()
        global_enabled = config.get('global_enabled', False)
        
        return jsonify({
            'success': True,
            'global_enabled': global_enabled,
            'monitoring_interval': config.get('monitoring_interval', 60)
        })
    except Exception as e:
        logger.error(f"Errore nel recupero dello stato monitoraggio: {e}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500

@app.route('/api/monitoring-status', methods=['POST'])
def toggle_monitoring_status():
    """API per abilitare/disabilitare il sistema di monitoraggio"""
    try:
        data = request.get_json()
        enabled = data.get('enabled', False)
        
        # Carica configurazione corrente
        config = load_monitoring_config()
        config['global_enabled'] = enabled
        
        # Salva la configurazione
        success = save_monitoring_config(config)
        
        if success:
            status_text = "abilitato" if enabled else "disabilitato"
            logger.info(f"Sistema di monitoraggio {status_text}")
            
            return jsonify({
                'success': True,
                'enabled': enabled,
                'message': f"Sistema di monitoraggio {status_text} con successo"
            })
        else:
            return jsonify({
                'success': False,
                'message': "Errore nel salvataggio della configurazione"
            }), 500
            
    except Exception as e:
        logger.error(f"Errore nel toggle del monitoraggio: {e}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500

@app.route('/api/monitoring-test', methods=['POST'])
def test_monitoring():
    """API per testare il sistema di monitoraggio inviando un messaggio di prova"""
    try:
        data = request.get_json()
        parameter = data.get('parameter', 'cpu_usage')
        
        # Ottieni la lingua corrente per utilizzare le traduzioni
        current_language = get_current_language()
        # Ottieni il messaggio di test tradotto
        message_key = f'alerts.test_messages.{parameter}'
        message = get_translation(message_key, current_language)
        
        # Se non trova la traduzione specifica, usa quella generica
        if message == message_key:
            message = get_translation('alerts.test_messages.generic', current_language)
        
        # Invia il messaggio di test
        success, result_message = send_telegram_message(message)
        
        return jsonify({
            'success': success,
            'message': result_message
        })
        
    except Exception as e:
        logger.error(f"Errore nel test del monitoraggio: {e}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500

@app.route('/api/current-metrics', methods=['GET'])
def get_current_metrics():
    """API per ottenere i valori correnti dei parametri monitorati"""
    try:
        import psutil
        
        # CPU Usage
        cpu_usage = psutil.cpu_percent(interval=1)
        
        # RAM Usage
        ram = psutil.virtual_memory()
        ram_usage = ram.percent
        
        # CPU Temperature
        cpu_temp = None
        try:
            temps = psutil.sensors_temperatures()
            if 'coretemp' in temps:
                cpu_temp = temps['coretemp'][0].current
            elif 'cpu_thermal' in temps:
                cpu_temp = temps['cpu_thermal'][0].current
            elif temps:
                for _, sensors in temps.items():
                    if sensors:
                        cpu_temp = sensors[0].current
                        break
        except:
            pass
        
        # Disk Usage per mount points configurati
        mount_points = load_mount_points()
        disk_usage = {}
        for mount in mount_points:
            if 'path' in mount:
                path = mount['path']
                try:
                    if os.path.exists(path):
                        usage = psutil.disk_usage(path)
                        disk_usage[path] = usage.percent
                except:
                    disk_usage[path] = None
        
        return jsonify({
            'success': True,
            'metrics': {
                'cpu_usage': cpu_usage,
                'ram_usage': ram_usage,
                'cpu_temperature': cpu_temp,
                'disk_usage': disk_usage
            }
        })
        
    except Exception as e:
        logger.error(f"Errore nel recupero delle metriche correnti: {e}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500

# Sistema di memorizzazione dati storici persistente
historical_data = {
    'cpu': [],
    'ram': [],
    'temperature': []
}

# File per la persistenza dei dati
# Usa il percorso assoluto per il container Docker
HISTORICAL_DATA_FILE = '/var/lib/ssh_monitor/historical_metrics.json'

def save_historical_data():
    """Salva i dati storici su file JSON"""
    try:
        # Assicura che la directory esista
        os.makedirs(os.path.dirname(HISTORICAL_DATA_FILE), exist_ok=True)
        with open(HISTORICAL_DATA_FILE, 'w') as f:
            json.dump(historical_data, f, indent=2)
        logger.info(f"Dati storici salvati su file: {HISTORICAL_DATA_FILE}")
    except Exception as e:
        logger.error(f"Errore nel salvataggio dei dati storici: {e}")

def load_historical_data():
    """Carica i dati storici dal file JSON"""
    global historical_data
    try:
        if os.path.exists(HISTORICAL_DATA_FILE):
            with open(HISTORICAL_DATA_FILE, 'r') as f:
                loaded_data = json.load(f)
                # Verifica che i dati abbiano la struttura corretta
                if isinstance(loaded_data, dict):
                    for key in ['cpu', 'ram', 'temperature']:
                        if key in loaded_data and isinstance(loaded_data[key], list):
                            historical_data[key] = loaded_data[key]
                logger.info(f"Dati storici caricati: {len(historical_data['cpu'])} CPU, {len(historical_data['ram'])} RAM, {len(historical_data['temperature'])} Temperature")
        else:
            logger.info("File dati storici non trovato, inizializzazione con dati vuoti")
    except Exception as e:
        logger.error(f"Errore nel caricamento dei dati storici: {e}")
        # In caso di errore, mantieni la struttura vuota
        historical_data = {'cpu': [], 'ram': [], 'temperature': []}

def collect_system_metrics():
    """Raccoglie le metriche di sistema correnti"""
    try:
        import psutil
        from datetime import datetime
        
        # CPU Usage
        cpu_usage = psutil.cpu_percent(interval=1)
        
        # RAM Usage
        ram = psutil.virtual_memory()
        ram_usage = ram.percent
        
        # CPU Temperature
        cpu_temp = None
        try:
            temps = psutil.sensors_temperatures()
            if 'coretemp' in temps:
                cpu_temp = temps['coretemp'][0].current
            elif 'cpu_thermal' in temps:
                cpu_temp = temps['cpu_thermal'][0].current
            elif temps:
                for _, sensors in temps.items():
                    if sensors:
                        cpu_temp = sensors[0].current
                        break
        except:
            pass
        
        # Timestamp corrente
        timestamp = datetime.now().isoformat()
        
        # Aggiungi ai dati storici
        historical_data['cpu'].append({'timestamp': timestamp, 'value': cpu_usage})
        historical_data['ram'].append({'timestamp': timestamp, 'value': ram_usage})
        if cpu_temp is not None:
            historical_data['temperature'].append({'timestamp': timestamp, 'value': cpu_temp})
        
        # Mantieni solo gli ultimi 7 giorni di dati (circa 60480 punti per 10 secondi)
        # 7 giorni * 24 ore * 60 minuti * 6 punti per minuto = 60480 punti
        max_points = 60480
        for metric_key in historical_data:
            if len(historical_data[metric_key]) > max_points:
                historical_data[metric_key] = historical_data[metric_key][-max_points:]
        
        # Salva i dati periodicamente (ogni 3 raccolte = 30 secondi)
        if len(historical_data['cpu']) % 3 == 0:
            save_historical_data()
                
    except Exception as e:
        logger.error(f"Errore nella raccolta delle metriche: {e}")

# Avvia la raccolta periodica dei dati
import threading
import time

def periodic_data_collection():
    """Raccoglie dati ogni 10 secondi"""
    while True:
        collect_system_metrics()
        time.sleep(10)  # 10 secondi

# Carica i dati storici all'avvio
load_historical_data()

# Forza un salvataggio iniziale per creare il file se non esiste
save_historical_data()

# Registra il salvataggio dei dati alla chiusura dell'applicazione
def save_data_on_exit():
    """Salva i dati storici prima della chiusura dell'applicazione"""
    logger.info("Salvataggio dati storici prima della chiusura...")
    save_historical_data()

atexit.register(save_data_on_exit)

# Avvia il thread di raccolta dati
data_collection_thread = threading.Thread(target=periodic_data_collection, daemon=True)
data_collection_thread.start()

@app.route('/api/chart-data/<metric>', methods=['GET'])
def get_chart_data(metric):
    """API per ottenere i dati storici reali per i grafici"""
    try:
        time_range = request.args.get('range', '24h')
        from datetime import datetime, timedelta
        
        # Calcola il periodo di tempo richiesto
        now = datetime.now()
        if time_range == '1h':
            start_time = now - timedelta(hours=1)
        elif time_range == '6h':
            start_time = now - timedelta(hours=6)
        elif time_range == '24h':
            start_time = now - timedelta(hours=24)
        elif time_range == '7d':
            start_time = now - timedelta(days=7)
        elif time_range == '30d':
            start_time = now - timedelta(days=30)
        else:
            start_time = now - timedelta(hours=24)
        
        # Se non ci sono dati storici, raccoglie i dati correnti
        if not historical_data.get(metric) or len(historical_data[metric]) == 0:
            collect_system_metrics()
        
        # Filtra i dati in base al range temporale
        filtered_data = []
        if metric in historical_data:
            for data_point in historical_data[metric]:
                try:
                    data_time = datetime.fromisoformat(data_point['timestamp'])
                    if data_time >= start_time:
                        filtered_data.append(data_point)
                except:
                    continue
        
        # Non generiamo dati casuali, mostriamo solo i dati reali quando disponibili
        # Se non ci sono dati storici, restituiamo un array vuoto
        if len(filtered_data) < 1:
            logger.info(f"Dati storici insufficienti per il grafico {metric}, restituisco array vuoto")
            # Non facciamo nulla, filtered_data rimane vuoto
        
        # Prepara la risposta
        timestamps = []
        values = []
        
        for data_point in filtered_data:
            timestamps.append(data_point['timestamp'])
            values.append(data_point['value'])
        
        return jsonify({
            'success': True,
            'timestamps': timestamps,
            'values': values
        })
        
    except Exception as e:
        logger.error(f"Errore nel recupero dei dati del grafico: {e}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500

@app.route('/api/reset-chart-data', methods=['POST'])
def reset_chart_data():
    """Endpoint per cancellare i dati storici dei grafici"""
    try:
        # Resetta i dati storici
        global historical_data
        historical_data = {
            'cpu': [],
            'ram': [],
            'temperature': []
        }
        
        # Salva il file JSON vuoto
        save_historical_data()
        
        logger.info("Dati storici dei grafici cancellati con successo")
        return jsonify({'success': True, 'message': 'Dati storici cancellati con successo'})
    except Exception as e:
        logger.error(f"Errore nella cancellazione dei dati storici: {e}")
        return jsonify({'success': False, 'message': 'Errore nella cancellazione dei dati'}), 500

@app.route('/api/monitoring-debug', methods=['GET'])
def get_monitoring_debug():
    """API per ottenere informazioni di debug del sistema di monitoraggio"""
    try:
        debug_info = get_monitoring_status()
        return jsonify({
            'success': True,
            'debug_info': debug_info
        })
    except Exception as e:
        logger.error(f"Errore nel recupero delle informazioni di debug: {e}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500

# ========== API PER LE TRADUZIONI ==========

@app.route('/api/language', methods=['GET'])
def get_language():
    """API per ottenere la lingua corrente e le lingue disponibili"""
    try:
        current_language = get_current_language()
        available_languages = get_available_languages()
        
        return jsonify({
            'success': True,
            'current_language': current_language,
            'available_languages': available_languages
        })
    except Exception as e:
        logger.error(f"Errore nel recupero delle informazioni lingua: {e}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500

@app.route('/api/language', methods=['POST'])
def set_language():
    """API per impostare la lingua"""
    try:
        data = request.get_json()
        language = data.get('language', 'it')
        
        # Verifica che la lingua sia disponibile
        available_languages = [lang['code'] for lang in get_available_languages()]
        if language not in available_languages:
            return jsonify({
                'success': False,
                'message': f'Language {language} not available'
            }), 400
        
        # Salva la configurazione
        success = set_current_language(language)
        
        if success:
            # Pulisci la cache delle traduzioni per forzare il reload
            global translations_cache
            translations_cache.clear()
            
            # Sincronizza la lingua del bot Telegram
            try:
                set_bot_language(language)
                logger.info(f"Lingua del bot Telegram aggiornata a: {language}")
            except Exception as e:
                logger.error(f"Errore nell'aggiornamento della lingua del bot: {e}")
            
            logger.info(f"Lingua cambiata in: {language}")
            return jsonify({
                'success': True,
                'message': 'Language changed successfully',
                'language': language
            })
        else:
            return jsonify({
                'success': False,
                'message': 'Error saving language configuration'
            }), 500
            
    except Exception as e:
        logger.error(f"Errore nel cambio lingua: {e}")
        return jsonify({
        'success': False,
        'message': str(e)
        }), 500

@app.route('/api/languages', methods=['GET'])
def get_languages_list():
    """Restituisce le lingue disponibili con informazioni dettagliate"""
    try:
        app_dir = Path(__file__).parent.resolve()
        translations_dir = app_dir / 'translations'
        
        languages = []
        if translations_dir.exists():
            for json_file in translations_dir.glob('*.json'):
                lang_code = json_file.stem
                
                # Carica il file per ottenere il nome della lingua
                try:
                    with open(json_file, 'r', encoding='utf-8') as f:
                        translations = json.load(f)
                        lang_name = translations.get('general', {}).get('language', lang_code.upper())
                except:
                    lang_name = lang_code.upper()
                
                languages.append({
                    'code': lang_code,
                    'name': lang_name,
                    'file': json_file.name,
                    'size': json_file.stat().st_size,
                    'is_default': lang_code in ['it', 'en']
                })
        
        return jsonify({
            'success': True,
            'languages': languages
        })
    except Exception as e:
        logger.error(f"Errore nel recupero delle lingue: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@app.route('/api/languages', methods=['POST'])
def upload_language():
    """Carica un nuovo file di traduzione"""
    try:
        # Verifica che tutti i dati necessari siano presenti
        if 'translationFile' not in request.files:
            return jsonify({'success': False, 'error': 'File di traduzione non fornito'}), 400
        
        file = request.files['translationFile']
        language_code = request.form.get('languageCode', '').lower().strip()
        language_name = request.form.get('languageName', '').strip()
        
        if not file or file.filename == '':
            return jsonify({'success': False, 'error': 'Nessun file selezionato'}), 400
        
        if not language_code or len(language_code) != 2:
            return jsonify({'success': False, 'error': 'Codice lingua deve essere di 2 caratteri'}), 400
        
        if not language_name:
            return jsonify({'success': False, 'error': 'Nome lingua richiesto'}), 400
        
        # Verifica che il file sia JSON
        if not file.filename.endswith('.json'):
            return jsonify({'success': False, 'error': 'Il file deve essere in formato JSON'}), 400
        
        # Leggi e valida il contenuto JSON
        try:
            content = file.read().decode('utf-8')
            translations_data = json.loads(content)
        except json.JSONDecodeError as e:
            return jsonify({'success': False, 'error': f'File JSON non valido: {str(e)}'}), 400
        except UnicodeDecodeError:
            return jsonify({'success': False, 'error': 'Errore di codifica del file. Usa UTF-8'}), 400
        
        # Valida la struttura delle traduzioni
        required_keys = ['app_title', 'nav', 'general', 'bot_messages']
        missing_keys = [key for key in required_keys if key not in translations_data]
        
        if missing_keys:
            return jsonify({'success': False, 'error': f'Chiavi mancanti nel file JSON: {missing_keys}'}), 400
        
        # Aggiorna il nome della lingua nel file
        translations_data['general']['language'] = language_name
        
        # Salva il file
        app_dir = Path(__file__).parent.resolve()
        translations_dir = app_dir / 'translations'
        translations_dir.mkdir(exist_ok=True)
        
        file_path = translations_dir / f'{language_code}.json'
        
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(translations_data, f, ensure_ascii=False, indent=2)
        
        # Pulisci la cache delle traduzioni per forzare il ricaricamento
        global translations_cache
        if language_code in translations_cache:
            del translations_cache[language_code]
        
        logger.info(f"Nuova lingua caricata: {language_code} ({language_name})")
        
        return jsonify({
            'success': True,
            'message': f'Lingua {language_name} ({language_code}) caricata con successo',
            'language': {
                'code': language_code,
                'name': language_name
            }
        })
        
    except Exception as e:
        logger.error(f"Errore nel caricamento della lingua: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/api/download-template')
def download_template():
    """Scarica un template JSON per creare nuove traduzioni"""
    try:
        # Usa il file italiano come template
        app_dir = Path(__file__).parent.resolve()
        template_file = app_dir / 'translations' / 'it.json'
        
        if not template_file.exists():
            return jsonify({'error': 'Template non disponibile'}), 404
        
        from flask import send_file
        return send_file(
            template_file, 
            as_attachment=True,
            download_name='translation_template.json',
            mimetype='application/json'
        )
    except Exception as e:
        logger.error(f"Errore nel download del template: {str(e)}")
        return jsonify({'error': str(e)}), 500

@app.route('/api/languages/<language_code>', methods=['DELETE'])
def delete_language(language_code):
    """Elimina una lingua (tranne it e en)"""
    try:
        # Non permettere di eliminare le lingue di base
        if language_code in ['it', 'en']:
            return jsonify({'success': False, 'error': 'Non è possibile eliminare le lingue di base'}), 400
        
        app_dir = Path(__file__).parent.resolve()
        file_path = app_dir / 'translations' / f'{language_code}.json'
        
        if not file_path.exists():
            return jsonify({'success': False, 'error': 'Lingua non trovata'}), 404
        
        file_path.unlink()
        
        # Pulisci la cache
        global translations_cache
        if language_code in translations_cache:
            del translations_cache[language_code]
        
        logger.info(f"Lingua eliminata: {language_code}")
        
        return jsonify({
            'success': True,
            'message': f'Lingua {language_code} eliminata con successo'
        })
        
    except Exception as e:
        logger.error(f"Errore nell'eliminazione della lingua: {str(e)}")
        return jsonify({'success': False, 'error': str(e)}), 500

# ========== API PER AI DETECTION ==========

@app.route('/api/ai-config', methods=['GET'])
def get_ai_config():
    """API per ottenere la configurazione AI"""
    if not AI_DETECTION_ENABLED:
        return jsonify({
            'success': False,
            'message': "AI Detection non abilitata"
        }), 400
    
    try:
        config = load_ai_config()
        return jsonify({
            'success': True,
            'config': config
        })
    except Exception as e:
        logger.error(f"Errore nel recupero configurazione AI: {e}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500

@app.route('/api/ai-config', methods=['POST'])
def update_ai_config():
    """API per aggiornare la configurazione AI"""
    if not AI_DETECTION_ENABLED:
        return jsonify({
            'success': False,
            'message': "AI Detection non abilitata"
        }), 400
    
    try:
        data = request.get_json()
        config = data.get('config', {})
        
        # Merge con configurazione default
        default_config = get_default_ai_config()
        for key, value in default_config.items():
            if key not in config:
                config[key] = value
        
        success = save_ai_config(config)
        
        if success:
            # Riavvia detection se abilitata
            if config.get('global_enabled', False):
                restart_all_detections()
            else:
                stop_all_detections()
            
            return jsonify({
                'success': True,
                'message': "Configurazione AI aggiornata con successo"
            })
        else:
            return jsonify({
                'success': False,
                'message': "Errore nel salvataggio della configurazione"
            }), 500
            
    except Exception as e:
        logger.error(f"Errore nell'aggiornamento configurazione AI: {e}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500

@app.route('/api/cameras', methods=['GET'])
def get_cameras():
    """API per ottenere la configurazione delle telecamere"""
    if not AI_DETECTION_ENABLED:
        return jsonify({
            'success': False,
            'message': "AI Detection non abilitata"
        }), 400
    
    try:
        cameras = load_cameras_config()
        return jsonify({
            'success': True,
            'cameras': cameras
        })
    except Exception as e:
        logger.error(f"Errore nel recupero configurazione telecamere: {e}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500

@app.route('/api/cameras', methods=['POST'])
def update_cameras():
    """API per aggiornare la configurazione delle telecamere"""
    if not AI_DETECTION_ENABLED:
        return jsonify({
            'success': False,
            'message': "AI Detection non abilitata"
        }), 400
    
    try:
        data = request.get_json()
        cameras = data.get('cameras', {})
        
        # Valida e pulisce configurazione telecamere
        cleaned_cameras = {}
        for camera_id, camera_config in cameras.items():
            if isinstance(camera_config, dict):
                # Merge con configurazione default
                default_config = get_default_camera_config()
                for key, value in default_config.items():
                    if key not in camera_config:
                        camera_config[key] = value
                cleaned_cameras[camera_id] = camera_config
        
        success = save_cameras_config(cleaned_cameras)
        
        if success:
            # Riavvia detection
            restart_all_detections()
            
            return jsonify({
                'success': True,
                'cameras': cleaned_cameras,
                'message': "Configurazione telecamere aggiornata con successo"
            })
        else:
            return jsonify({
                'success': False,
                'message': "Errore nel salvataggio della configurazione"
            }), 500
            
    except Exception as e:
        logger.error(f"Errore nell'aggiornamento configurazione telecamere: {e}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500

@app.route('/api/cameras/<camera_id>', methods=['DELETE'])
def delete_camera(camera_id):
    """API per eliminare una telecamera"""
    if not AI_DETECTION_ENABLED:
        return jsonify({
            'success': False,
            'message': "AI Detection non abilitata"
        }), 400
    
    try:
        # Ferma detection per questa camera
        stop_camera_detection(camera_id)
        
        # Carica configurazione
        cameras = load_cameras_config()
        
        if camera_id in cameras:
            del cameras[camera_id]
            success = save_cameras_config(cameras)
            
            if success:
                return jsonify({
                    'success': True,
                    'message': f"Telecamera {camera_id} eliminata con successo"
                })
            else:
                return jsonify({
                    'success': False,
                    'message': "Errore nel salvataggio della configurazione"
                }), 500
        else:
            return jsonify({
                'success': False,
                'message': f"Telecamera {camera_id} non trovata"
            }), 404
            
    except Exception as e:
        logger.error(f"Errore nell'eliminazione telecamera {camera_id}: {e}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500

@app.route('/api/detection-status', methods=['GET'])
def get_ai_detection_status():
    """API per ottenere lo stato delle detection"""
    if not AI_DETECTION_ENABLED:
        return jsonify({
            'success': False,
            'message': "AI Detection non abilitata"
        }), 400
    
    try:
        status = get_detection_status()
        return jsonify({
            'success': True,
            'status': status
        })
    except Exception as e:
        logger.error(f"Errore nel recupero stato detection: {e}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500

@app.route('/api/detection-control', methods=['POST'])
def control_detection():
    """API per controllare le detection (start/stop/restart)"""
    if not AI_DETECTION_ENABLED:
        return jsonify({
            'success': False,
            'message': "AI Detection non abilitata"
        }), 400
    
    try:
        data = request.get_json()
        action = data.get('action', '')
        
        if action == 'start':
            success = start_all_detections()
            message = "Detection avviate con successo" if success else "Nessuna detection avviata"
        elif action == 'stop':
            stop_all_detections()
            success = True
            message = "Detection fermate con successo"
        elif action == 'restart':
            success = restart_all_detections()
            message = "Detection riavviate con successo" if success else "Errore nel riavvio detection"
        else:
            return jsonify({
                'success': False,
                'message': f"Azione non riconosciuta: {action}"
            }), 400
        
        return jsonify({
            'success': success,
            'message': message
        })
        
    except Exception as e:
        logger.error(f"Errore nel controllo detection: {e}")
        return jsonify({
            'success': False,
            'message': str(e)
        }), 500

# ========== API ROUTES PER GESTIONE COMANDI ==========

@app.route('/api/commands', methods=['GET'])
def get_commands():
    """Restituisce la lista dei comandi configurati"""
    try:
        commands = load_commands_config()
        return jsonify({
            'success': True,
            'commands': commands
        })
    except Exception as e:
        logger.error(f"Errore nel caricamento comandi: {e}")
        return jsonify({
            'success': False,
            'message': f'Errore nel caricamento comandi: {str(e)}'
        }), 500

@app.route('/api/commands', methods=['POST'])
def save_command():
    """Salva un nuovo comando"""
    try:
        data = request.get_json()
        
        # Validazione dati
        required_fields = ['name', 'description', 'script_path']
        for field in required_fields:
            if not data.get(field):
                return jsonify({
                    'success': False,
                    'message': f'Campo {field} richiesto'
                }), 400
        
        # Validazione percorso script
        script_path = data['script_path'].strip()
        if not validate_script_path(script_path):
            return jsonify({
                'success': False,
                'message': 'Percorso script non valido o non sicuro'
            }), 400
        
        # Validazione formato cron se abilitato
        if data.get('cron_enabled', False) and data.get('cron_schedule'):
            if not validate_cron_format(data['cron_schedule']):
                return jsonify({
                    'success': False,
                    'message': 'Formato espressione cron non valido'
                }), 400
        
        # Carica comandi esistenti
        commands = load_commands_config()
        
        # Genera ID univoco
        command_id = str(int(time.time()))
        
        # Aggiungi nuovo comando
        commands[command_id] = {
            'name': data['name'].strip(),
            'description': data['description'].strip(),
            'script_path': script_path,
            'enabled': data.get('enabled', True),
            'cron_enabled': data.get('cron_enabled', False),
            'cron_schedule': data.get('cron_schedule', '').strip(),
            'created_at': datetime.now().isoformat()
        }
        
        # Salva configurazione
        save_commands_config(commands)
        
        # Aggiorna i job cron
        update_cron_after_command_change()
        
        return jsonify({
            'success': True,
            'message': 'Comando salvato con successo'
        })
        
    except Exception as e:
        logger.error(f"Errore nel salvataggio comando: {e}")
        return jsonify({
            'success': False,
            'message': f'Errore nel salvataggio comando: {str(e)}'
        }), 500

@app.route('/api/commands/<command_id>', methods=['GET'])
def get_command(command_id):
    """Ottiene i dettagli di un comando specifico"""
    try:
        commands = load_commands_config()
        
        if command_id not in commands:
            return jsonify({
                'success': False,
                'message': 'Comando non trovato'
            }), 404
        
        return jsonify({
            'success': True,
            'command': commands[command_id]
        })
        
    except Exception as e:
        logger.error(f"Errore nel recupero comando: {e}")
        return jsonify({
            'success': False,
            'message': f'Errore nel recupero comando: {str(e)}'
        }), 500

@app.route('/api/commands/<command_id>', methods=['PUT'])
def update_command(command_id):
    """Aggiorna un comando esistente"""
    try:
        data = request.get_json()
        commands = load_commands_config()
        
        if command_id not in commands:
            return jsonify({
                'success': False,
                'message': 'Comando non trovato'
            }), 404
        
        # Validazione dati
        required_fields = ['name', 'description', 'script_path']
        for field in required_fields:
            if field not in data or not data[field].strip():
                return jsonify({
                    'success': False,
                    'message': f'Campo {field} richiesto'
                }), 400
        
        # Validazione percorso script
        script_path = data['script_path'].strip()
        if not validate_script_path(script_path):
            return jsonify({
                'success': False,
                'message': 'Percorso script non valido o non sicuro'
            }), 400
        
        # Validazione formato cron se abilitato
        if data.get('cron_enabled', False) and data.get('cron_schedule'):
            if not validate_cron_format(data['cron_schedule']):
                return jsonify({
                    'success': False,
                    'message': 'Formato espressione cron non valido'
                }), 400
        
        # Aggiorna comando
        commands[command_id] = {
            'name': data['name'].strip(),
            'description': data['description'].strip(),
            'script_path': script_path,
            'enabled': data.get('enabled', False),
            'cron_enabled': data.get('cron_enabled', False),
            'cron_schedule': data.get('cron_schedule', '').strip()
        }
        
        # Mantieni il timestamp di creazione se esiste
        if 'created_at' in commands[command_id]:
            commands[command_id]['created_at'] = commands[command_id]['created_at']
        
        # Salva configurazione
        save_commands_config(commands)
        
        # Aggiorna i job cron
        update_cron_after_command_change()
        
        return jsonify({
            'success': True,
            'message': 'Comando aggiornato con successo'
        })
        
    except Exception as e:
        logger.error(f"Errore nell'aggiornamento comando: {e}")
        return jsonify({
            'success': False,
            'message': f'Errore nell\'aggiornamento comando: {str(e)}'
        }), 500

@app.route('/api/commands/<command_id>', methods=['DELETE'])
def delete_command(command_id):
    """Elimina un comando"""
    try:
        commands = load_commands_config()
        
        if command_id not in commands:
            return jsonify({
                'success': False,
                'message': 'Comando non trovato'
            }), 404
        
        # Rimuovi comando
        del commands[command_id]
        
        # Salva configurazione
        save_commands_config(commands)
        
        # Aggiorna i job cron
        update_cron_after_command_change()
        
        return jsonify({
            'success': True,
            'message': 'Comando eliminato con successo'
        })
        
    except Exception as e:
        logger.error(f"Errore nell'eliminazione comando: {e}")
        return jsonify({
            'success': False,
            'message': f'Errore nell\'eliminazione comando: {str(e)}'
        }), 500

@app.route('/api/commands/<command_id>/execute', methods=['POST'])
def execute_command(command_id):
    """Esegue un comando"""
    try:
        commands = load_commands_config()
        
        if command_id not in commands:
            return jsonify({
                'success': False,
                'message': 'Comando non trovato'
            }), 404
        
        command = commands[command_id]
        
        if not command.get('enabled', False):
            return jsonify({
                'success': False,
                'message': 'Comando disabilitato'
            }), 400
        
        # Esegui comando
        result = execute_script(command['script_path'])
        
        if result['success']:
            # Invia notifica Telegram
            timestamp = datetime.now().strftime('%d/%m/%Y %H:%M:%S')
            output = result['output'] if len(result['output']) <= 1000 else result['output'][:997] + "..."
            message = f"✅ *Comando eseguito con successo*\n\n📝 *Nome:* {command['name']}\n📄 *Descrizione:* {command['description']}\n🕐 *Timestamp:* {timestamp}\n\n📤 *Output:*\n```\n{output}\n```"
            
            # Invia la notifica in background per non bloccare la risposta API
            threading.Thread(target=send_telegram_message, args=(message,)).start()
            
            return jsonify({
                'success': True,
                'message': 'Comando eseguito con successo',
                'output': result['output']
            })
        else:
            return jsonify({
                'success': False,
                'message': f'Errore nell\'esecuzione: {result["error"]}'
            }), 500
        
    except Exception as e:
        logger.error(f"Errore nell'esecuzione comando: {e}")
        return jsonify({
            'success': False,
            'message': f'Errore nell\'esecuzione comando: {str(e)}'
        }), 500

@app.route('/api/commands/test', methods=['POST'])
def test_command():
    """Testa un comando senza salvarlo"""
    try:
        data = request.get_json()
        
        script_path = data.get('script_path')
        if not script_path:
            return jsonify({
                'success': False,
                'message': 'Percorso script richiesto'
            }), 400
        
        if not os.path.exists(script_path):
            return jsonify({
                'success': False,
                'message': 'Script non trovato nel percorso specificato'
            }), 400
        
        # Testa esecuzione
        result = execute_script(script_path)
        
        if result['success']:
            return jsonify({
                'success': True,
                'message': 'Test comando completato con successo',
                'output': result['output']
            })
        else:
            return jsonify({
                'success': False,
                'message': f'Errore nel test: {result["error"]}'
            }), 500
        
    except Exception as e:
        logger.error(f"Errore nel test comando: {e}")
        return jsonify({
            'success': False,
            'message': f'Errore nel test comando: {str(e)}'
        }), 500

# ========== FUNZIONI DI SUPPORTO PER COMANDI ==========

def load_commands_config():
    """Carica la configurazione dei comandi"""
    commands_file = Path('/etc/ssh_monitor/commands_config.json')
    
    if commands_file.exists():
        try:
            with open(commands_file, 'r', encoding='utf-8') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Errore nel caricamento configurazione comandi: {e}")
    
    return {}

def save_commands_config(commands):
    """Salva la configurazione dei comandi"""
    commands_file = Path('/etc/ssh_monitor/commands_config.json')
    
    try:
        with open(commands_file, 'w', encoding='utf-8') as f:
            json.dump(commands, f, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.error(f"Errore nel salvataggio configurazione comandi: {e}")
        raise

def validate_script_path(script_path):
    """Valida il percorso di uno script per sicurezza"""
    if not script_path:
        return False
    
    # Controlla che il percorso sia assoluto
    if not os.path.isabs(script_path):
        return False
    
    # Controlla che il file esista
    if not os.path.exists(script_path):
        return False
    
    # Controlla che sia un file (non una directory)
    if not os.path.isfile(script_path):
        return False
    
    # Controlla che non contenga sequenze pericolose
    dangerous_patterns = ['../', '~/', '$(']
    for pattern in dangerous_patterns:
        if pattern in script_path:
            return False
    
    # Controlla che sia in una directory sicura (opzionale)
    # Puoi personalizzare questa lista in base alle tue esigenze
    allowed_dirs = ['/home/', '/opt/', '/usr/local/bin/', '/usr/bin/']
    if not any(script_path.startswith(allowed_dir) for allowed_dir in allowed_dirs):
        return False
    
    return True

def validate_cron_format(cron_expression):
    """Valida il formato di un'espressione cron"""
    if not cron_expression or not cron_expression.strip():
        return False
    
    parts = cron_expression.strip().split()
    if len(parts) != 5:
        return False
    
    # Definisci i range validi per ogni campo
    ranges = [
        (0, 59),  # minuti
        (0, 23),  # ore
        (1, 31),  # giorni del mese
        (1, 12),  # mesi
        (0, 6)    # giorni della settimana
    ]
    
    for i, part in enumerate(parts):
        if part == '*':
            continue
        
        # Gestisci range (es: 1-5)
        if '-' in part:
            try:
                start, end = map(int, part.split('-'))
                if start < ranges[i][0] or end > ranges[i][1] or start > end:
                    return False
            except ValueError:
                return False
        # Gestisci liste (es: 1,3,5)
        elif ',' in part:
            try:
                values = [int(x) for x in part.split(',')]
                for val in values:
                    if val < ranges[i][0] or val > ranges[i][1]:
                        return False
            except ValueError:
                return False
        # Gestisci step (es: */5)
        elif '/' in part:
            try:
                base, step = part.split('/')
                if base != '*':
                    base_val = int(base)
                    if base_val < ranges[i][0] or base_val > ranges[i][1]:
                        return False
                step_val = int(step)
                if step_val <= 0:
                    return False
            except ValueError:
                return False
        # Gestisci valori singoli
        else:
            try:
                val = int(part)
                if val < ranges[i][0] or val > ranges[i][1]:
                    return False
            except ValueError:
                return False
    
    return True

def execute_script(script_path):
    """Esegue uno script e restituisce il risultato"""
    try:
        # Verifica che il file sia eseguibile
        if not os.access(script_path, os.X_OK):
            return {
                'success': False,
                'error': 'Script non eseguibile'
            }
        
        # Esegui script con timeout
        result = subprocess.run(
            [script_path],
            capture_output=True,
            text=True,
            timeout=300,  # 5 minuti di timeout
            cwd=os.path.dirname(script_path)
        )
        
        if result.returncode == 0:
            return {
                'success': True,
                'output': result.stdout
            }
        else:
            return {
                'success': False,
                'error': result.stderr or f'Exit code: {result.returncode}'
            }
    
    except subprocess.TimeoutExpired:
        return {
            'success': False,
            'error': 'Timeout esecuzione script (5 minuti)'
        }
    except Exception as e:
        return {
            'success': False,
            'error': str(e)
        }

# ========== SISTEMA DI SCHEDULING CRON ==========

# Variabili globali per il sistema di scheduling
cron_scheduler_thread = None
cron_stop_event = threading.Event()
cron_jobs = {}

def parse_cron_expression(cron_expr):
    """Converte un'espressione cron in valori utilizzabili"""
    parts = cron_expr.strip().split()
    if len(parts) != 5:
        return None
    
    def parse_field(field, min_val, max_val):
        if field == '*':
            return list(range(min_val, max_val + 1))
        elif '-' in field:
            start, end = map(int, field.split('-'))
            return list(range(start, end + 1))
        elif ',' in field:
            return [int(x) for x in field.split(',')]
        elif '/' in field:
            base, step = field.split('/')
            if base == '*':
                return list(range(min_val, max_val + 1, int(step)))
            else:
                start = int(base)
                return list(range(start, max_val + 1, int(step)))
        else:
            return [int(field)]
    
    try:
        return {
            'minutes': parse_field(parts[0], 0, 59),
            'hours': parse_field(parts[1], 0, 23),
            'days': parse_field(parts[2], 1, 31),
            'months': parse_field(parts[3], 1, 12),
            'weekdays': parse_field(parts[4], 0, 6)
        }
    except (ValueError, IndexError):
        return None

def should_run_now(cron_schedule, current_time):
    """Verifica se un comando dovrebbe essere eseguito ora"""
    parsed = parse_cron_expression(cron_schedule)
    if not parsed:
        return False
    
    return (current_time.minute in parsed['minutes'] and
            current_time.hour in parsed['hours'] and
            current_time.day in parsed['days'] and
            current_time.month in parsed['months'] and
            current_time.weekday() in parsed['weekdays'])

def execute_scheduled_command(command_id, command):
    """Esegue un comando schedulato"""
    try:
        logger.info(f"Esecuzione comando schedulato: {command['name']} (ID: {command_id})")
        
        # Esegui il comando
        result = execute_script(command['script_path'])
        
        # Prepara il messaggio di notifica
        timestamp = datetime.now().strftime('%d/%m/%Y %H:%M:%S')
        
        # Ottieni le traduzioni dal bot Telegram
        from telegram_bot import get_bot_translation
        
        if result['success']:
            output = result['output'] if len(result['output']) <= 1000 else result['output'][:997] + "..."
            
            # Verifica se c'è output o meno
            if output.strip():
                message = get_bot_translation("bot_messages.commands.scheduled_success").format(
                    command_name=command['name'],
                    description=command['description'],
                    timestamp=timestamp,
                    output=output
                )
            else:
                message = get_bot_translation("bot_messages.commands.scheduled_success_no_output").format(
                    command_name=command['name'],
                    description=command['description'],
                    timestamp=timestamp
                )
        else:
            message = get_bot_translation("bot_messages.commands.scheduled_error").format(
                command_name=command['name'],
                error=result['error'],
                timestamp=timestamp
            )
        
        # Invia notifica Telegram in background
        threading.Thread(target=send_telegram_message, args=(message,)).start()
        
        logger.info(f"Comando schedulato completato: {command['name']}")
        
    except Exception as e:
        logger.error(f"Errore nell'esecuzione del comando schedulato {command_id}: {e}")
        
        # Invia notifica di errore
        timestamp = datetime.now().strftime('%d/%m/%Y %H:%M:%S')
        
        # Ottieni le traduzioni dal bot Telegram
        from telegram_bot import get_bot_translation
        
        error_message = get_bot_translation("bot_messages.commands.scheduling_system_error").format(
            command_name=command.get('name', 'Sconosciuto'),
            error=str(e),
            timestamp=timestamp
        )
        
        threading.Thread(target=send_telegram_message, args=(error_message,)).start()

def cron_scheduler_loop():
    """Loop principale del sistema di scheduling cron"""
    logger.info("Sistema di scheduling cron avviato")
    
    last_minute = None
    
    while not cron_stop_event.is_set():
        try:
            current_time = datetime.now()
            current_minute = current_time.replace(second=0, microsecond=0)
            
            # Esegui controlli solo una volta per minuto
            if current_minute != last_minute:
                last_minute = current_minute
                
                # Carica i comandi configurati
                commands = load_commands_config()
                
                # Controlla ogni comando per vedere se deve essere eseguito
                for command_id, command in commands.items():
                    if (command.get('enabled', False) and 
                        command.get('cron_enabled', False) and 
                        command.get('cron_schedule')):
                        
                        if should_run_now(command['cron_schedule'], current_time):
                            # Esegui il comando in un thread separato
                            threading.Thread(
                                target=execute_scheduled_command,
                                args=(command_id, command),
                                daemon=True
                            ).start()
            
            # Attendi 30 secondi prima del prossimo controllo
            cron_stop_event.wait(30)
            
        except Exception as e:
            logger.error(f"Errore nel loop del scheduler cron: {e}")
            cron_stop_event.wait(60)  # Attendi un minuto in caso di errore
    
    logger.info("Sistema di scheduling cron fermato")

def start_cron_scheduler():
    """Avvia il sistema di scheduling cron"""
    global cron_scheduler_thread, cron_stop_event
    
    if cron_scheduler_thread and cron_scheduler_thread.is_alive():
        logger.info("Sistema di scheduling cron già attivo")
        return
    
    cron_stop_event.clear()
    cron_scheduler_thread = threading.Thread(target=cron_scheduler_loop, daemon=True)
    cron_scheduler_thread.start()
    logger.info("Sistema di scheduling cron avviato")

def stop_cron_scheduler():
    """Ferma il sistema di scheduling cron"""
    global cron_scheduler_thread, cron_stop_event
    
    if cron_scheduler_thread and cron_scheduler_thread.is_alive():
        cron_stop_event.set()
        cron_scheduler_thread.join(timeout=10)
        logger.info("Sistema di scheduling cron fermato")

def update_cron_jobs():
    """Aggiorna i job cron attivi (riavvia il scheduler)"""
    logger.info("Aggiornamento sistema di scheduling cron")
    stop_cron_scheduler()
    start_cron_scheduler()

# Avvia il sistema di scheduling cron all'avvio dell'applicazione
def initialize_cron_scheduler():
    """Inizializza il sistema di scheduling cron all'avvio dell'applicazione"""
    logger.info("Inizializzazione sistema di scheduling cron")
    start_cron_scheduler()

# Registra la funzione di inizializzazione
with app.app_context():
    initialize_cron_scheduler()

# Aggiorna i job cron quando vengono salvati o aggiornati i comandi
def update_cron_after_command_change():
    """Aggiorna i job cron dopo una modifica ai comandi"""
    update_cron_jobs()

# Funzione per la chiusura pulita dell'applicazione
def cleanup_on_exit():
    """Chiude pulitamente tutti i servizi quando l'applicazione viene terminata"""
    logger.info("Chiusura applicazione in corso...")
    stop_cron_scheduler()
    logger.info("Sistema di scheduling cron fermato")

# Registra la funzione di cleanup
atexit.register(cleanup_on_exit)
signal.signal(signal.SIGTERM, lambda signum, frame: cleanup_on_exit())
signal.signal(signal.SIGINT, lambda signum, frame: cleanup_on_exit())

if __name__ == '__main__':
    logger.info("Avvio applicazione SSH Monitor")
    # Avvia il sistema di scheduling cron
    start_cron_scheduler()
    logger.info("Sistema di scheduling cron avviato")
    
    try:
        app.run(host='0.0.0.0', port=5000, debug=False)
    except KeyboardInterrupt:
        logger.info("Interruzione da tastiera ricevuta")
    finally:
        cleanup_on_exit()