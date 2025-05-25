#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import re
import json
import time
import threading
import subprocess
import psutil
import ipaddress
from datetime import datetime, timedelta
from pathlib import Path
import logging

import telegram
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.ext import Updater, CommandHandler, CallbackQueryHandler, MessageHandler, Filters, CallbackContext

# Configurazione logging
logger = logging.getLogger("SSH Monitor - Telegram Bot")

# Variabili globali per il bot Telegram
BOT_TOKEN = None
CHAT_ID = None
BOT_INSTANCE = None
UPDATER = None
MONITOR_THREAD = None

# Percorsi configurazione
CONFIG_PATH = Path('/etc/ssh_monitor/config.ini')
MOUNT_POINTS_FILE = Path('/etc/ssh_monitor/mount_points.json')

# Cache per i percorsi lunghi
PATH_CACHE = {}
PATH_COUNTER = 0

# Stato di upload e download
UPLOAD_STATES = {}
DOWNLOAD_STATES = {}

# Stato per la creazione di nuove cartelle
FOLDER_CREATION_STATES = {}

# Sistema di monitoraggio
MONITORING_CONFIG_FILE = Path('/etc/ssh_monitor/monitoring_config.json')
MONITORING_THREAD = None
MONITORING_ACTIVE = False
ALERT_STATES = {}  # Stato corrente degli alert
REMINDER_TIMERS = {}  # Timer per i reminder

# ----------------------------------------
# Funzioni per il sistema di monitoraggio
# ----------------------------------------

def get_default_monitoring_config():
    """Restituisce la configurazione predefinita per il monitoraggio"""
    return {
        "cpu_usage": {
            "enabled": False,
            "threshold": 80.0,
            "reminder_enabled": False,
            "reminder_interval": 300,  # 5 minuti in secondi
            "reminder_unit": "seconds"
        },
        "ram_usage": {
            "enabled": False,
            "threshold": 85.0,
            "reminder_enabled": False,
            "reminder_interval": 300,
            "reminder_unit": "seconds"
        },
        "cpu_temperature": {
            "enabled": False,
            "threshold": 70.0,
            "reminder_enabled": False,
            "reminder_interval": 600,
            "reminder_unit": "seconds"
        },
        "disk_usage": {
            # Struttura: {"mount_point": {"enabled": bool, "threshold": float, "reminder_enabled": bool, "reminder_interval": int}}
        },
        "network_connection": {
            "test_host": "8.8.8.8",
            "test_timeout": 5,
            "reconnect_alert": False
        },
        "monitoring_interval": 60,  # Controllo ogni 60 secondi
        "global_enabled": False
    }

def load_monitoring_config():
    """Carica la configurazione del monitoraggio dal file"""
    try:
        if MONITORING_CONFIG_FILE.exists():
            with open(MONITORING_CONFIG_FILE, "r") as f:
                config = json.load(f)
                # Merge con configurazione predefinita per parametri mancanti
                default_config = get_default_monitoring_config()
                for key, value in default_config.items():
                    if key not in config:
                        config[key] = value
                return config
        else:
            return get_default_monitoring_config()
    except Exception as e:
        logger.error(f"Errore nel caricamento della configurazione monitoraggio: {e}")
        return get_default_monitoring_config()

def save_monitoring_config(config):
    """Salva la configurazione del monitoraggio nel file"""
    try:
        MONITORING_CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(MONITORING_CONFIG_FILE, "w") as f:
            json.dump(config, f, indent=2)
        return True
    except Exception as e:
        logger.error(f"Errore nel salvataggio della configurazione monitoraggio: {e}")
        return False

def get_cpu_usage_value():
    """Ottiene la percentuale di utilizzo CPU corrente"""
    try:
        return psutil.cpu_percent(interval=1)
    except Exception as e:
        logger.error(f"Errore nel recupero dell'utilizzo CPU: {e}")
        return None

def get_ram_usage_value():
    """Ottiene la percentuale di utilizzo RAM corrente"""
    try:
        ram = psutil.virtual_memory()
        return ram.percent
    except Exception as e:
        logger.error(f"Errore nel recupero dell'utilizzo RAM: {e}")
        return None

def get_cpu_temperature_value():
    """Ottiene la temperatura CPU corrente"""
    try:
        temps = psutil.sensors_temperatures()
        # Cerca prima la CPU
        if 'coretemp' in temps:
            return temps['coretemp'][0].current
        elif 'cpu_thermal' in temps:
            return temps['cpu_thermal'][0].current
        # Altrimenti prendi la prima disponibile
        elif temps:
            for _, sensors in temps.items():
                if sensors:
                    return sensors[0].current
        return None
    except Exception as e:
        logger.error(f"Errore nel recupero della temperatura CPU: {e}")
        return None

def get_disk_usage_value(mount_point):
    """Ottiene la percentuale di utilizzo disco per un mount point"""
    try:
        if os.path.exists(mount_point):
            usage = psutil.disk_usage(mount_point)
            return usage.percent
        return None
    except Exception as e:
        logger.error(f"Errore nel recupero dell'utilizzo disco per {mount_point}: {e}")
        return None

def send_alert_notification(parameter_name, current_value, threshold, is_alert=True):
    """Invia una notifica di alert o recovery via Telegram"""
    try:
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        
        if is_alert:
            # Alert: parametro sopra soglia
            if parameter_name.startswith("disk_"):
                mount_point = parameter_name.replace("disk_", "")
                message = get_bot_translation("bot_messages.alert_messages.disk_alert", 
                                            mount_point=mount_point, 
                                            value=current_value, 
                                            threshold=threshold, 
                                            timestamp=timestamp)
            elif parameter_name == "cpu_usage":
                message = get_bot_translation("bot_messages.alert_messages.cpu_alert", 
                                            value=current_value, 
                                            threshold=threshold, 
                                            timestamp=timestamp)
            elif parameter_name == "ram_usage":
                message = get_bot_translation("bot_messages.alert_messages.ram_alert", 
                                            value=current_value, 
                                            threshold=threshold, 
                                            timestamp=timestamp)
            elif parameter_name == "cpu_temperature":
                message = get_bot_translation("bot_messages.alert_messages.temp_alert", 
                                            value=current_value, 
                                            threshold=threshold, 
                                            timestamp=timestamp)
        else:
            # Recovery: parametro rientrato nella soglia
            if parameter_name.startswith("disk_"):
                mount_point = parameter_name.replace("disk_", "")
                message = get_bot_translation("bot_messages.alert_messages.disk_recovery", 
                                            mount_point=mount_point, 
                                            value=current_value, 
                                            threshold=threshold, 
                                            timestamp=timestamp)
            elif parameter_name == "cpu_usage":
                message = get_bot_translation("bot_messages.alert_messages.cpu_recovery", 
                                            value=current_value, 
                                            threshold=threshold, 
                                            timestamp=timestamp)
            elif parameter_name == "ram_usage":
                message = get_bot_translation("bot_messages.alert_messages.ram_recovery", 
                                            value=current_value, 
                                            threshold=threshold, 
                                            timestamp=timestamp)
            elif parameter_name == "cpu_temperature":
                message = get_bot_translation("bot_messages.alert_messages.temp_recovery", 
                                            value=current_value, 
                                            threshold=threshold, 
                                            timestamp=timestamp)
        
        return send_telegram_message(message)
    except Exception as e:
        logger.error(f"Errore nell'invio della notifica: {e}")
        return False

def setup_reminder_timer(parameter_name, config):
    """Imposta un timer per il reminder di un parametro"""
    global REMINDER_TIMERS
    
    try:
        # Cancella timer esistente se presente
        if parameter_name in REMINDER_TIMERS:
            REMINDER_TIMERS[parameter_name].cancel()
            del REMINDER_TIMERS[parameter_name]
        
        # Verifica che il reminder sia abilitato
        if not config.get("reminder_enabled", False):
            logger.debug(f"Reminder non abilitato per {parameter_name}")
            return
        
        # Calcola l'intervallo in secondi
        interval = config.get("reminder_interval", 300)
        unit = config.get("reminder_unit", "seconds")
        
        if unit == "minutes":
            interval *= 60
        elif unit == "hours":
            interval *= 3600
        elif unit == "days":
            interval *= 86400
        
        logger.info(f"Impostazione reminder per {parameter_name}: intervallo {interval} secondi")
        
        # Crea il nuovo timer con una copia della configurazione
        config_copy = config.copy()  # Importante: crea una copia per evitare problemi di riferimento
        
        def reminder_callback():
            try:
                logger.info(f"Callback reminder eseguito per {parameter_name}")
                # Controlla se l'alert è ancora attivo
                if parameter_name in ALERT_STATES and ALERT_STATES[parameter_name]["active"]:
                    current_value = ALERT_STATES[parameter_name]["current_value"]
                    threshold = ALERT_STATES[parameter_name]["threshold"]
                    
                    logger.info(f"Invio reminder per {parameter_name}: valore {current_value}, soglia {threshold}")
                    send_alert_notification(parameter_name, current_value, threshold, is_alert=True)
                    
                    # Ricarica la configurazione corrente per il prossimo timer
                    current_config = load_monitoring_config()
                    if parameter_name.startswith("disk_"):
                        mount_point = parameter_name.replace("disk_", "")
                        param_config = current_config.get("disk_usage", {}).get(mount_point, {})
                    else:
                        param_config = current_config.get(parameter_name, {})
                    
                    # Imposta il prossimo reminder solo se ancora abilitato
                    if param_config.get("reminder_enabled", False):
                        setup_reminder_timer(parameter_name, param_config)
                    else:
                        logger.info(f"Reminder disabilitato per {parameter_name}, non imposto il prossimo timer")
                else:
                    logger.info(f"Alert non più attivo per {parameter_name}, annullo i reminder")
            except Exception as e:
                logger.error(f"Errore nel callback reminder per {parameter_name}: {e}")
        
        timer = threading.Timer(interval, reminder_callback)
        timer.start()
        REMINDER_TIMERS[parameter_name] = timer
        logger.info(f"Timer reminder impostato con successo per {parameter_name}")
        
    except Exception as e:
        logger.error(f"Errore nell'impostazione del timer per {parameter_name}: {e}")

def check_parameter_threshold(parameter_name, current_value, config):
    """Controlla se un parametro ha superato o rientrato nella soglia"""
    global ALERT_STATES
    
    try:
        if current_value is None:
            return
            
        threshold = config.get("threshold", 0)
        was_in_alert = parameter_name in ALERT_STATES and ALERT_STATES[parameter_name]["active"]
        
        # Controlla se il parametro supera la soglia
        if current_value > threshold:
            if not was_in_alert:
                # Nuovo alert
                ALERT_STATES[parameter_name] = {
                    "active": True,
                    "current_value": current_value,
                    "threshold": threshold,
                    "alert_start": datetime.now()
                }
                logger.info(f"Nuovo alert per {parameter_name}: valore {current_value} > soglia {threshold}")
                send_alert_notification(parameter_name, current_value, threshold, is_alert=True)
                
                # Imposta reminder se abilitato
                if config.get("reminder_enabled", False):
                    logger.info(f"Impostazione reminder per nuovo alert: {parameter_name}")
                    setup_reminder_timer(parameter_name, config)
                else:
                    logger.debug(f"Reminder non abilitato per {parameter_name}")
            else:
                # Aggiorna valore corrente per alert esistente
                ALERT_STATES[parameter_name]["current_value"] = current_value
                ALERT_STATES[parameter_name]["threshold"] = threshold
                logger.debug(f"Aggiornamento alert esistente per {parameter_name}: valore {current_value}")
                
                # Verifica se il reminder è ancora attivo e correttamente configurato
                if config.get("reminder_enabled", False):
                    # Se il reminder è abilitato ma non c'è un timer attivo, riavvialo
                    if parameter_name not in REMINDER_TIMERS:
                        logger.warning(f"Reminder abilitato ma timer non attivo per {parameter_name}, riavvio")
                        setup_reminder_timer(parameter_name, config)
                else:
                    # Se il reminder è stato disabilitato, cancella il timer esistente
                    if parameter_name in REMINDER_TIMERS:
                        logger.info(f"Reminder disabilitato per {parameter_name}, cancello timer")
                        REMINDER_TIMERS[parameter_name].cancel()
                        del REMINDER_TIMERS[parameter_name]
        else:
            if was_in_alert:
                # Recovery: parametro rientrato nella soglia
                send_alert_notification(parameter_name, current_value, threshold, is_alert=False)
                
                # Cancella timer reminder se presente
                if parameter_name in REMINDER_TIMERS:
                    REMINDER_TIMERS[parameter_name].cancel()
                    del REMINDER_TIMERS[parameter_name]
                
                # Rimuovi dallo stato alert
                del ALERT_STATES[parameter_name]
                
    except Exception as e:
        logger.error(f"Errore nel controllo soglia per {parameter_name}: {e}")

def monitoring_loop():
    """Loop principale del monitoraggio"""
    global MONITORING_ACTIVE
    
    logger.info("Sistema di monitoraggio avviato")
    
    while MONITORING_ACTIVE:
        try:
            config = load_monitoring_config()
            
            if not config.get("global_enabled", False):
                time.sleep(10)  # Controlla ogni 10 secondi se il monitoraggio è disabilitato
                continue
            
            # Controlla CPU
            if config["cpu_usage"]["enabled"]:
                cpu_value = get_cpu_usage_value()
                check_parameter_threshold("cpu_usage", cpu_value, config["cpu_usage"])
            
            # Controlla RAM
            if config["ram_usage"]["enabled"]:
                ram_value = get_ram_usage_value()
                check_parameter_threshold("ram_usage", ram_value, config["ram_usage"])
            
            # Controlla temperatura CPU
            if config["cpu_temperature"]["enabled"]:
                temp_value = get_cpu_temperature_value()
                check_parameter_threshold("cpu_temperature", temp_value, config["cpu_temperature"])
            
            # Controlla utilizzo disco per ogni mount point configurato
            for mount_point, mount_config in config["disk_usage"].items():
                if mount_config.get("enabled", False):
                    disk_value = get_disk_usage_value(mount_point)
                    parameter_name = f"disk_{mount_point}"
                    check_parameter_threshold(parameter_name, disk_value, mount_config)
            
            # Attendi l'intervallo di monitoraggio
            time.sleep(config.get("monitoring_interval", 60))
            
        except Exception as e:
            logger.error(f"Errore nel loop di monitoraggio: {e}")
            time.sleep(30)  # Attendi 30 secondi prima di riprovare
    
    logger.info("Sistema di monitoraggio arrestato")

def start_monitoring():
    """Avvia il sistema di monitoraggio"""
    global MONITORING_THREAD, MONITORING_ACTIVE
    
    if MONITORING_THREAD and MONITORING_THREAD.is_alive():
        logger.info("Sistema di monitoraggio già attivo")
        return True
    
    try:
        MONITORING_ACTIVE = True
        MONITORING_THREAD = threading.Thread(target=monitoring_loop, daemon=True)
        MONITORING_THREAD.start()
        logger.info("Sistema di monitoraggio avviato con successo")
        return True
    except Exception as e:
        logger.error(f"Errore nell'avvio del sistema di monitoraggio: {e}")
        MONITORING_ACTIVE = False
        return False

def stop_monitoring():
    """Ferma il sistema di monitoraggio"""
    global MONITORING_ACTIVE, REMINDER_TIMERS
    
    try:
        MONITORING_ACTIVE = False
        
        # Cancella tutti i timer di reminder
        for timer in REMINDER_TIMERS.values():
            timer.cancel()
        REMINDER_TIMERS.clear()
        
        # Pulisci gli stati di alert
        ALERT_STATES.clear()
        
        logger.info("Sistema di monitoraggio arrestato con successo")
        return True
    except Exception as e:
        logger.error(f"Errore nell'arresto del sistema di monitoraggio: {e}")
        return False

def get_monitoring_status():
    """Restituisce lo stato dettagliato del sistema di monitoraggio per debug"""
    global MONITORING_ACTIVE, ALERT_STATES, REMINDER_TIMERS
    
    status = {
        "monitoring_active": MONITORING_ACTIVE,
        "active_alerts": len(ALERT_STATES),
        "active_reminders": len(REMINDER_TIMERS),
        "alert_details": {},
        "reminder_details": {}
    }
    
    # Dettagli degli alert attivi
    for param_name, alert_info in ALERT_STATES.items():
        try:
            status["alert_details"][param_name] = {
                "active": bool(alert_info.get("active", False)),
                "current_value": float(alert_info.get("current_value", 0)),
                "threshold": float(alert_info.get("threshold", 0)),
                "alert_start": alert_info.get("alert_start", datetime.now()).isoformat()
            }
        except Exception as e:
            logger.error(f"Errore nella serializzazione dell'alert {param_name}: {e}")
            status["alert_details"][param_name] = {
                "active": False,
                "current_value": 0,
                "threshold": 0,
                "alert_start": "error",
                "error": str(e)
            }
    
    # Dettagli dei reminder attivi
    for param_name, timer in REMINDER_TIMERS.items():
        try:
            status["reminder_details"][param_name] = {
                "is_alive": bool(timer.is_alive()) if timer else False,
                "timer_exists": timer is not None
            }
        except Exception as e:
            logger.error(f"Errore nella serializzazione del timer {param_name}: {e}")
            status["reminder_details"][param_name] = {
                "is_alive": False,
                "timer_exists": False,
                "error": str(e)
            }
    
    logger.info(f"Stato monitoraggio preparato per serializzazione JSON")
    return status

# ----------------------------------------
# Funzioni di utilità
# ----------------------------------------

def cache_path(path):
    """Cache per i percorsi lunghi per evitare ButtonDataInvalid"""
    global PATH_CACHE, PATH_COUNTER
    
    # Se il percorso è più lungo di 40 caratteri, lo memorizziamo nella cache
    if len(path) > 40:
        PATH_COUNTER += 1
        cache_id = f"path_{PATH_COUNTER}"
        PATH_CACHE[cache_id] = path
        return cache_id
    return path

def get_cached_path(cache_id_or_path):
    """Recupera un percorso dalla cache o restituisce il percorso diretto"""
    global PATH_CACHE
    
    # Se è un ID della cache, recupera il percorso
    if cache_id_or_path.startswith("path_"):
        return PATH_CACHE.get(cache_id_or_path, "")
    return cache_id_or_path

def run_host_command(command):
    """Esegue un comando sull'host anziché nel container
    
    Utilizzando il socket Docker, è possibile eseguire comandi sull'host
    creando un container privilegiato che condivide i namespace dell'host.
    
    Args:
        command: Lista o stringa del comando da eseguire
        
    Returns:
        Il risultato dell'esecuzione del comando o None in caso di errore
    """
    try:
        if isinstance(command, list):
            cmd_str = " ".join(command)
        else:
            cmd_str = command
        
        # Per i comandi di sistema (reboot/poweroff) utilizziamo nsenter per accedere al namespace dell'host
        if "reboot" in cmd_str or "poweroff" in cmd_str or "shutdown" in cmd_str:
            # nsenter permette di eseguire comandi nei namespace dell'host
            docker_cmd = [
                "docker", "run", "--rm", "--privileged",
                "--pid=host", "--net=host", "--ipc=host",
                "--volume", "/:/host",  # Monta la root dell'host in /host
                "debian:stable-slim",     # Usiamo Debian invece di Alpine
                "chroot", "/host", "sh", "-c", cmd_str  # chroot nella root dell'host
            ]
        else:
            # Per altri comandi, utilizziamo il metodo standard
            docker_cmd = [
                "docker", "run", "--rm", "--privileged", 
                "--pid=host", "--net=host", "--ipc=host",
                "debian:stable-slim", "sh", "-c", cmd_str
            ]
        
        logger.info(f"Esecuzione comando sull'host: {cmd_str}")
        logger.debug(f"Comando docker: {' '.join(docker_cmd)}")
        
        result = subprocess.run(docker_cmd, capture_output=True, text=True)
        if result.returncode == 0:
            logger.info(f"Comando eseguito con successo sull'host.")
            return result
        else:
            logger.error(f"Errore nell'esecuzione del comando sull'host: {result.stderr}")
            return None
            
    except Exception as e:
        logger.error(f"Errore durante l'esecuzione del comando sull'host: {e}")
        return None

def load_mount_points():
    """Carica i mount points dal file di configurazione"""
    try:
        if MOUNT_POINTS_FILE.exists():
            with open(MOUNT_POINTS_FILE, "r") as f:
                return json.load(f)
        return []
    except Exception as e:
        logger.error(f"Errore nel caricamento dei mount points: {e}")
        return []

def save_mount_points(mount_points):
    """Salva i mount points nel file di configurazione"""
    try:
        MOUNT_POINTS_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(MOUNT_POINTS_FILE, "w") as f:
            json.dump(mount_points, f, indent=2)
        return True
    except Exception as e:
        logger.error(f"Errore nel salvataggio dei mount points: {e}")
        return False

def load_download_mount_points():
    """Carica i mount points download dal file di configurazione"""
    try:
        # Usa un file separato per i mount points download
        download_mount_points_file = Path('/etc/ssh_monitor/download_mount_points.json')
        if download_mount_points_file.exists():
            with open(download_mount_points_file, "r") as f:
                return json.load(f)
        return []
    except Exception as e:
        logger.error(f"Errore nel caricamento dei mount points download: {e}")
        return []

def save_download_mount_points(mount_points):
    """Salva i mount points download nel file di configurazione"""
    try:
        download_mount_points_file = Path('/etc/ssh_monitor/download_mount_points.json')
        download_mount_points_file.parent.mkdir(parents=True, exist_ok=True)
        with open(download_mount_points_file, "w") as f:
            json.dump(mount_points, f, indent=2)
        return True
    except Exception as e:
        logger.error(f"Errore nel salvataggio dei mount points download: {e}")
        return False

def get_local_ip():
    """Ottiene l'indirizzo IP locale del server"""
    try:
        # Usa hostname -I per ottenere gli indirizzi IP
        result = subprocess.run(['hostname', '-I'], capture_output=True, text=True)
        # Prende il primo IP (solitamente quello principale)
        ip = result.stdout.strip().split()[0]
        return ip
    except Exception as e:
        logger.error(f"Errore nel recupero dell'IP locale: {e}")
        return "unknown"

def get_uptime():
    """Ottiene l'uptime del sistema"""
    try:
        with open("/proc/uptime", "r") as f:
            return float(f.readline().split()[0])
    except:
        try:
            # Fallback per Docker: leggi uptime del sistema host
            with open("/host/proc/uptime", "r") as f:
                return float(f.readline().split()[0])
        except:
            return 0  # Se non riusciamo a leggere l'uptime, restituiamo 0

def format_uptime(uptime_seconds):
    """Formatta l'uptime in un formato leggibile"""
    days, remainder = divmod(int(uptime_seconds), 86400)
    hours, remainder = divmod(remainder, 3600)
    minutes, seconds = divmod(remainder, 60)
    
    result = ""
    if days > 0:
        day_text = get_bot_translation('bot_messages.time_units.day_plural') if days != 1 else get_bot_translation('bot_messages.time_units.day_singular')
        result += f"{days} {day_text}, "
    if hours > 0 or days > 0:
        hour_text = get_bot_translation('bot_messages.time_units.hour_plural') if hours != 1 else get_bot_translation('bot_messages.time_units.hour_singular')
        result += f"{hours} {hour_text}, "
    if minutes > 0 or hours > 0 or days > 0:
        minute_text = get_bot_translation('bot_messages.time_units.minute_plural') if minutes != 1 else get_bot_translation('bot_messages.time_units.minute_singular')
        result += f"{minutes} {minute_text}, "
    second_text = get_bot_translation('bot_messages.time_units.second_plural') if seconds != 1 else get_bot_translation('bot_messages.time_units.second_singular')
    result += f"{seconds} {second_text}"
    
    return result

def format_size(size_bytes):
    """Formatta le dimensioni in bytes in formato leggibile"""
    if size_bytes < 1024:
        return f"{size_bytes} bytes"
    elif size_bytes < 1024 * 1024:
        return f"{size_bytes / 1024:.1f} KB"
    elif size_bytes < 1024 * 1024 * 1024:
        return f"{size_bytes / (1024 * 1024):.1f} MB"
    else:
        return f"{size_bytes / (1024 * 1024 * 1024):.1f} GB"

# ----------------------------------------
# Funzioni per le risorse di sistema
# ----------------------------------------

def get_cpu_resources():
    """Ottiene informazioni sulle risorse CPU"""
    cpu_percent = psutil.cpu_percent(interval=1)
    cpu_count = psutil.cpu_count(logical=True)
    cpu_freq = psutil.cpu_freq()
    # Ottieni informazioni dettagliate sull'utilizzo della CPU
    cpu_times_percent = psutil.cpu_times_percent(interval=1)

    # Ottieni la temperatura se disponibile
    temperature = None
    try:
        temps = psutil.sensors_temperatures()
        # Cerca prima la CPU
        if 'coretemp' in temps:
            temperature = temps['coretemp'][0].current
        elif 'cpu_thermal' in temps:
            temperature = temps['cpu_thermal'][0].current
        # Altrimenti prendi la prima disponibile
        elif temps:
            for _, sensors in temps.items():
                if sensors:
                    temperature = sensors[0].current
                    break
    except:
        temperature = None
    
    # Ottieni l'uptime
    uptime = get_uptime()
    uptime_str = format_uptime(uptime)
    
    # Formatta il messaggio
    message = f"{get_bot_translation('bot_messages.resource_info.cpu_title')}\n\n"
    message += f"{get_bot_translation('bot_messages.resource_info.cpu_usage')}: *{cpu_percent}%*\n"
    message += f"{get_bot_translation('bot_messages.resource_info.cpu_cores')}: {cpu_count}\n"
    # Dettagli utilizzo CPU
    message += f"\n*{get_bot_translation('bot_messages.resource_info.usage_details')}:*\n"
    message += f"{get_bot_translation('bot_messages.resource_info.user')}: {cpu_times_percent.user:.1f}%\n"
    message += f"{get_bot_translation('bot_messages.resource_info.system')}: {cpu_times_percent.system:.1f}%\n"
    
    # Aggiunge iowait se disponibile
    if hasattr(cpu_times_percent, 'iowait'):
        message += f"{get_bot_translation('bot_messages.resource_info.iowait')}: {cpu_times_percent.iowait:.1f}%\n"
    
    message += f"{get_bot_translation('bot_messages.resource_info.idle')}: {cpu_times_percent.idle:.1f}%\n"
    
    # Informazioni sulla frequenza
    if cpu_freq:
        current_freq = cpu_freq.current
        message += f"\n{get_bot_translation('bot_messages.resource_info.frequency')}: {current_freq:.0f} MHz\n"
        if hasattr(cpu_freq, 'min') and cpu_freq.min:
            message += f"{get_bot_translation('bot_messages.resource_info.frequency_range')}: {cpu_freq.min:.0f}-{cpu_freq.max:.0f} MHz\n"
    # Informazioni sulla temperatura
    if temperature:
        message += f"\n{get_bot_translation('bot_messages.resource_info.temperature')}: *{temperature:.1f}°C*\n"
    
    message += f"\n*{get_bot_translation('bot_messages.resource_info.system_uptime')}:*\n{uptime_str}"
    
    return message

def get_ram_resources():
    """Ottiene informazioni sulle risorse RAM"""
    ram = psutil.virtual_memory()
    swap = psutil.swap_memory()
    
    # Formatta il messaggio
    message = f"{get_bot_translation('bot_messages.resource_info.ram_title')}\n\n"
    message += f"{get_bot_translation('bot_messages.resource_info.ram_total')}: {format_size(ram.total)}\n"
    message += f"{get_bot_translation('bot_messages.resource_info.ram_used')}: *{format_size(ram.used)}* ({ram.percent}%)\n"
    message += f"{get_bot_translation('bot_messages.resource_info.ram_available')}: {format_size(ram.available)}\n\n"
    
    message += f"{get_bot_translation('bot_messages.resource_info.swap_total')}: {format_size(swap.total)}\n"
    message += f"{get_bot_translation('bot_messages.resource_info.swap_used')}: {format_size(swap.used)} ({swap.percent}%)\n"
    
    return message

def get_disk_info():
    """Ottiene informazioni sui dischi"""
    partitions = psutil.disk_partitions()
    
    message = f"{get_bot_translation('bot_messages.resource_info.disk_title')}\n\n"
    # Monitora solo le partizioni di sistema specificate
    system_partitions = ['/', '/home', '/var', '/tmp']
    
    # Prima mostro le partizioni di sistema
    message += f"*{get_bot_translation('bot_messages.resource_info.system_partitions')}:*\n\n"
    for part in partitions:
        # Filtra solo le partizioni specificate
        if part.mountpoint in system_partitions:
            try:
                usage = psutil.disk_usage(part.mountpoint)
                
                # Evidenzia partizioni con spazio quasi esaurito
                highlight = usage.percent >= 90
                
                message += f"*{part.mountpoint}* ({part.fstype}):\n"
                message += f"  {get_bot_translation('bot_messages.resource_info.total')}: {format_size(usage.total)}\n"
                message += f"  {get_bot_translation('bot_messages.resource_info.used')}: {'*' if highlight else ''}{format_size(usage.used)} ({usage.percent}%){'*' if highlight else ''}\n"
                message += f"  {get_bot_translation('bot_messages.resource_info.free')}: {format_size(usage.free)}\n\n"
            except PermissionError:
                message += f"*{part.mountpoint}* ({get_bot_translation('bot_messages.resource_info.access_denied')})\n\n"
    # Poi mostro i punti di mount configurati
    message += f"*{get_bot_translation('bot_messages.resource_info.mount_points_configured')}:*\n\n"
    
    # Ottieni i punti di mount dalla configurazione
    mount_points = load_mount_points()
    
    if mount_points:
        for mount in mount_points:
            path = mount.get('path')
            if path and os.path.exists(path):
                try:
                    usage = psutil.disk_usage(path)
                    
                    # Evidenzia partizioni con spazio quasi esaurito
                    highlight = usage.percent >= 90
                    
                    message += f"*{path}*:\n"
                    message += f"  {get_bot_translation('bot_messages.resource_info.total')}: {format_size(usage.total)}\n"
                    message += f"  {get_bot_translation('bot_messages.resource_info.used')}: {'*' if highlight else ''}{format_size(usage.used)} ({usage.percent}%){'*' if highlight else ''}\n"
                    message += f"  {get_bot_translation('bot_messages.resource_info.free')}: {format_size(usage.free)}\n\n"
                except Exception as e:
                    message += f"*{path}* (Errore: {str(e)})\n\n"
    else:
        message += f"{get_bot_translation('bot_messages.resource_info.no_mount_points')}.\n\n"
        
    # Statistiche I/O solo per i punti di mount configurati
    try:
        # Ottieni le statistiche I/O per unità se disponibili
        
        # Aggiungiamo le statistiche I/O per unità se disponibili
        disk_io_per_disk = psutil.disk_io_counters(perdisk=True)
        if disk_io_per_disk and mount_points:
            message += f"\n*{get_bot_translation('bot_messages.resource_info.io_statistics')}:*\n"
            
            # Mappa dei dispositivi ai punti di mount
            mount_to_device = {}
            
            # Ottieni la mappa dei dispositivi
            try:
                # Usa il comando mount per ottenere la mappa
                result = subprocess.run(["mount"], capture_output=True, text=True)
                if result.returncode == 0:
                    mount_output = result.stdout.strip().split('\n')
                    for line in mount_output:
                        parts = line.split()
                        if len(parts) >= 3:
                            device = parts[0]
                            mount_point = parts[2]
                            
                            # Estrai il nome del dispositivo senza il percorso
                            device_name = os.path.basename(device)
                            
                            # Mappa il dispositivo al punto di mount
                            for mount in mount_points:
                                path = mount.get('path')
                                if path and (path == mount_point or mount_point.startswith(path + '/')):
                                    mount_to_device[device_name] = path
            except Exception as e:
                logger.error(f"Errore nell'ottenimento della mappa dispositivi: {str(e)}")
            
            # Mostra le statistiche solo per i dispositivi mappati ai punti di mount
            for disk, stats in disk_io_per_disk.items():
                # Cerca il disco nella mappa o controlla se è un disco principale
                if disk in mount_to_device or any(disk in device for device in mount_to_device.keys()):
                    mount_point = mount_to_device.get(disk, get_bot_translation('bot_messages.resource_info.mount_point_unknown'))
                    message += f"\n*{disk}* ({mount_point}):\n"
                    message += f"  {get_bot_translation('bot_messages.resource_info.reads')}: {format_size(stats.read_bytes)}\n"
                    message += f"  {get_bot_translation('bot_messages.resource_info.writes')}: {format_size(stats.write_bytes)}\n"
    except Exception as e:
        logger.error(f"Errore nel recupero delle statistiche I/O: {str(e)}")
    
    return message

def get_network_info():
    """Ottiene informazioni sulla rete"""
    # Ottieni le interfacce di rete
    net_if_addrs = psutil.net_if_addrs()
    # Ottieni statistiche I/O delle interfacce
    net_io_now = psutil.net_io_counters(pernic=True)
    
    # Ottieni l'IP locale del container
    local_ip = get_local_ip()
    # Ottieni l'IP pubblico
    public_ip = get_public_ip()
    
    # Ottieni l'IP locale del server host
    host_ip = get_host_ip()
         
    message = f"{get_bot_translation('bot_messages.resource_info.network_title')}\n\n"
    # IPs sezione
    message += f"*{get_bot_translation('bot_messages.resource_info.ip_addresses')}:*\n"
    message += f"{get_bot_translation('bot_messages.resource_info.ip_container')}: *{local_ip}*\n"
    
    if host_ip and host_ip != local_ip:
        message += f"{get_bot_translation('bot_messages.resource_info.ip_server_host')}: *{host_ip}*\n"
        
    if public_ip:
        message += f"{get_bot_translation('bot_messages.resource_info.ip_public')}: *{public_ip}*\n"
    
    # Statistiche totali (basate sull'interfaccia dell'host)
    try:
        # Prova a ottenere le statistiche dell'interfaccia dell'host
        host_stats = get_host_interface_stats(host_ip)
        
        if host_stats:
            message += f"\n*{get_bot_translation('bot_messages.resource_info.total_statistics')}:*\n"
            message += f"{get_bot_translation('bot_messages.resource_info.total_sent')}: {format_size(host_stats['bytes_sent'])}\n"
            message += f"{get_bot_translation('bot_messages.resource_info.total_received')}: {format_size(host_stats['bytes_recv'])}\n"
            
            # Calcola velocità di trasmissione
            # Prima misurazione
            time.sleep(1)  # Attendi 1 secondo
            
            # Seconda misurazione
            host_stats_new = get_host_interface_stats(host_ip)
            
            if host_stats_new:
                # Calcola la velocità
                upload_speed = host_stats_new['bytes_sent'] - host_stats['bytes_sent']
                download_speed = host_stats_new['bytes_recv'] - host_stats['bytes_recv']
                
                message += f"\n*{get_bot_translation('bot_messages.resource_info.current_speed')}:*\n"
                message += f"{get_bot_translation('bot_messages.resource_info.download')}: {format_size(download_speed)}/s\n"
                message += f"{get_bot_translation('bot_messages.resource_info.upload')}: {format_size(upload_speed)}/s\n"
        else:
            # Fallback alle statistiche totali se non riusciamo ad ottenere quelle dell'host
            total_stats = psutil.net_io_counters()
            message += f"\n*{get_bot_translation('bot_messages.resource_info.total_statistics')}:*\n"
            message += f"{get_bot_translation('bot_messages.resource_info.total_sent')}: {format_size(total_stats.bytes_sent)}\n"
            message += f"{get_bot_translation('bot_messages.resource_info.total_received')}: {format_size(total_stats.bytes_recv)}\n"
            
            # Calcola velocità di trasmissione
            time.sleep(1)
            total_stats_new = psutil.net_io_counters()
            
            upload_speed = total_stats_new.bytes_sent - total_stats.bytes_sent
            download_speed = total_stats_new.bytes_recv - total_stats.bytes_recv
            
            message += f"\n*{get_bot_translation('bot_messages.resource_info.current_speed')}:*\n"
            message += f"{get_bot_translation('bot_messages.resource_info.download')}: {format_size(download_speed)}/s\n"
            message += f"{get_bot_translation('bot_messages.resource_info.upload')}: {format_size(upload_speed)}/s\n"
            
    except Exception as e:
        logger.error(f"Errore nel calcolo delle statistiche di rete: {str(e)}")
    
    # Dettagli per interfaccia
    message += f"\n*{get_bot_translation('bot_messages.resource_info.network_interfaces')}:*\n"
    
    
    # Per ogni interfaccia, mostra l'indirizzo e le statistiche I/O
    for interface, addrs in net_if_addrs.items():
        # Escludiamo loopback e interfacce virtuali
        if interface != 'lo' and not interface.startswith('veth'):
            # Otteniamo l'indirizzo IPv4 se disponibile
            ipv4 = None
            for addr in addrs:
                if addr.family == 2:  # AF_INET (IPv4)
                    ipv4 = addr.address
                    break
            
            if ipv4:
                message += f"\n*{interface}* ({ipv4})\n"
                
                # Aggiungiamo le statistiche I/O se disponibili
                if interface in net_io_now:
                    stats = net_io_now[interface]
                    message += f"  {get_bot_translation('bot_messages.resource_info.total_sent')}: {format_size(stats.bytes_sent)}\n"
                    message += f"  {get_bot_translation('bot_messages.resource_info.total_received')}: {format_size(stats.bytes_recv)}\n"
                    message += f"  {get_bot_translation('bot_messages.resource_info.packets_sent')}: {stats.packets_sent}\n"
                    message += f"  {get_bot_translation('bot_messages.resource_info.packets_received')}: {stats.packets_recv}\n"
    
    return message

def get_public_ip():
    """Ottieni l'indirizzo IP pubblico"""
    try:
        import requests as requests_module  # Importa localmente per evitare problemi di scope
        response = requests_module.get('https://api.ipify.org', timeout=5)
        return response.text.strip()
    except Exception as e:
        logger.error(f"Errore nel recupero dell'IP pubblico: {str(e)}")
        return None

def get_host_ip():
    """Ottieni l'indirizzo IP del server host"""
    try:
        # Prova a eseguire un comando sul server host
        result = run_host_command("hostname -I | awk '{print $1}'")
        if result and result.stdout:
            return result.stdout.strip()
        return None
    except Exception as e:
        logger.error(f"Errore nel recupero dell'IP host: {str(e)}")
        return None

def get_host_interface_stats(host_ip):
    """Ottieni le statistiche dell'interfaccia dell'host basandosi sull'IP"""
    try:
        if not host_ip:
            return None
            
        # Metodo 1: Prova con ip -j (JSON output)
        result = run_host_command("ip -j addr show 2>/dev/null")
        host_interface = None
        
        if result and result.stdout:
            try:
                import json
                interfaces = json.loads(result.stdout)
                
                # Trova l'interfaccia che ha l'IP dell'host
                for iface in interfaces:
                    if 'addr_info' in iface:
                        for addr in iface['addr_info']:
                            if addr.get('local') == host_ip and addr.get('family') == 'inet':
                                host_interface = iface['ifname']
                                break
                    if host_interface:
                        break
            except:
                pass
        
        # Metodo 2: Fallback con ip addr show (output text)
        if not host_interface:
            result = run_host_command(f"ip addr show | grep -B2 '{host_ip}/' | grep '^[0-9]' | head -1")
            if result and result.stdout:
                # Estrai il nome dell'interfaccia dal formato "2: eth0: <BROADCAST..."
                line = result.stdout.strip()
                if ':' in line:
                    parts = line.split(':')
                    if len(parts) >= 2:
                        host_interface = parts[1].strip()
        
        # Metodo 3: Fallback con ifconfig se disponibile
        if not host_interface:
            result = run_host_command(f"ifconfig | grep -B1 '{host_ip}' | grep '^[a-zA-Z]' | head -1")
            if result and result.stdout:
                line = result.stdout.strip()
                if line:
                    host_interface = line.split()[0]
        
        if not host_interface:
            logger.warning(f"Impossibile trovare l'interfaccia per l'IP host {host_ip}")
            return None
            
        # Ottieni le statistiche dell'interfaccia dell'host
        result = run_host_command(f"cat /proc/net/dev | grep '{host_interface}:'")
        if not result or not result.stdout:
            return None
            
        # Parsing delle statistiche di /proc/net/dev
        line = result.stdout.strip()
        if ':' in line:
            parts = line.split(':')[1].split()
            if len(parts) >= 16:
                return {
                    'interface': host_interface,
                    'bytes_recv': int(parts[0]),
                    'packets_recv': int(parts[1]),
                    'bytes_sent': int(parts[8]),
                    'packets_sent': int(parts[9])
                }
                
        return None
    except Exception as e:
        logger.error(f"Errore nel recupero delle statistiche dell'interfaccia host: {str(e)}")
        return None

def get_top_processes(num=5):
    """Ottiene i processi con maggiore utilizzo di CPU e RAM"""
    # Ottieni tutti i processi
    processes = []
    for proc in psutil.process_iter(['pid', 'name', 'username', 'cpu_percent', 'memory_percent']):
        try:
            # Aggiorna la percentuale di CPU (richiede un intervallo)
            proc.info['cpu_percent'] = proc.cpu_percent(interval=0.1)
            processes.append(proc.info)
        except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
            pass
    
    # Ordina per CPU
    cpu_processes = sorted(processes, key=lambda p: p['cpu_percent'], reverse=True)[:num]
    # Ordina per RAM
    ram_processes = sorted(processes, key=lambda p: p['memory_percent'], reverse=True)[:num]
    
    # Formatta il messaggio
    message = f"*Top {num} Processi per CPU*\n\n"
    for i, proc in enumerate(cpu_processes, 1):
        message += f"{i}. {proc['name']} (PID: {proc['pid']})\n"
        message += f"   CPU: {proc['cpu_percent']:.1f}% | RAM: {proc['memory_percent']:.1f}%\n"
        message += f"   Utente: {proc['username']}\n\n"
    
    message += f"*Top {num} Processi per RAM*\n\n"
    for i, proc in enumerate(ram_processes, 1):
        message += f"{i}. {proc['name']} (PID: {proc['pid']})\n"
        message += f"   RAM: {proc['memory_percent']:.1f}% | CPU: {proc['cpu_percent']:.1f}%\n"
        message += f"   Utente: {proc['username']}\n\n"
    
    return message

# ----------------------------------------
# Funzioni per il bot Telegram
# ----------------------------------------

def init_bot(token=None, chat_id=None):
    """Inizializza il bot Telegram"""
    global BOT_INSTANCE, UPDATER, BOT_TOKEN, CHAT_ID
    
    # Usa i valori forniti o quelli globali
    BOT_TOKEN = token or BOT_TOKEN
    CHAT_ID = chat_id or CHAT_ID
    
    if not BOT_INSTANCE and BOT_TOKEN:
        try:
            BOT_INSTANCE = telegram.Bot(token=BOT_TOKEN)
            UPDATER = Updater(token=BOT_TOKEN, use_context=True)
            
            # Registra gli handler per i comandi (multilingue)
            dp = UPDATER.dispatcher
            # Comandi universali (stessi per tutte le lingue)
            # IMPORTANTE: Questi comandi NON devono mai essere tradotti per evitare problemi
            dp.add_handler(CommandHandler("res", command_risorse))      # Risorse sistema
            dp.add_handler(CommandHandler("start", command_start))      # Avvia bot
            dp.add_handler(CommandHandler("help", command_help))        # Aiuto
            dp.add_handler(CommandHandler("reboot", command_reboot))    # Riavvia server
            dp.add_handler(CommandHandler("docker", command_docker))    # Gestione Docker
            dp.add_handler(CommandHandler("upload", command_upload))    # Upload file
            dp.add_handler(CommandHandler("download", command_download))  # Download file
            dp.add_handler(CallbackQueryHandler(button_callback))
            # Aggiungiamo un handler per i file ricevuti
            dp.add_handler(MessageHandler(Filters.document, handle_file_upload))
            # Handler per input di testo (per la creazione di cartelle)
            dp.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_text_input))
            
            # Avvia il polling in un thread separato
            UPDATER.start_polling(drop_pending_updates=True)
            
            # Avvia il sistema di monitoraggio
            start_monitoring()
            
            logger.info("Bot Telegram inizializzato con successo")
            return True
        except Exception as e:
            logger.error(f"Errore nell'inizializzazione del bot Telegram: {e}")
            return False
    return bool(BOT_INSTANCE)

def stop_bot():
    """Ferma il bot Telegram"""
    global UPDATER, BOT_INSTANCE
    
    if UPDATER:
        try:
            # Ferma il sistema di monitoraggio
            stop_monitoring()
            
            UPDATER.stop()
            UPDATER = None
            BOT_INSTANCE = None
            logger.info("Bot Telegram fermato con successo")
            return True
        except Exception as e:
            logger.error(f"Errore nell'arresto del bot Telegram: {e}")
            return False
    return True

def get_resource_keyboard():
    """Costruisce la tastiera inline per i comandi del bot"""
    keyboard = [
        [
            InlineKeyboardButton(get_bot_translation("bot_messages.cpu"), callback_data="cpu_resources"),
            InlineKeyboardButton(get_bot_translation("bot_messages.ram"), callback_data="ram_resources")
        ],
        [
            InlineKeyboardButton(get_bot_translation("bot_messages.disk"), callback_data="disk_resources"),
            InlineKeyboardButton(get_bot_translation("bot_messages.network"), callback_data="network_resources")
        ],
        [
            InlineKeyboardButton(get_bot_translation("bot_messages.docker_list"), callback_data="docker_list")
        ],
        [
            InlineKeyboardButton(get_bot_translation("bot_messages.all_resources"), callback_data="all_resources")
        ]
    ]
    return InlineKeyboardMarkup(keyboard)

def command_risorse(update, context):
    """Handler per il comando /res"""
    message = get_bot_translation("bot_messages.choose_resource")
    update.message.reply_text(
        message,
        reply_markup=get_resource_keyboard()
    )

def command_start(update, context):
    """Handler per il comando /start"""
    message = get_bot_translation("bot_messages.welcome")
    update.message.reply_text(message)

def command_help(update, context):
    """Handler per il comando /help"""
    message = get_bot_translation("bot_messages.help")
    update.message.reply_text(message)

def command_download(update, context):
    """Handler per il comando /download per scaricare files dal server"""
    global DOWNLOAD_STATES
    
    # Identifica l'utente
    chat_id = update.effective_chat.id
    
    # Inizializza lo stato di download per questo utente
    DOWNLOAD_STATES[chat_id] = {
        "state": "selecting_directory",  # Stato iniziale: selezione della directory
        "current_path": None,           # Percorso corrente durante la navigazione
        "parent_paths": [],             # Storico dei percorsi per navigare indietro
        "timestamp": time.time()        # Timestamp per timeout
    }
    
    # Ottieni i mount points download configurati
    mount_points = load_download_mount_points()
    
    # Iniziamo con una lista vuota per la tastiera
    keyboard = []
    
    if mount_points:
        # Aggiungi un pulsante per ogni mount point
        for mount in mount_points:
            path = mount.get('path', '')
            if path:
                # Usa solo il nome della directory come testo del pulsante
                display_name = os.path.basename(path) or path
                keyboard.append([InlineKeyboardButton(f"📁 {display_name}", callback_data=f"download_mount_{path}")])
    
    # Pulsante di annullamento
    keyboard.append([InlineKeyboardButton(get_bot_translation("bot_messages.download.cancel"), callback_data="download_cancel")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    if mount_points:
        message = get_bot_translation("bot_messages.download.title") + "\n\n"
        message += get_bot_translation("bot_messages.download.select_mount") + "\n\n"
        message += get_bot_translation("bot_messages.download.note")
    else:
        message = get_bot_translation("bot_messages.download.no_mount_points")
    
    update.message.reply_text(
        message,
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )

def command_reboot(update, context):
    """Handler per il comando /reboot"""
    keyboard = [
        [InlineKeyboardButton(get_bot_translation("bot_messages.reboot_yes"), callback_data="confirm_reboot")],
        [InlineKeyboardButton(get_bot_translation("bot_messages.reboot_no"), callback_data="cancel_action")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    message = get_bot_translation("bot_messages.reboot_confirm")
    update.message.reply_text(
        message,
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )

def command_docker(update, context, page=0):
    """Handler per il comando /docker con paginazione"""
    try:
        # Ottieni la lista dei container Docker
        result = subprocess.run(['docker', 'ps', '-a', '--format', '{{.Names}}\t{{.Status}}\t{{.Image}}'], 
                              capture_output=True, text=True, check=True)
        
        containers = result.stdout.strip().split('\n')
        
        if not containers or not containers[0]:
            if hasattr(update, 'callback_query'):
                update.callback_query.edit_message_text("Nessun container Docker trovato.")
            else:
                update.message.reply_text("Nessun container Docker trovato.")
            return
        
        # Crea una tastiera con un pulsante per ogni container
        keyboard = []
        running_containers = []
        stopped_containers = []
        
        # Ordina i container per stato (running/stopped) e per nome
        for container in containers:
            if not container.strip():
                continue
                
            parts = container.split('\t')
            name = parts[0] if len(parts) > 0 else "Unknown"
            status = parts[1] if len(parts) > 1 else "Unknown"
            image = parts[2] if len(parts) > 2 else ""
            
            # Determina se il container è in esecuzione
            is_running = 'Up' in status
            container_data = {'name': name, 'status': status, 'image': image}
            
            if is_running:
                running_containers.append(container_data)
            else:
                stopped_containers.append(container_data)
        
        # Ordina i container per nome
        running_containers.sort(key=lambda x: x['name'])
        stopped_containers.sort(key=lambda x: x['name'])
        
        # Prepara tutti i container in un'unica lista
        all_containers = []
        
        # Aggiungiamo i container in esecuzione
        if running_containers:
            for container in running_containers:
                # Estrai il tempo di uptime dal messaggio di stato in formato ultra-compatto
                uptime_text = ""
                if "Up" in container['status']:
                    uptime_match = re.search(r'Up (.*)', container['status'])
                    if uptime_match:
                        uptime = uptime_match.group(1)
                        # Rendi l'uptime ultra-compatto
                        uptime = uptime.replace(" hours", "h").replace(" hour", "h")
                        uptime = uptime.replace(" minutes", "m").replace(" minute", "m")
                        uptime = uptime.replace(" seconds", "s").replace(" second", "s")
                        uptime = uptime.replace(" days", "d").replace(" day", "d")
                        # Mantieni gli spazi per maggiore leggibilità
                        uptime = uptime.replace("ago", "").strip()
                        uptime_text = f" - {uptime}"
                
                container_name = container['name']
                # Aggiungi container alla lista con le sue info
                all_containers.append({
                    "name": container_name,
                    "display_name": container_name,
                    "status": "running",
                    "uptime_text": uptime_text
                })
        
        # Aggiungiamo i container fermi
        if stopped_containers:
            for container in stopped_containers:
                container_name = container['name']
                # Aggiungi container alla lista con le sue info
                all_containers.append({
                    "name": container_name,
                    "display_name": container_name,
                    "status": "stopped",
                    "uptime_text": ""
                })
        
        # Calcola il numero totale di pagine
        containers_per_page = 10
        total_containers = len(all_containers)
        total_pages = (total_containers + containers_per_page - 1) // containers_per_page
        
        # Assicurati che la pagina richiesta sia valida
        page = max(0, min(page, total_pages - 1)) if total_pages > 0 else 0
        
        # Ottieni i container per la pagina corrente
        start_idx = page * containers_per_page
        end_idx = min(start_idx + containers_per_page, total_containers)
        current_page_containers = all_containers[start_idx:end_idx]
        
        # Crea un bottone per ogni container nella pagina corrente
        for container in current_page_containers:
            # Mostra il nome completo del container, ora che abbiamo più spazio
            display_name = container["display_name"]
                
            if container["status"] == "running":
                # Container in esecuzione con uptime in grassetto - riempie tutto lo schermo
                button_text = f"🟢  {display_name}{container['uptime_text']}  "
            else:
                # Container fermo in grassetto - riempie tutto lo schermo
                button_text = f"🔴  {display_name}  "
                
            # Crea un singolo pulsante che occupa tutta la larghezza della riga
            # In Telegram, quando un pulsante è l'unico nella riga, si espande per occupare tutto lo spazio disponibile
            keyboard.append([
                InlineKeyboardButton(button_text, callback_data=f"docker_{container['name']}")
            ])
        
        # Aggiungi i pulsanti di navigazione se ci sono più pagine
        nav_buttons = []
        
        if total_pages > 1:
            # Aggiungi pulsante per pagina precedente se non siamo alla prima pagina
            if page > 0:
                nav_buttons.append(
                    InlineKeyboardButton(get_bot_translation("bot_messages.previous"), callback_data=f"docker_page_{page-1}")
                )
                
            # Informazioni sulla pagina
            page_info = f"{page+1}/{total_pages}"
            nav_buttons.append(
                InlineKeyboardButton(page_info, callback_data="docker_page_info")
            )
            
            # Aggiungi pulsante per pagina successiva se non siamo all'ultima pagina
            if page < total_pages - 1:
                nav_buttons.append(
                    InlineKeyboardButton(get_bot_translation("bot_messages.next"), callback_data=f"docker_page_{page+1}")
                )
        
        # Aggiungi la riga di navigazione se ci sono più pagine
        if nav_buttons:
            keyboard.append(nav_buttons)
                
        # Aggiungi pulsante per tornare al menu principale
        keyboard.append([InlineKeyboardButton(get_bot_translation("bot_messages.back_to_resources"), callback_data="back_to_resources")])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # Mostra intestazione con conteggio totale e pagina corrente
        docker_summary = get_bot_translation("bot_messages.docker_summary", running=len(running_containers), stopped=len(stopped_containers))
        if total_pages > 1:
            message = f"{get_bot_translation('bot_messages.docker_management')} ({docker_summary}) - Pag {page+1}/{total_pages}"
        else:
            message = f"{get_bot_translation('bot_messages.docker_management')} ({docker_summary})"
        
        # Aggiorna il messaggio se è un callback, altrimenti invia un nuovo messaggio
        if hasattr(update, 'callback_query') and update.callback_query is not None:
            try:
                update.callback_query.edit_message_text(text=message, reply_markup=reply_markup, parse_mode="Markdown")
            except Exception as edit_error:
                logger.error(f"Errore nell'aggiornamento del messaggio: {str(edit_error)}")
                # Se fallisce l'aggiornamento, invia un nuovo messaggio
                update.callback_query.message.reply_text(text=message, reply_markup=reply_markup, parse_mode="Markdown")
        else:
            update.message.reply_text(text=message, reply_markup=reply_markup, parse_mode="Markdown")
            
    except Exception as e:
        error_message = f"Errore nel recupero dei container Docker: {e}"
        if hasattr(update, 'callback_query') and update.callback_query is not None:
            update.callback_query.edit_message_text(text=error_message)
        else:
            update.message.reply_text(error_message)

def command_upload(update, context):
    """Handler per il comando /upload per caricare files sul server"""
    global UPLOAD_STATES
    
    # Identifica l'utente
    chat_id = update.effective_chat.id
    
    # Inizializza lo stato di upload per questo utente
    UPLOAD_STATES[chat_id] = {
        "state": "selecting_directory",  # Stato iniziale: selezione della directory
        "dir": None,                    # Directory di destinazione
        "pending_files": [],            # Lista di file in attesa di essere salvati
        "timestamp": time.time(),       # Timestamp per timeout
        "current_path": None,          # Percorso corrente durante la navigazione
        "parent_paths": []             # Storico dei percorsi per navigare indietro
    }
    
    # Ottieni i mount points configurati
    mount_points = load_mount_points()
    
    # Iniziamo con una lista vuota per la tastiera
    keyboard = []
    
    # Aggiungi i mount points configurati
    if mount_points:
        for mount in mount_points:
            path = mount.get("path")
            if path:
                keyboard.append([InlineKeyboardButton(f"📂 {path}", callback_data=f"browse_dir_{path}")])
    else:
        # Se non ci sono mount points configurati, mostra un messaggio
        error_msg = get_bot_translation("bot_messages.upload.no_mount_points")
        update.message.reply_text(error_msg)
        return
    
    # Aggiungi pulsante di annullamento
    cancel_label = get_bot_translation("bot_messages.upload.cancel")
    keyboard.append([InlineKeyboardButton(cancel_label, callback_data="upload_cancel")])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Prepara il messaggio
    title = get_bot_translation("bot_messages.upload.title")
    select_msg = get_bot_translation("bot_messages.upload.select_mount")
    note = get_bot_translation("bot_messages.upload.note")
    message_text = f"{title}\n\n{select_msg}\n\n{note}"
    
    # Invia il messaggio
    update.message.reply_text(
        text=message_text,
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )

def handle_text_input(update, context):
    """Gestisce l'input testuale dell'utente per varie funzionalità"""
    global FOLDER_CREATION_STATES, UPLOAD_STATES
    
    # Identifica l'utente
    chat_id = update.effective_chat.id
    
    # Gestione creazione nuove cartelle
    if chat_id in FOLDER_CREATION_STATES:
        folder_state = FOLDER_CREATION_STATES[chat_id]
        parent_path = folder_state["parent_path"]
        message_id = folder_state["message_id"]
        
        # Ottieni il nome della cartella dall'input dell'utente
        folder_name = update.message.text.strip()
        
        # Verifica che il nome sia valido
        if not folder_name or '/' in folder_name or folder_name in ['.', '..']:
            update.message.reply_text(
                "⚠️ Nome cartella non valido. Usa un nome senza caratteri speciali o barre.",
                parse_mode="Markdown"
            )
            return
        
        # Costruisci il percorso completo
        new_folder_path = os.path.join(parent_path, folder_name)
        
        try:
            # Verifica se la cartella esiste già
            if os.path.exists(new_folder_path):
                update.message.reply_text(
                    f"⚠️ La cartella `{folder_name}` esiste già in questo percorso.",
                    parse_mode="Markdown"
                )
                return
            
            # Crea la cartella
            os.makedirs(new_folder_path, exist_ok=True)
            
            # Invia messaggio di successo
            update.message.reply_text(
                get_bot_translation("bot_messages.upload.folder_created_success", folder_name=folder_name),
                parse_mode="Markdown"
            )
            
            # Aggiorna il messaggio di navigazione
            try:
                # Crea un oggetto callback_query fittizio per riutilizzare handle_browse_directory
                query = type('obj', (object,), {
                    'message': type('obj', (object,), {
                        'chat_id': chat_id,
                        'message_id': message_id,
                        'edit_text': lambda **kwargs: None,
                        'edit_message_text': lambda **kwargs: None
                    }),
                    'edit_message_text': lambda **kwargs: None,
                    'answer': lambda *args, **kwargs: None
                })
                
                # Chiama la funzione di navigazione con il percorso del genitore
                context.bot.delete_message(chat_id=chat_id, message_id=message_id)
                
                # Crea un nuovo messaggio di navigazione
                keyboard = [[InlineKeyboardButton("📂 " + get_bot_translation("bot_messages.upload.continue_navigation"), callback_data=f"browse_dir_{parent_path}")]]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                update.message.reply_text(
                    get_bot_translation("bot_messages.upload.navigate_new_folder", path=new_folder_path),
                    reply_markup=reply_markup,
                    parse_mode="Markdown"
                )
                
            except Exception as e:
                logger.error(f"Errore nell'aggiornamento del messaggio di navigazione: {e}")
        
        except Exception as e:
            update.message.reply_text(
                f"⚠️ Errore nella creazione della cartella: {str(e)}",
                parse_mode="Markdown"
            )
        
        # Rimuovi lo stato di creazione cartella
        del FOLDER_CREATION_STATES[chat_id]
        return

def handle_file_upload(update, context):
    """Gestisce i file caricati dall'utente"""
    global UPLOAD_STATES
    
    # Identifica l'utente
    chat_id = update.effective_chat.id
    
    # Controlla se l'utente è in modalità upload
    if chat_id not in UPLOAD_STATES or UPLOAD_STATES[chat_id]["state"] != "uploading":
        update.message.reply_text(get_bot_translation("bot_messages.upload.upload_required"))
        return
    
    # Ottieni la directory di destinazione
    dest_dir = UPLOAD_STATES[chat_id]["dir"]
    if not dest_dir:
        update.message.reply_text("⚠️ Errore: nessuna directory di destinazione specificata. Usa /upload per ricominciare.")
        # Resetta lo stato
        del UPLOAD_STATES[chat_id]
        return
    
    # Controlla se la directory esiste
    if not os.path.isdir(dest_dir):
        try:
            # Prova a creare la directory se non esiste
            os.makedirs(dest_dir, exist_ok=True)
            update.message.reply_text(f"📂 Creata directory: {dest_dir}")
        except Exception as e:
            update.message.reply_text(f"⚠️ Errore: impossibile creare la directory {dest_dir}\n{str(e)}")
            # Resetta lo stato
            del UPLOAD_STATES[chat_id]
            return
    
    # Ottieni il file document dal messaggio
    document = update.message.document
    file_name = document.file_name
    file_id = document.file_id
    file_size = document.file_size
    
    try:
        # Informa l'utente che stiamo scaricando il file
        progress_message = update.message.reply_text(
            f"📋 *Scaricamento in corso:*\n" +
            f"File: `{file_name}`\n" +
            f"Dimensione: {format_size(file_size)}\n" +
            f"Destinazione: `{dest_dir}`",
            parse_mode="Markdown"
        )
        
        # Ottieni il file dal servizio Telegram
        file = context.bot.get_file(file_id)
        
        # Costruisci il percorso completo di destinazione
        dest_path = os.path.join(dest_dir, file_name)
        
        # Prima verifica che la cartella sia scrivibile facendo un test
        test_file = os.path.join(dest_dir, ".tmp_write_test")
        try:
            with open(test_file, "wb") as f:
                f.write(b"test")
            os.unlink(test_file)  # Rimuovi il file di test
        except Exception as test_error:
            raise Exception(f"Directory non scrivibile: {str(test_error)}")

        download_success = False
        error_messages = []
        
        # Metodo 1: Download tramite requests
        try:
            import requests
            file_url = file.file_path
            response = requests.get(file_url, stream=True)
            response.raise_for_status()
            with open(dest_path, 'wb') as out_file:
                for chunk in response.iter_content(chunk_size=8192): 
                    if chunk:
                        out_file.write(chunk)
            download_success = True
            logger.info(f"Download completato con metodo 1 (requests) per {file_name}")
        except Exception as e1:
            error_messages.append(f"Metodo 1 fallito: {str(e1)}")
            logger.error(f"Errore metodo 1: {str(e1)}")
        
        # Metodo 2: Download diretto con Telegram API
        if not download_success:
            try:
                file.download(custom_path=dest_path)
                download_success = True
                logger.info(f"Download completato con metodo 2 (download diretto) per {file_name}")
            except Exception as e2:
                error_messages.append(f"Metodo 2 fallito: {str(e2)}")
                logger.error(f"Errore metodo 2: {str(e2)}")
        
        # Controlla se il download è riuscito
        if not download_success:
            raise Exception("Tutti i metodi di download hanno fallito:\n" + "\n".join(error_messages))
            
        # Verifica che il file esista davvero sul disco
        if not os.path.exists(dest_path):
            raise Exception(f"Il file sembra essere stato scaricato, ma non è presente nella posizione {dest_path}")
            
        # Controlla la dimensione del file scaricato
        saved_size = os.path.getsize(dest_path)
        if saved_size < 10:  # Se il file è troppo piccolo, potrebbe essere un errore
            raise Exception(f"Il file salvato è troppo piccolo: solo {saved_size} bytes")
        
        # Aggiorna il messaggio di progresso
        context.bot.edit_message_text(
            chat_id=chat_id,
            message_id=progress_message.message_id,
            text=get_bot_translation("bot_messages.upload.file_saved_success", 
                                   filename=file_name,
                                   size=format_size(saved_size),
                                   path=dest_path),
            parse_mode="Markdown"
        )
        
        # Aggiungi pulsanti per continuare o terminare
        keyboard = [
            [InlineKeyboardButton(get_bot_translation("bot_messages.upload.upload_more_files"), callback_data="upload_continue")],
            [InlineKeyboardButton(get_bot_translation("bot_messages.upload.done"), callback_data="upload_finish")]
        ]
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        update.message.reply_text(
            get_bot_translation("bot_messages.upload.upload_question"),
            reply_markup=reply_markup
        )
        
    except Exception as e:
        # Fornisci un messaggio di errore dettagliato
        error_message = f"⚠️ *Errore durante il salvataggio del file*\n\n" + \
                      f"File: `{file_name}`\n" + \
                      f"Directory: `{dest_dir}`\n\n" + \
                      f"Errore: `{str(e)}`\n\n" + \
                      "*Suggerimenti:*\n" + \
                      "1. Scegli una directory non montata in sola lettura\n" + \
                      "2. Prova la directory /tmp che è solitamente scrivibile\n" + \
                      "3. Verifica i permessi del filesystem"  
                      
        update.message.reply_text(error_message, parse_mode="Markdown")
        
        # Registra l'errore per il debug
        logger.error(f"Errore upload file: {str(e)}")
        
        # Offri la possibilità di ricominciare
        keyboard = [[InlineKeyboardButton("↩️ Riprova con un'altra directory", callback_data="upload_restart")]]
        reply_markup = InlineKeyboardMarkup(keyboard)
        update.message.reply_text("Vuoi riprovare con un'altra directory?", reply_markup=reply_markup)

def get_back_button_keyboard():
    """Crea una tastiera con solo il pulsante Torna indietro"""
    keyboard = [[InlineKeyboardButton(get_bot_translation("bot_messages.back"), callback_data="back_to_resources")]]
    return InlineKeyboardMarkup(keyboard)

def button_callback(update, context):
    """Gestisce i callback dai pulsanti inline"""
    query = update.callback_query
    query.answer()
    
    # Ottieni il testo del callback data
    callback_data = query.data
    
    # Gestisci i vari tipi di callback
    if callback_data == "cpu_resources":
        # Mostra risorse CPU
        response = get_cpu_resources()
        query.edit_message_text(text=response, reply_markup=get_back_button_keyboard(), parse_mode="Markdown")
        
    elif callback_data == "ram_resources":
        # Mostra risorse RAM
        response = get_ram_resources()
        query.edit_message_text(text=response, reply_markup=get_back_button_keyboard(), parse_mode="Markdown")
        
    elif callback_data == "disk_resources":
        # Mostra risorse disco
        response = get_disk_info()
        query.edit_message_text(text=response, reply_markup=get_back_button_keyboard(), parse_mode="Markdown")
        
    elif callback_data == "network_resources":
        # Mostra risorse rete
        response = get_network_info()
        query.edit_message_text(text=response, reply_markup=get_back_button_keyboard(), parse_mode="Markdown")
        
    elif callback_data == "docker_list":
        # Mostra la lista dei container Docker
        # Simuliamo il comando /docker con pagina 0
        command_docker(query, context, page=0)
    
    elif callback_data.startswith("docker_page_"):
        # Gestisci la paginazione dei container Docker
        if callback_data == "docker_page_info":
            # Non fare nulla se l'utente clicca sul numero di pagina
            pass
        else:
            # Estrai il numero di pagina dal callback_data
            try:
                page = int(callback_data.split("_")[-1])
                command_docker(query, context, page=page)
            except ValueError:
                # In caso di errore mostra la prima pagina
                command_docker(query, context, page=0)
        
    elif callback_data == "all_resources":
        # Mostra tutte le risorse
        response = f"{get_cpu_resources()}\n\n{'-'*30}\n\n{get_ram_resources()}\n\n{'-'*30}\n\n{get_disk_info()}\n\n{'-'*30}\n\n{get_network_info()}"
        
        # Usa la funzione per ottenere il pulsante "Torna indietro"
        query.edit_message_text(text=response, reply_markup=get_back_button_keyboard(), parse_mode="Markdown")
    
    # Gestione callback per i comandi Docker
    elif callback_data.startswith("docker_"):
        handle_docker_callback(query, context, callback_data)
        
    # Gestione callback per la conferma di riavvio
    elif callback_data == "confirm_reboot":
        handle_reboot(query, context)
        
    # Gestione callback per l'annullamento di azioni
    elif callback_data == "cancel_action":
        query.edit_message_text(get_bot_translation("bot_messages.operation_cancelled"))
    
    # Gestione callback per tornare alla lista risorse
    elif callback_data == "back_to_resources":
        query.edit_message_text(
            get_bot_translation("bot_messages.choose_resource"),
            reply_markup=get_resource_keyboard()
        )
        
    # Gestione callback per l'upload di file
    elif callback_data.startswith("browse_dir_"):
        handle_browse_directory(query, context)
    elif callback_data == "upload_cancel":
        handle_upload_cancel(query, context)
    elif callback_data == "upload_restart":
        handle_upload_restart(query, context)
    elif callback_data == "upload_continue":
        handle_upload_continue(query, context)
    elif callback_data == "upload_finish":
        handle_upload_finish(query, context)
    elif callback_data == "upload_parent_dir":
        handle_navigate_to_parent(query, context)
    elif callback_data.startswith("create_folder_"):
        handle_create_folder(query, context)
    elif callback_data.startswith("select_dir_"):
        handle_select_directory(query, context)
    elif callback_data.startswith("delete_folder_"):
        handle_delete_folder_request(query, context)
    elif callback_data.startswith("confirm_delete_"):
        handle_confirm_delete_folder(query, context)
    elif callback_data.startswith("cancel_delete_"):
        handle_cancel_delete_folder(query, context)
    elif callback_data.startswith("force_delete_"):
        handle_force_delete_folder(query, context)
    
    # Gestione callback per il download di file
    elif callback_data.startswith("download_mount_"):
        handle_download_mount_selection(query, context)
    elif callback_data == "download_cancel":
        handle_download_cancel(query, context)
    elif callback_data.startswith("download_dir_"):
        handle_download_browse_directory(query, context)
    elif callback_data == "download_parent_dir":
        handle_download_navigate_to_parent(query, context)
    elif callback_data.startswith("download_file_"):
        handle_download_file(query, context)
    elif callback_data == "download_prev_page":
        handle_download_page_navigation(query, context, -1)
    elif callback_data == "download_next_page":
        handle_download_page_navigation(query, context, 1)
    elif callback_data == "download_page_info":
        pass  # Non fare nulla

def handle_download_mount_selection(query, context):
    """Gestisce la selezione del mount point per il download"""
    global DOWNLOAD_STATES
    
    # Estrai il percorso dalla query
    callback_data = query.data
    path = callback_data[len("download_mount_"):]
    
    # Identifica l'utente
    chat_id = query.message.chat_id
    
    # Inizializza o aggiorna lo stato di download
    if chat_id not in DOWNLOAD_STATES:
        DOWNLOAD_STATES[chat_id] = {
            "state": "browsing",
            "current_path": path,
            "parent_paths": [],
            "current_page": 0,
            "timestamp": time.time()
        }
    else:
        DOWNLOAD_STATES[chat_id]["current_path"] = path
        DOWNLOAD_STATES[chat_id]["parent_paths"] = []
        DOWNLOAD_STATES[chat_id]["current_page"] = 0
        DOWNLOAD_STATES[chat_id]["state"] = "browsing"
    
    # Avvia la navigazione nella directory
    show_download_directory_contents(query, context, path)

def handle_download_browse_directory(query, context):
    """Gestisce la navigazione nelle directory per il download dei file"""
    global DOWNLOAD_STATES
    
    # Estrai il percorso dalla query
    callback_data = query.data
    path = callback_data[len("download_dir_"):]
    
    # Decodi il percorso dalla cache se necessario
    path = get_cached_path(path)
    
    # Identifica l'utente
    chat_id = query.message.chat_id
    
    # Aggiorna lo stato di navigazione dell'utente
    if chat_id in DOWNLOAD_STATES:
        # Se stiamo cambiando directory, salva quella precedente per poter tornare indietro
        current_path = DOWNLOAD_STATES[chat_id].get("current_path")
        if current_path and current_path != path:
            DOWNLOAD_STATES[chat_id]["parent_paths"].append(current_path)
        
        DOWNLOAD_STATES[chat_id]["current_path"] = path
        DOWNLOAD_STATES[chat_id]["current_page"] = 0  # Reset alla prima pagina
    else:
        # Se non esiste uno stato, lo inizializziamo
        DOWNLOAD_STATES[chat_id] = {
            "state": "browsing",
            "current_path": path,
            "parent_paths": [],
            "current_page": 0,
            "timestamp": time.time()
        }
    
    # Mostra il contenuto della directory
    show_download_directory_contents(query, context, path)

def show_download_directory_contents(query, context, path, page=None):
    """Mostra il contenuto di una directory per il download"""
    try:
        # Identifica l'utente e gestisci la paginazione
        chat_id = query.message.chat_id
        
        if page is None:
            # Usa la pagina corrente dallo stato
            if chat_id in DOWNLOAD_STATES:
                page = DOWNLOAD_STATES[chat_id].get("current_page", 0)
            else:
                page = 0
        else:
            # Aggiorna la pagina nello stato
            if chat_id in DOWNLOAD_STATES:
                DOWNLOAD_STATES[chat_id]["current_page"] = page
        
        # Verifica che la directory esista
        if not os.path.isdir(path):
            query.edit_message_text(get_bot_translation("bot_messages.download.path_not_found", path=path))
            return
        
        # Elenca i file e le directory nel percorso
        items = os.listdir(path)
        
        # Filtra e ordina gli elementi
        directories = []
        files = []
        
        for item in items:
            item_path = os.path.join(path, item)
            try:
                if os.path.isdir(item_path):
                    directories.append(item)
                elif os.path.isfile(item_path):
                    # Aggiungi tutti i file, controlleremo il limite solo al download
                    file_size = os.path.getsize(item_path)
                    logger.info(f"File trovato: {item}, dimensione: {file_size} bytes")
                    files.append({"name": item, "size": file_size})
                    logger.info(f"File aggiunto alla lista: {item}")
            except Exception as e:
                logger.error(f"Errore accesso file {item}: {str(e)}")
                pass  # Ignora gli errori di accesso ai file
        
        # Ordina alfabeticamente
        directories.sort()
        files.sort(key=lambda x: x["name"])
        
        # Paginazione - elementi per pagina
        items_per_page = 15
        total_items = len(directories) + len(files)
        total_pages = max(1, (total_items + items_per_page - 1) // items_per_page)
        
        # Calcola gli indici per la pagina corrente
        start_idx = page * items_per_page
        end_idx = start_idx + items_per_page
        
        # Combina directories e files per la paginazione
        all_items = []
        for directory in directories:
            all_items.append({"type": "dir", "name": directory})
        for file_info in files:
            all_items.append({"type": "file", "info": file_info})
        
        # Prendi solo gli elementi per questa pagina
        page_items = all_items[start_idx:end_idx]
        
        # Costruisci la tastiera
        keyboard = []
        
        # Aggiungi pulsante per tornare alla directory superiore se possibile
        if chat_id in DOWNLOAD_STATES and DOWNLOAD_STATES[chat_id]["parent_paths"]:
            keyboard.append([
                InlineKeyboardButton(get_bot_translation("bot_messages.download.parent_directory"), callback_data="download_parent_dir")
            ])
        
        # Aggiungi gli elementi della pagina corrente
        for item in page_items:
            if item["type"] == "dir":
                directory = item["name"]
                full_path = os.path.join(path, directory)
                cached_path = cache_path(full_path)
                keyboard.append([
                    InlineKeyboardButton(f"📂 {directory}", callback_data=f"download_dir_{cached_path}")
                ])
            else:
                file_info = item["info"]
                file_name = file_info["name"]
                file_size = file_info["size"]
                size_str = format_file_size(file_size)
                full_path = os.path.join(path, file_name)
                cached_path = cache_path(full_path)
                
                # Indica se il file è troppo grande per Telegram
                if file_size > 50 * 1024 * 1024:  # 50MB
                    button_text = f"📄 {file_name} ({size_str}) ⚠️"
                else:
                    button_text = f"📄 {file_name} ({size_str})"
                    
                keyboard.append([
                    InlineKeyboardButton(button_text, callback_data=f"download_file_{cached_path}")
                ])
        
        # Aggiungi controlli di paginazione se necessario
        if total_pages > 1:
            pagination_row = []
            
            # Pulsante pagina precedente
            if page > 0:
                pagination_row.append(InlineKeyboardButton("⬅️", callback_data=f"download_prev_page"))
            
            # Indicatore pagina corrente
            pagination_row.append(InlineKeyboardButton(f"{page + 1}/{total_pages}", callback_data="download_page_info"))
            
            # Pulsante pagina successiva
            if page < total_pages - 1:
                pagination_row.append(InlineKeyboardButton("➡️", callback_data=f"download_next_page"))
            
            keyboard.append(pagination_row)
        
        # Aggiungi pulsante di annullamento
        keyboard.append([
            InlineKeyboardButton(get_bot_translation("bot_messages.download.cancel"), callback_data="download_cancel")
        ])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # Prepara il messaggio
        message = f"{get_bot_translation('bot_messages.download.navigation_title')}\n\n"
        message += f"{get_bot_translation('bot_messages.download.current_path')}: `{path}`\n\n"
        
        # Informazioni sul contenuto
        message += f"{get_bot_translation('bot_messages.download.subfolders')}: {len(directories)}\n"
        message += f"{get_bot_translation('bot_messages.download.files')}: {len(files)}\n"
        
        # Informazioni paginazione
        if total_pages > 1:
            message += get_bot_translation("bot_messages.download.pagination_info", 
                                         current=page + 1, 
                                         total=total_pages, 
                                         shown=len(page_items), 
                                         total_items=total_items) + "\n"
        
        message += "\n"
        
        # Aggiungi istruzioni
        if len(files) == 0 and len(directories) == 0:
            message += "⚠️ Questa directory è vuota.\n\n"
        elif len(files) == 0:
            message += "⚠️ Nessun file scaricabile trovato in questa directory (solo cartelle).\n\n"
        
        # Conta i file troppo grandi
        large_files = sum(1 for f in files if f["size"] > 50 * 1024 * 1024)
        if large_files > 0:
            message += get_bot_translation("bot_messages.download.large_files_warning", count=large_files) + "\n\n"
        
        message += get_bot_translation('bot_messages.download.navigation_instruction')
        
        # Aggiorna il messaggio
        query.edit_message_text(
            text=message,
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )
        
    except Exception as e:
        logger.error(f"Errore durante la navigazione nella directory per download: {str(e)}")
        query.edit_message_text(f"⚠️ Errore durante la navigazione: {str(e)}")

def handle_download_navigate_to_parent(query, context):
    """Gestisce la navigazione alla directory superiore per il download"""
    global DOWNLOAD_STATES
    
    # Identifica l'utente
    chat_id = query.message.chat_id
    
    # Verifica che l'utente abbia uno stato valido
    if chat_id not in DOWNLOAD_STATES or not DOWNLOAD_STATES[chat_id]["parent_paths"]:
        query.edit_message_text("⚠️ Non è possibile tornare indietro.")
        return
    
    # Prendi l'ultima directory dalla cronologia
    parent_path = DOWNLOAD_STATES[chat_id]["parent_paths"].pop()
    
    # Aggiorna il percorso corrente
    DOWNLOAD_STATES[chat_id]["current_path"] = parent_path
    
    # Mostra il contenuto della directory parent
    show_download_directory_contents(query, context, parent_path)

def handle_download_file(query, context):
    """Gestisce il download di un file"""
    global DOWNLOAD_STATES
    
    # Estrai il percorso del file dalla query
    callback_data = query.data
    file_path = callback_data[len("download_file_"):]
    
    # Decodi il percorso dalla cache se necessario
    file_path = get_cached_path(file_path)
    
    # Identifica l'utente
    chat_id = query.message.chat_id
    
    try:
        # Verifica che il file esista
        if not os.path.isfile(file_path):
            query.edit_message_text(get_bot_translation("bot_messages.download.file_not_found"))
            return
        
        # Verifica la dimensione del file
        file_size = os.path.getsize(file_path)
        file_name = os.path.basename(file_path)
        if file_size > 50 * 1024 * 1024:  # 50MB
            size_str = format_file_size(file_size)
            query.edit_message_text(get_bot_translation("bot_messages.download.file_too_large", filename=file_name, size=size_str))
            return
        
        # Invia il file
        file_name = os.path.basename(file_path)
        
        # Prima aggiorna il messaggio per indicare che stiamo inviando il file
        query.edit_message_text(get_bot_translation("bot_messages.download.sending_file", filename=file_name))
        
        # Invia il file
        with open(file_path, 'rb') as file:
            context.bot.send_document(
                chat_id=chat_id,
                document=file,
                filename=file_name,
                caption=get_bot_translation("bot_messages.download.file_sent", filename=file_name, size=format_file_size(file_size))
            )
        
        # Pulizia dello stato download per questo utente
        if chat_id in DOWNLOAD_STATES:
            del DOWNLOAD_STATES[chat_id]
            
    except Exception as e:
        logger.error(f"Errore durante il download del file: {str(e)}")
        query.edit_message_text(get_bot_translation("bot_messages.download.error", error=str(e)))

def handle_download_cancel(query, context):
    """Gestisce l'annullamento del download"""
    global DOWNLOAD_STATES
    
    # Identifica l'utente
    chat_id = query.message.chat_id
    
    # Pulisci lo stato download per questo utente
    if chat_id in DOWNLOAD_STATES:
        del DOWNLOAD_STATES[chat_id]
    
    query.edit_message_text(get_bot_translation("bot_messages.download.cancelled"))

def handle_download_page_navigation(query, context, direction):
    """Gestisce la navigazione tra pagine per il download"""
    global DOWNLOAD_STATES
    
    # Identifica l'utente
    chat_id = query.message.chat_id
    
    if chat_id not in DOWNLOAD_STATES:
        query.edit_message_text("⚠️ Sessione di download scaduta.")
        return
    
    # Ottieni lo stato corrente
    current_path = DOWNLOAD_STATES[chat_id]["current_path"]
    current_page = DOWNLOAD_STATES[chat_id].get("current_page", 0)
    
    # Calcola la nuova pagina
    new_page = max(0, current_page + direction)
    
    # Aggiorna lo stato
    DOWNLOAD_STATES[chat_id]["current_page"] = new_page
    
    # Mostra il contenuto della directory con la nuova pagina
    show_download_directory_contents(query, context, current_path, new_page)

def format_file_size(size_bytes):
    """Formatta la dimensione del file in formato leggibile"""
    if size_bytes == 0:
        return "0B"
    
    size_names = ["B", "KB", "MB", "GB"]
    i = 0
    while size_bytes >= 1024 and i < len(size_names) - 1:
        size_bytes /= 1024.0
        i += 1
    
    return f"{size_bytes:.1f}{size_names[i]}"

def handle_docker_callback(query, context, callback_data):
    """Gestisce i callback relativi ai comandi Docker"""
    try:
        # Estrai il nome del container e l'azione dal callback data
        if callback_data.startswith("docker_start_"):
            container_name = callback_data[len("docker_start_"):]
            action = "start"
        elif callback_data.startswith("docker_stop_"):
            container_name = callback_data[len("docker_stop_"):]
            action = "stop"
        elif callback_data.startswith("docker_restart_"):
            container_name = callback_data[len("docker_restart_"):]
            action = "restart"
        elif callback_data.startswith("docker_pause_"):
            container_name = callback_data[len("docker_pause_"):]
            action = "pause"
        elif callback_data.startswith("docker_"):
            container_name = callback_data[len("docker_"):]
            action = "inspect"
        else:
            query.edit_message_text(get_bot_translation("bot_messages.docker_details.unrecognized_command"))
            return
        
        if action == "inspect":
            # Mostra informazioni dettagliate sul container
            result = subprocess.run(['docker', 'inspect', container_name], capture_output=True, text=True)
            
            if result.returncode != 0:
                error_msg = get_bot_translation("bot_messages.docker_details.error_inspect")
                query.edit_message_text(f"{error_msg} {container_name}:\n{result.stderr}")
                return
            
            # Analizziamo i dati JSON per estrarre le informazioni principali
            container_info = json.loads(result.stdout)[0]
            
            # Estrai informazioni utili
            state = container_info.get('State', {})
            config = container_info.get('Config', {})
            network = container_info.get('NetworkSettings', {})
            
            # Costruisci il messaggio
            container_label = get_bot_translation("bot_messages.docker_details.container")
            message = f"📊 *{container_label}: {container_name}*\n"
            message += f"{'='*30}\n\n"
            
            # Stato
            status = state.get('Status', get_bot_translation("bot_messages.docker_details.unknown"))
            running = state.get('Running', False)
            
            status_label = get_bot_translation("bot_messages.docker_details.status")
            status_text = get_bot_translation("bot_messages.docker_details.status_running") if running else get_bot_translation("bot_messages.docker_details.status_stopped")
            message += f"*{status_label}:* {status_text}\n"
            message += f"*Status:* {status}\n"
            
            # Uptime
            if running:
                started_at = state.get('StartedAt', '')
                if started_at:
                    try:
                        # Rimuovi i nanosecondi per evitare errori di parsing
                        if '.' in started_at:
                            # Estrai solo fino ai millisecondi (3 cifre dopo il punto)
                            timestamp_parts = started_at.split('.')
                            if len(timestamp_parts) > 1:
                                milliseconds = timestamp_parts[1]
                                # Estrai solo la parte di millisecondi prima del fuso orario
                                if '+' in milliseconds:
                                    timezone_parts = milliseconds.split('+')
                                    milliseconds = timezone_parts[0][:3]  # Prendi solo i primi 3 caratteri
                                    timezone = '+' + timezone_parts[1]
                                    started_at = f"{timestamp_parts[0]}.{milliseconds}+{timezone}"
                                elif '-' in milliseconds:
                                    timezone_parts = milliseconds.split('-')
                                    milliseconds = timezone_parts[0][:3]
                                    timezone = '-' + timezone_parts[1]
                                    started_at = f"{timestamp_parts[0]}.{milliseconds}-{timezone}"
                        
                        # Gestisci i formati comuni
                        if 'Z' in started_at:
                            started_at = started_at.replace('Z', '+00:00')
                        
                        # Usa strptime per maggiore compatibilità
                        from datetime import datetime
                        start_time = datetime.strptime(started_at.split('.')[0], "%Y-%m-%dT%H:%M:%S")
                        uptime = datetime.now() - start_time
                        days, seconds = uptime.days, uptime.seconds
                        hours, remainder = divmod(seconds, 3600)
                        minutes, seconds = divmod(remainder, 60)
                        
                        uptime_str = ""
                        if days > 0:
                            uptime_str += f"{days}d "
                        uptime_str += f"{hours}h {minutes}m {seconds}s"
                        
                        uptime_label = get_bot_translation("bot_messages.docker_details.uptime")
                        message += f"{uptime_label}: {uptime_str}\n"
                    except Exception as e:
                        logger.error(f"Errore nel calcolo dell'uptime: {e}")
            
            # Immagine
            image = config.get('Image', get_bot_translation("bot_messages.docker_details.unknown_image"))
            image_label = get_bot_translation("bot_messages.docker_details.image")
            message += f"{image_label}: `{image}`\n"
            
            # Aggiungi informazioni su CPU e memoria
            try:
                # Ottieni stats del container
                stats_cmd = ['docker', 'stats', '--no-stream', '--format', '{{.CPUPerc}}|{{.MemUsage}}|{{.MemPerc}}', container_name]
                stats_result = subprocess.run(stats_cmd, capture_output=True, text=True)
                
                if stats_result.returncode == 0 and stats_result.stdout.strip():
                    # Formato: CPUPerc|MemUsage|MemPerc
                    stats = stats_result.stdout.strip().split('|')
                    if len(stats) >= 3:
                        cpu_usage = stats[0].strip()
                        mem_usage = stats[1].strip()
                        mem_perc = stats[2].strip()
                        
                        resources_label = get_bot_translation("bot_messages.docker_details.resources")
                        cpu_label = get_bot_translation("bot_messages.docker_details.cpu")
                        memory_label = get_bot_translation("bot_messages.docker_details.memory")
                        message += f"\n{resources_label}\n"
                        message += f"{'_'*20}\n"
                        message += f"{cpu_label}: {cpu_usage}\n"
                        message += f"{memory_label}: {mem_usage} ({mem_perc})\n"
            except Exception as e:
                logger.error(f"Errore nel recupero delle statistiche del container: {str(e)}")
            
            # Porte esposte
            ports = network.get('Ports', {})
            if ports:
                ports_label = get_bot_translation("bot_messages.docker_details.ports")
                port_mapped_icon = get_bot_translation("bot_messages.docker_details.port_mapped")
                port_unmapped_icon = get_bot_translation("bot_messages.docker_details.port_unmapped")
                port_unmapped_text = get_bot_translation("bot_messages.docker_details.port_unmapped_text")
                message += f"\n{ports_label}\n"
                message += f"{'_'*20}\n"
                for port, bindings in ports.items():
                    if bindings:
                        for binding in bindings:
                            host_ip = binding.get('HostIp', '0.0.0.0')
                            host_port = binding.get('HostPort', 'N/A')
                            message += f"  {port_mapped_icon} {port} → {host_ip}:{host_port}\n"
                    else:
                        message += f"  {port_unmapped_icon} {port} {port_unmapped_text}\n"
            
            # Volumi
            mounts = container_info.get('Mounts', [])
            if mounts:
                volumes_label = get_bot_translation("bot_messages.docker_details.volumes")
                message += f"\n{volumes_label}\n"
                message += f"{'_'*20}\n"
                for mount in mounts:
                    src = mount.get('Source', 'N/A')
                    dst = mount.get('Destination', 'N/A')
                    mode = mount.get('Mode', 'rw')
                    message += f"  {'📥' if mode == 'ro' else '📤'} {src}\n    ↳ {dst} ({mode})\n"
            
            # Variabili d'ambiente
            env = config.get('Env', [])
            if env and len(env) > 0:
                config_label = get_bot_translation("bot_messages.docker_details.configuration")
                env_vars_label = get_bot_translation("bot_messages.docker_details.env_vars")
                env_vars_count = get_bot_translation("bot_messages.docker_details.env_vars_count")
                message += f"\n{config_label}\n"
                message += f"{'_'*20}\n"
                message += f"{env_vars_label}: {len(env)} {env_vars_count}\n"
            
            # Crea i pulsanti per le azioni
            keyboard = []
            
            # Azioni diverse in base allo stato
            if running:
                stop_label = get_bot_translation("bot_messages.docker_details.actions.stop")
                pause_label = get_bot_translation("bot_messages.docker_details.actions.pause")
                restart_label = get_bot_translation("bot_messages.docker_details.actions.restart")
                keyboard.append([
                    InlineKeyboardButton(stop_label, callback_data=f"docker_stop_{container_name}"),
                    InlineKeyboardButton(pause_label, callback_data=f"docker_pause_{container_name}"),
                    InlineKeyboardButton(restart_label, callback_data=f"docker_restart_{container_name}")
                ])
            else:
                start_label = get_bot_translation("bot_messages.docker_details.actions.start")
                keyboard.append([
                    InlineKeyboardButton(start_label, callback_data=f"docker_start_{container_name}")
                ])
            
            # Aggiungi pulsante per tornare alla lista
            back_label = get_bot_translation("bot_messages.back_to_list")
            keyboard.append([InlineKeyboardButton(back_label, callback_data="docker_list")])
            
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            # Limita la lunghezza del messaggio e assicurati che i caratteri Markdown siano bilanciati
            if len(message) > 3000:
                message = message[:2997] + "..."
            
            # Assicurati che tutti i tag Markdown siano bilanciati
            # (Questo è un controllo di base, ma potrebbe non catturare tutti i problemi)
            asterisk_count = message.count('*')
            if asterisk_count % 2 != 0:
                message += "*"  # Aggiungi un asterisco per bilanciare
                
            backtick_count = message.count('`')
            if backtick_count % 2 != 0:
                message += "`"  # Aggiungi un backtick per bilanciare
            
            try:
                # Invia il messaggio
                query.edit_message_text(text=message, reply_markup=reply_markup, parse_mode="Markdown")
            except Exception as e:
                # Se fallisce, prova senza parse_mode
                logger.error(f"Errore nell'invio del messaggio formattato: {str(e)}")
                # Rimuovi i caratteri Markdown per sicurezza
                clean_message = message.replace('*', '').replace('_', '').replace('`', '').replace('[', '').replace(']', '')
                query.edit_message_text(text=clean_message, reply_markup=reply_markup)
            
        else:
            # Esegui l'azione sul container
            # Prima mostra un messaggio di attesa
            query.edit_message_text(f"⏳ Esecuzione comando '{action}' sul container {container_name}...")
            
            # Esegui il comando
            result = subprocess.run(['docker', action, container_name], capture_output=True, text=True)
            
            # Verifica il risultato
            if result.returncode == 0:
                # Formatta il messaggio di stato
                action_past = {
                    "start": "avviato",
                    "stop": "fermato",
                    "restart": "riavviato",
                    "pause": "messo in pausa"
                }.get(action, action)
                
                success_message = f"✅ Container {container_name} {action_past} con successo."
                
                # Aggiungi pulsanti per navigare
                keyboard = [
                    [InlineKeyboardButton(get_bot_translation("bot_messages.back_to_container_list"), callback_data="docker_list")],
                    [InlineKeyboardButton(get_bot_translation("bot_messages.back_to_resources"), callback_data="back_to_resources")]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                query.edit_message_text(text=success_message, reply_markup=reply_markup)
            else:
                # Mostra l'errore
                error_message = f"⚠️ Errore durante l'esecuzione del comando '{action}' sul container {container_name}:\n{result.stderr}"
                
                # Aggiungi pulsanti per navigare
                keyboard = [
                    [InlineKeyboardButton(get_bot_translation("bot_messages.back_to_container_list"), callback_data="docker_list")],
                    [InlineKeyboardButton(get_bot_translation("bot_messages.back_to_resources"), callback_data="back_to_resources")]
                ]
                reply_markup = InlineKeyboardMarkup(keyboard)
                
                query.edit_message_text(text=error_message, reply_markup=reply_markup)
                
    except Exception as e:
        logger.error(f"Errore nella gestione del callback Docker: {e}")
        query.edit_message_text(f"Errore durante l'esecuzione del comando Docker: {str(e)}")

def handle_reboot(query, context):
    """Gestisce il riavvio del server"""
    try:
        # Informa l'utente che il riavvio è in corso
        message = get_bot_translation("bot_messages.reboot_in_progress")
        query.edit_message_text(
            message,
            parse_mode="Markdown"
        )
        
        # Registra l'evento nel log
        logger.warning(f"Riavvio del server richiesto dall'utente {query.from_user.id}")
        
        # Esegui il comando di riavvio
        # Usiamo un thread separato per evitare di bloccare il bot
        def reboot_system():
            try:
                time.sleep(2)  # Piccolo ritardo per assicurarsi che il messaggio venga inviato
                result = run_host_command("reboot")
                if not result:
                    logger.error("Errore nell'esecuzione del comando di riavvio")
            except Exception as e:
                logger.error(f"Errore durante il riavvio: {str(e)}")
        
        # Avvia il thread per il riavvio
        threading.Thread(target=reboot_system).start()
        
    except Exception as e:
        logger.error(f"Errore durante il tentativo di riavvio: {str(e)}")
        query.edit_message_text(f"⚠️ Errore durante il tentativo di riavvio: {str(e)}")

def handle_browse_directory(query, context):
    """Gestisce la navigazione nelle directory per l'upload dei file"""
    global UPLOAD_STATES
    
    # Estrai il percorso dalla query
    callback_data = query.data
    path = callback_data[len("browse_dir_"):]
    
    # Decodi il percorso dalla cache se necessario
    path = get_cached_path(path)
    
    # Identifica l'utente
    chat_id = query.message.chat_id
    
    # Aggiorna lo stato di navigazione dell'utente
    if chat_id in UPLOAD_STATES:
        # Se stiamo cambiando directory, salva quella precedente per poter tornare indietro
        current_path = UPLOAD_STATES[chat_id].get("current_path")
        if current_path and current_path != path:
            UPLOAD_STATES[chat_id]["parent_paths"].append(current_path)
        
        UPLOAD_STATES[chat_id]["current_path"] = path
    else:
        # Se non esiste uno stato, lo inizializziamo
        UPLOAD_STATES[chat_id] = {
            "state": "selecting_directory",
            "dir": None,
            "current_path": path,
            "parent_paths": []
        }
    
    try:
        # Verifica che la directory esista
        if not os.path.isdir(path):
            query.edit_message_text(get_bot_translation("bot_messages.upload.path_not_found", path=path))
            return
        
        # Elenca i file e le directory nel percorso
        items = os.listdir(path)
        
        # Filtra e ordina gli elementi
        directories = []
        files = []
        
        for item in items:
            item_path = os.path.join(path, item)
            try:
                if os.path.isdir(item_path):
                    directories.append(item)
                else:
                    files.append(item)
            except:
                pass  # Ignora gli errori di accesso ai file
        
        # Ordina alfabeticamente
        directories.sort()
        files.sort()
        
        # Costruisci la tastiera
        keyboard = []
        
        # Aggiungi un pulsante per selezionare la directory corrente
        keyboard.append([
            InlineKeyboardButton(get_bot_translation("bot_messages.upload.select_folder"), callback_data=f"select_dir_{path}")
        ])
        
        # Aggiungi pulsante per creare una nuova cartella
        keyboard.append([
            InlineKeyboardButton(get_bot_translation("bot_messages.upload.create_folder"), callback_data=f"create_folder_{path}")
        ])
        
        # Aggiungi pulsante per eliminare la cartella corrente (solo se non è un punto di mount)
        if UPLOAD_STATES[chat_id]["parent_paths"]:  # Solo se non siamo nella root
            keyboard.append([
                InlineKeyboardButton(get_bot_translation("bot_messages.upload.delete_folder"), callback_data=f"delete_folder_{path}")
            ])
        
        # Aggiungi pulsante per tornare alla directory superiore se possibile
        if UPLOAD_STATES[chat_id]["parent_paths"]:
            keyboard.append([
                InlineKeyboardButton(get_bot_translation("bot_messages.upload.parent_directory"), callback_data="upload_parent_dir")
            ])
        
        # Aggiungi le directory
        for directory in directories:
            full_path = os.path.join(path, directory)
            cached_path = cache_path(full_path)
            keyboard.append([
                InlineKeyboardButton(f"📂 {directory}", callback_data=f"browse_dir_{cached_path}")
            ])
        
        # Aggiungi pulsante di annullamento
        keyboard.append([
            InlineKeyboardButton(get_bot_translation("bot_messages.upload.cancel"), callback_data="upload_cancel")
        ])
        
        reply_markup = InlineKeyboardMarkup(keyboard)
        
        # Prepara il messaggio
        message = f"{get_bot_translation('bot_messages.upload.navigation_title')}\n\n"
        message += f"{get_bot_translation('bot_messages.upload.current_path')}: `{path}`\n\n"
        
        # Informazioni sul contenuto
        message += f"{get_bot_translation('bot_messages.upload.subfolders')}: {len(directories)}\n"
        message += f"{get_bot_translation('bot_messages.upload.files')}: {len(files)}\n\n"
        
        # Aggiungi istruzioni
        message += get_bot_translation('bot_messages.upload.navigation_instruction')
        
        # Aggiorna il messaggio
        query.edit_message_text(
            text=message,
            reply_markup=reply_markup,
            parse_mode="Markdown"
        )
        
    except Exception as e:
        logger.error(f"Errore durante la navigazione nella directory: {str(e)}")
        query.edit_message_text(f"⚠️ Errore durante la navigazione: {str(e)}")
        
def handle_navigate_to_parent(query, context):
    """Gestisce la navigazione alla directory superiore"""
    global UPLOAD_STATES
    
    # Identifica l'utente
    chat_id = query.message.chat_id
    
    # Verifica che l'utente abbia uno stato valido
    if chat_id not in UPLOAD_STATES or not UPLOAD_STATES[chat_id]["parent_paths"]:
        query.edit_message_text("⚠️ Non è possibile tornare indietro.")
        return
    
    # Prendi l'ultima directory dalla cronologia
    parent_path = UPLOAD_STATES[chat_id]["parent_paths"].pop()
    
    # Crea un nuovo callback_data per navigare a quella directory
    callback_data = f"browse_dir_{parent_path}"
    
    # Modifica la query e richiama la funzione di navigazione
    query.data = callback_data
    handle_browse_directory(query, context)

def handle_select_directory(query, context):
    """Gestisce la selezione di una directory per l'upload"""
    global UPLOAD_STATES
    
    # Estrai il percorso dalla query
    callback_data = query.data
    path = callback_data[len("select_dir_"):]
    
    # Decodi il percorso dalla cache se necessario
    path = get_cached_path(path)
    
    # Identifica l'utente
    chat_id = query.message.chat_id
    
    # Verifica che lo stato di upload sia valido
    if chat_id not in UPLOAD_STATES:
        query.edit_message_text("⚠️ Sessione di upload non valida. Usa /upload per ricominciare.")
        return
    
    # Verifica che la directory esista
    if not os.path.isdir(path):
        query.edit_message_text(get_bot_translation("bot_messages.upload.path_not_found", path=path))
        return
    
    # Aggiorna lo stato di upload con la directory selezionata
    UPLOAD_STATES[chat_id]["state"] = "uploading"
    UPLOAD_STATES[chat_id]["dir"] = path
    
    # Informa l'utente che può iniziare a caricare i file
    query.edit_message_text(
        get_bot_translation("bot_messages.upload.folder_selected", path=path),
        parse_mode="Markdown"
    )

def handle_delete_folder_request(query, context):
    """Gestisce la richiesta di eliminazione di una cartella"""
    # Estrai il percorso dalla query
    callback_data = query.data
    path = callback_data[len("delete_folder_"):]
    
    # Decodi il percorso dalla cache se necessario
    path = get_cached_path(path)
    
    # Verifica che la directory esista
    if not os.path.isdir(path):
        query.edit_message_text(get_bot_translation("bot_messages.upload.path_not_found", path=path))
        return
    
    # Ottieni nome della cartella per mostrarlo nel messaggio
    folder_name = os.path.basename(path)
    parent_dir = os.path.dirname(path)
    
    # Crea la tastiera di conferma
    keyboard = [
        [
            InlineKeyboardButton(get_bot_translation("bot_messages.upload.confirm_delete"), callback_data=f"confirm_delete_{path}"),
            InlineKeyboardButton(get_bot_translation("bot_messages.upload.cancel_delete"), callback_data=f"cancel_delete_{path}")
        ]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    # Chiedi conferma all'utente
    query.edit_message_text(
        get_bot_translation("bot_messages.upload.delete_confirmation", folder_name=folder_name, path=path),
        reply_markup=reply_markup,
        parse_mode="Markdown"
    )

def handle_confirm_delete_folder(query, context):
    """Gestisce la conferma di eliminazione di una cartella"""
    global UPLOAD_STATES
    
    # Estrai il percorso dalla query
    callback_data = query.data
    path = callback_data[len("confirm_delete_"):]
    
    # Decodi il percorso dalla cache se necessario
    path = get_cached_path(path)
    
    # Identifica l'utente
    chat_id = query.message.chat_id
    
    # Ottieni il percorso padre per tornare indietro dopo l'eliminazione
    parent_path = os.path.dirname(path)
    
    try:
        # Verifica che la directory esista
        if not os.path.isdir(path):
            query.edit_message_text(get_bot_translation("bot_messages.upload.path_not_found", path=path))
            return
        
        # Controlla che la directory sia vuota
        if os.listdir(path):
            # Se non è vuota, chiedi ulteriore conferma
            folder_name = os.path.basename(path)
            keyboard = [
                [
                    InlineKeyboardButton(get_bot_translation("bot_messages.upload.confirm_force_delete"), callback_data=f"force_delete_{path}"),
                    InlineKeyboardButton(get_bot_translation("bot_messages.upload.cancel_delete"), callback_data=f"cancel_delete_{path}")
                ]
            ]
            reply_markup = InlineKeyboardMarkup(keyboard)
            
            query.edit_message_text(
                get_bot_translation("bot_messages.upload.delete_non_empty", folder_name=folder_name),
                reply_markup=reply_markup,
                parse_mode="Markdown"
            )
            return
        
        # Elimina la directory
        os.rmdir(path)
        
        # Mostra messaggio di successo e poi torna alla navigazione
        success_message = get_bot_translation("bot_messages.upload.folder_deleted_success")
        query.edit_message_text(success_message)
        
        # Torna alla directory padre dopo una breve pausa
        time.sleep(1)
        
        # Aggiorna lo stato di navigazione
        if chat_id in UPLOAD_STATES:
            # Resetta le parent_paths per fare in modo che torni alla directory padre
            UPLOAD_STATES[chat_id]["current_path"] = parent_path
            UPLOAD_STATES[chat_id]["parent_paths"] = []
        
        # Crea un nuovo callback_data per la navigazione
        new_callback_data = f"browse_dir_{parent_path}"
        query.data = new_callback_data
        handle_browse_directory(query, context)
        
    except Exception as e:
        query.edit_message_text(f"⚠️ Errore durante l'eliminazione della cartella: {str(e)}")

def handle_cancel_delete_folder(query, context):
    """Gestisce l'annullamento dell'eliminazione di una cartella"""
    # Estrai il percorso dalla query
    callback_data = query.data
    path = callback_data[len("cancel_delete_"):]
    
    # Decodi il percorso dalla cache se necessario
    path = get_cached_path(path)
    
    # Torna alla navigazione della directory
    query.data = f"browse_dir_{path}"
    handle_browse_directory(query, context)

def handle_force_delete_folder(query, context):
    """Gestisce l'eliminazione forzata di una cartella non vuota"""
    global UPLOAD_STATES
    
    # Estrai il percorso dalla query
    callback_data = query.data
    path = callback_data[len("force_delete_"):]
    
    # Decodi il percorso dalla cache se necessario
    path = get_cached_path(path)
    
    # Identifica l'utente
    chat_id = query.message.chat_id
    
    # Ottieni il percorso padre per tornare indietro dopo l'eliminazione
    parent_path = os.path.dirname(path)
    
    try:
        # Verifica che la directory esista
        if not os.path.isdir(path):
            query.edit_message_text(get_bot_translation("bot_messages.upload.path_not_found", path=path))
            return
        
        # Elimina ricorsivamente la directory e tutto il suo contenuto
        import shutil
        shutil.rmtree(path)
        
        # Mostra messaggio di successo e poi torna alla navigazione
        success_message = get_bot_translation("bot_messages.upload.folder_force_deleted_success")
        query.edit_message_text(success_message)
        
        # Torna alla directory padre dopo una breve pausa
        time.sleep(1)
        
        # Aggiorna lo stato di navigazione
        if chat_id in UPLOAD_STATES:
            # Resetta le parent_paths per fare in modo che torni alla directory padre
            UPLOAD_STATES[chat_id]["current_path"] = parent_path
            UPLOAD_STATES[chat_id]["parent_paths"] = []
        
        # Crea un nuovo callback_data per la navigazione
        new_callback_data = f"browse_dir_{parent_path}"
        query.data = new_callback_data
        handle_browse_directory(query, context)
        
    except Exception as e:
        query.edit_message_text(f"⚠️ Errore durante l'eliminazione della cartella: {str(e)}")

def handle_create_folder(query, context):
    """Gestisce la creazione di una nuova cartella"""
    global FOLDER_CREATION_STATES
    
    # Estrai il percorso dalla query
    callback_data = query.data
    path = callback_data[len("create_folder_"):]
    
    # Decodi il percorso dalla cache se necessario
    path = get_cached_path(path)
    
    # Identifica l'utente
    chat_id = query.message.chat_id
    
    # Aggiorna lo stato di creazione cartella
    FOLDER_CREATION_STATES[chat_id] = {
        "parent_path": path,
        "message_id": query.message.message_id
    }
    
    # Informa l'utente di inserire il nome della cartella
    query.edit_message_text(
        get_bot_translation("bot_messages.upload.creating_folder", path=path),
        parse_mode="Markdown"
    )

def handle_upload_cancel(query, context):
    """Gestisce l'annullamento dell'upload"""
    global UPLOAD_STATES
    
    # Identifica l'utente
    chat_id = query.message.chat_id
    
    # Rimuovi lo stato di upload
    if chat_id in UPLOAD_STATES:
        del UPLOAD_STATES[chat_id]
    
    # Informa l'utente
    query.edit_message_text(get_bot_translation("bot_messages.upload.operation_cancelled"))

def handle_upload_restart(query, context):
    """Gestisce il riavvio dell'upload con una nuova directory"""
    # Simula il comando /upload
    query.message.reply_text("Ricominciamo. Seleziona una directory per l'upload.")
    command_upload(query, context)

def handle_upload_continue(query, context):
    """Continua l'upload con la stessa directory"""
    # Identifica l'utente
    chat_id = query.message.chat_id
    
    # Verifica che lo stato di upload sia valido
    if chat_id in UPLOAD_STATES and UPLOAD_STATES[chat_id]["state"] == "uploading":
        dir_path = UPLOAD_STATES[chat_id]["dir"]
        query.edit_message_text(
            get_bot_translation("bot_messages.upload.folder_selected", path=dir_path),
            parse_mode="Markdown"
        )
    else:
        query.edit_message_text("⚠️ Sessione di upload non valida. Usa /upload per ricominciare.")

def handle_upload_finish(query, context):
    """Termina l'upload"""
    global UPLOAD_STATES
    
    # Identifica l'utente
    chat_id = query.message.chat_id
    
    # Rimuovi lo stato di upload
    if chat_id in UPLOAD_STATES:
        dir_path = UPLOAD_STATES[chat_id]["dir"]
        del UPLOAD_STATES[chat_id]
        query.edit_message_text(
            get_bot_translation("bot_messages.upload.upload_completed", directory=dir_path),
            parse_mode="Markdown"
        )
    else:
        query.edit_message_text("⚠️ Sessione di upload non valida.")

def send_telegram_message(message, parse_mode="Markdown", chat_id=None):
    """Invia un messaggio tramite il bot Telegram"""
    global BOT_INSTANCE, CHAT_ID
    
    # Usa il chat_id fornito o quello globale
    target_chat_id = chat_id or CHAT_ID
    
    if not BOT_INSTANCE or not target_chat_id:
        logger.error("Bot Telegram non inizializzato o chat_id non impostato")
        return False
    
    try:
        # Limita la lunghezza del messaggio a 4096 caratteri
        if len(message) > 4096:
            message = message[:4093] + "..."
        
        BOT_INSTANCE.send_message(chat_id=target_chat_id, text=message, parse_mode=parse_mode)
        return True
    except Exception as e:
        logger.error(f"Errore nell'invio del messaggio Telegram: {e}")
        return False

def get_file_browser_keyboard(directory, file_list=None):
    """Crea una tastiera per la navigazione dei file"""
    keyboard = []
    
    # Aggiungi navigazione alla directory superiore se applicabile
    parent_dir = os.path.dirname(directory)
    if parent_dir and parent_dir != directory:
        keyboard.append([InlineKeyboardButton(get_bot_translation("bot_messages.upload.parent_directory"), callback_data=f"browse_dir_{parent_dir}")])
    
    # Aggiungi le sottodirectory
    try:
        items = file_list or os.listdir(directory)
        dirs = [item for item in items if os.path.isdir(os.path.join(directory, item))]
        dirs.sort()
        
        for dir_name in dirs:
            full_path = os.path.join(directory, dir_name)
            # Cache il percorso se è troppo lungo per il callback_data
            cached_path = cache_path(full_path)
            keyboard.append([InlineKeyboardButton(f"📂 {dir_name}", callback_data=f"browse_dir_{cached_path}")])
    except Exception as e:
        logger.error(f"Errore nella lettura delle directory: {str(e)}")
    
    # Aggiungi pulsante di annullamento
    keyboard.append([InlineKeyboardButton(get_bot_translation("bot_messages.upload.cancel"), callback_data="upload_cancel")])
    
    return InlineKeyboardMarkup(keyboard)

# ----------------------------------------
# Funzioni per l'esportazione
# ----------------------------------------

def send_notification(message, parse_mode="Markdown"):
    """Invia una notifica tramite il bot Telegram"""
    return send_telegram_message(message, parse_mode)

# Thread per il bot Telegram
BOT_THREAD = None

def start_bot_thread(token=None, chat_id=None):
    """Avvia il bot Telegram in un thread separato"""
    global BOT_THREAD, UPDATER
    
    # Ferma il thread esistente se presente
    stop_bot_thread()
    
    # Inizializza il bot con i parametri forniti
    success = init_bot(token=token, chat_id=chat_id)
    if success:
        logger.info("Bot Telegram inizializzato con successo")
        # Non è necessario creare un thread aggiuntivo, perché UPDATER.start_polling
        # già avvia un thread in background per il polling
        return True
    else:
        logger.error("Errore nell'inizializzazione del bot Telegram")
        return False

def stop_bot_thread():
    """Ferma il thread del bot Telegram"""
    # Ferma semplicemente il bot, poiché non abbiamo più un thread separato
    success = stop_bot()
    return success

# Variabile globale per la lingua corrente del bot
current_bot_language = 'it'

def get_bot_translation(key, **kwargs):
    """Ottiene una traduzione per il bot usando la lingua corrente"""
    global current_bot_language
    
    # Importa le funzioni di traduzione da app.py
    try:
        from pathlib import Path
        import json
        
        app_dir = Path(__file__).parent.resolve()
        translation_file = app_dir / 'translations' / f'{current_bot_language}.json'
        if translation_file.exists():
            with open(translation_file, 'r', encoding='utf-8') as f:
                translations = json.load(f)
        else:
            return key
        
        # Naviga attraverso i punti nella chiave
        keys = key.split('.')
        value = translations
        
        for k in keys:
            if isinstance(value, dict) and k in value:
                value = value[k]
            else:
                return key
        
        # Se ci sono parametri, formatta la stringa
        if kwargs and isinstance(value, str):
            try:
                return value.format(**kwargs)
            except KeyError:
                return value
        
        return value
    except Exception as e:
        logger.error(f"Errore nel recupero traduzione {key}: {e}")
        return key

def set_bot_language(language):
    """Imposta la lingua del bot"""
    global current_bot_language
    current_bot_language = language

def get_bot_language():
    """Ottiene la lingua corrente del bot"""
    global current_bot_language
    return current_bot_language

# Esporta le funzioni principali
__all__ = ["init_bot", "stop_bot", "send_notification", "start_bot_thread", "stop_bot_thread", 
           "load_mount_points", "save_mount_points", "load_monitoring_config", "save_monitoring_config",
           "start_monitoring", "stop_monitoring", "get_default_monitoring_config", 
           "set_bot_language", "get_bot_language"]

if __name__ == "__main__":
    # Configurazione del logging
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
    )
    
    # Versione di test standalone
    logger.info("Avvio del bot Telegram in modalità standalone...")
    
    # Leggi le configurazioni da .env se presente
    from dotenv import load_dotenv
    load_dotenv()
    
    # Ottieni token e chat_id dalle variabili d'ambiente
    bot_token = os.environ.get("TELEGRAM_BOT_TOKEN")
    chat_id = os.environ.get("TELEGRAM_CHAT_ID")
    
    if not bot_token or not chat_id:
        logger.error("Token o chat_id non impostati. Imposta TELEGRAM_BOT_TOKEN e TELEGRAM_CHAT_ID nelle variabili d'ambiente o nel file .env")
        exit(1)
    
    # Inizializza il bot
    if init_bot(token=bot_token, chat_id=chat_id):
        logger.info(f"Bot inizializzato con successo. ID chat: {chat_id}")
        
        # Mantieni il bot in esecuzione fino alla chiusura del programma
        try:
            logger.info("Bot in esecuzione. Premi CTRL+C per terminare.")
            UPDATER.idle()
        except KeyboardInterrupt:
            logger.info("Interruzione da tastiera ricevuta. Arresto del bot...")
        finally:
            stop_bot()
            logger.info("Bot arrestato.")
    else:
        logger.error("Impossibile inizializzare il bot. Controlla token e connessione.")