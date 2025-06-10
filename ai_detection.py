#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os
import cv2
import json
import time
import numpy as np
import threading
import logging
from datetime import datetime
from pathlib import Path
import io
import base64
from PIL import Image

# Import condizionale per le dipendenze AI
AI_ENABLED = os.environ.get('ENABLE_AI_DETECTION', 'false').lower() == 'true'

if AI_ENABLED:
    try:
        from ultralytics import YOLO
        import torch
    except ImportError as e:
        logging.error(f"Dipendenze AI non disponibili: {e}")
        AI_ENABLED = False

# Configurazione logging
logger = logging.getLogger("AI Detection")

# Percorsi configurazione
AI_CONFIG_FILE = Path('/etc/ssh_monitor/ai_config.json')
CAMERAS_CONFIG_FILE = Path('/etc/ssh_monitor/cameras_config.json')

# Thread globali per il monitoraggio
DETECTION_THREADS = {}
STOP_DETECTION = threading.Event()

# Mappatura categorie YOLO alle nostre categorie
YOLO_CATEGORY_MAP = {
    'people': [0],  # person
    'objects': [
        15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29, 30, 31, 32, 33, 34, 35, 36, 37, 38, 39, 40, 41, 42, 43, 44, 45, 46, 47, 48, 49, 50, 51, 52, 53, 54, 55, 56, 57, 58, 59, 60, 61, 62, 63, 64, 65, 66, 67, 68, 69, 70, 71, 72, 73, 74, 75, 76, 77, 78, 79
    ],  # vari oggetti
    'animals': [14, 15, 16, 17, 18, 19, 20, 21, 22, 23]  # animali comuni
}

# Nomi delle classi YOLO
YOLO_CLASS_NAMES = [
    "person", "bicycle", "car", "motorcycle", "airplane", "bus", "train", "truck", "boat",
    "traffic light", "fire hydrant", "stop sign", "parking meter", "bench", "bird", "cat",
    "dog", "horse", "sheep", "cow", "elephant", "bear", "zebra", "giraffe", "backpack",
    "umbrella", "handbag", "tie", "suitcase", "frisbee", "skis", "snowboard", "sports ball",
    "kite", "baseball bat", "baseball glove", "skateboard", "surfboard", "tennis racket",
    "bottle", "wine glass", "cup", "fork", "knife", "spoon", "bowl", "banana", "apple",
    "sandwich", "orange", "broccoli", "carrot", "hot dog", "pizza", "donut", "cake",
    "chair", "couch", "dining table", "toilet", "tv", "laptop",
    "mouse", "remote", "keyboard", "cell phone", "microwave", "oven", "toaster", "sink",
    "book", "clock", "vase", "scissors", "teddy bear", "hair drier", "toothbrush"
]

def get_default_ai_config():
    """Configurazione predefinita per l'AI detection"""
    return {
        "global_enabled": False,
        "model_path": "yolov10m-human.pt",  # Modello medio per default
        "detection_interval": 2.0,  # Secondi tra analisi frame
        "max_concurrent_cameras": 4,
        "save_images": True,  # Salvataggio globale delle immagini
        "save_path": "/var/lib/ssh_monitor/snapshots",  # Percorso globale di salvataggio
        "snapshot_quality": 100  # Qualità moderata per evitare corruzione
    }

def load_ai_config():
    """Carica la configurazione AI dal file"""
    try:
        if AI_CONFIG_FILE.exists():
            with open(AI_CONFIG_FILE, 'r') as f:
                config = json.load(f)
                # Merge con configurazione default
                default = get_default_ai_config()
                for key, value in default.items():
                    if key not in config:
                        config[key] = value
                return config
        return get_default_ai_config()
    except Exception as e:
        logger.error(f"Errore nel caricamento configurazione AI: {e}")
        return get_default_ai_config()

def save_ai_config(config):
    """Salva la configurazione AI"""
    try:
        AI_CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(AI_CONFIG_FILE, 'w') as f:
            json.dump(config, f, indent=2)
        return True
    except Exception as e:
        logger.error(f"Errore nel salvataggio configurazione AI: {e}")
        return False

def get_default_camera_config():
    """Configurazione predefinita per una telecamera"""
    return {
        "name": "",
        "rtsp_url": "",
        "enabled": False,
        "confidence_threshold": 0.5,
        "iou_threshold": 0.3,
        "categories": {
            "people": False,
            "objects": False,
            "animals": False
        }
    }

def load_cameras_config():
    """Carica la configurazione delle telecamere"""
    try:
        if CAMERAS_CONFIG_FILE.exists():
            with open(CAMERAS_CONFIG_FILE, 'r') as f:
                return json.load(f)
        return {}
    except Exception as e:
        logger.error(f"Errore nel caricamento configurazione telecamere: {e}")
        return {}

def save_cameras_config(cameras):
    """Salva la configurazione delle telecamere"""
    try:
        CAMERAS_CONFIG_FILE.parent.mkdir(parents=True, exist_ok=True)
        with open(CAMERAS_CONFIG_FILE, 'w') as f:
            json.dump(cameras, f, indent=2)
        return True
    except Exception as e:
        logger.error(f"Errore nel salvataggio configurazione telecamere: {e}")
        return False

class CameraDetector:
    """Classe per gestire la detection su una singola telecamera"""
    
    def __init__(self, camera_id, camera_config, ai_config):
        self.camera_id = camera_id
        self.camera_config = camera_config
        self.ai_config = ai_config
        self.model = None
        self.cap = None
        self.running = False
        self.previous_detections = []  # Memorizza le detection del frame precedente
        self.last_notification_time = 0  # Timestamp dell'ultima notifica inviata
        self.notification_cooldown = 10.0  # Cooldown di 10 secondi tra notifiche per la stessa scena
        
    def initialize_model(self):
        """Inizializza il modello YOLO"""
        if not AI_ENABLED:
            logger.error("AI Detection non abilitata")
            return False
            
        try:
            model_name = self.ai_config.get('model_path', 'yolov10l-human.pt')
            # Crea directory per i modelli persistenti
            models_dir = Path('/var/lib/ssh_monitor/models')
            models_dir.mkdir(parents=True, exist_ok=True)
            
            # Percorso completo al modello nella directory persistente
            persistent_model_path = models_dir / model_name
            
            # Se il modello esiste nella directory persistente, usalo
            if persistent_model_path.exists():
                logger.info(f"Caricamento modello da storage persistente: {persistent_model_path}")
                self.model = YOLO(str(persistent_model_path))
            else:
                # Altrimenti scarica il modello e salvalo nella directory persistente
                logger.info(f"Scaricamento modello {model_name} nella directory persistente")
                self.model = YOLO(model_name)
                # Salva il modello nella directory persistente
                if hasattr(self.model, 'model') and hasattr(self.model.model, 'pt_path'):
                    # Ottieni il percorso del modello scaricato
                    downloaded_path = Path(self.model.model.pt_path)
                    if downloaded_path.exists():
                        # Copia il modello nella directory persistente
                        import shutil
                        shutil.copy(downloaded_path, persistent_model_path)
                        logger.info(f"Modello salvato in: {persistent_model_path}")
            
            logger.info(f"Modello YOLO caricato: {model_name}")
            return True
        except Exception as e:
            logger.error(f"Errore nel caricamento del modello: {e}")
            return False
    
    def connect_camera(self):
        """Connette alla telecamera RTSP"""
        try:
            rtsp_url = self.camera_config.get('rtsp_url', '')
            if not rtsp_url:
                logger.error(f"URL RTSP non configurato per camera {self.camera_id}")
                return False
                
            self.cap = cv2.VideoCapture(rtsp_url)
            if not self.cap.isOpened():
                logger.error(f"Impossibile connettersi alla camera {self.camera_id}: {rtsp_url}")
                return False
                
            # Configurazioni ottimali per RTSP
            self.cap.set(cv2.CAP_PROP_BUFFERSIZE, 1)
            self.cap.set(cv2.CAP_PROP_FPS, 10)
            
            logger.info(f"Connessione stabilita con camera {self.camera_id}")
            return True
        except Exception as e:
            logger.error(f"Errore nella connessione camera {self.camera_id}: {e}")
            return False
    
    def process_frame(self, frame):
        """Elabora un frame per la detection"""
        try:
            if self.model is None:
                return []
            
            # Preprocessing: ridimensiona il frame a 1280x720 per l'AI detection
            original_height, original_width = frame.shape[:2]
            preprocessed_frame = cv2.resize(frame, (1280, 720))
            
            # Calcola i fattori di scala per convertire le coordinate delle detection
            scale_x = original_width / 1280
            scale_y = original_height / 720
                
            # Esegui detection sul frame preprocessato
            results = self.model(preprocessed_frame, verbose=False)
            
            detections = []
            for result in results:
                boxes = result.boxes
                if boxes is not None:
                    for box in boxes:
                        # Estrai informazioni detection
                        class_id = int(box.cls[0])
                        confidence = float(box.conf[0])
                        class_name = YOLO_CLASS_NAMES[class_id] if class_id < len(YOLO_CLASS_NAMES) else "unknown"
                        
                        # Filtra per soglia di confidenza
                        if confidence < self.camera_config.get('confidence_threshold', 0.5):
                            continue
                            
                        # Determina categoria
                        category = self._get_category_for_class(class_id)
                        if not category:
                            continue
                            
                        # Verifica se la categoria è abilitata
                        if not self.camera_config.get('categories', {}).get(category, False):
                            continue
                            
                        # Coordinate bounding box (dal frame preprocessato 1280x720)
                        x1, y1, x2, y2 = box.xyxy[0].tolist()
                        
                        # Scala le coordinate al frame originale
                        x1_scaled = x1 * scale_x
                        y1_scaled = y1 * scale_y
                        x2_scaled = x2 * scale_x
                        y2_scaled = y2 * scale_y
                        
                        detections.append({
                            'class_id': class_id,
                            'class_name': class_name,
                            'category': category,
                            'confidence': confidence,
                            'bbox': [x1_scaled, y1_scaled, x2_scaled, y2_scaled]
                        })
            
            return detections
        except Exception as e:
            logger.error(f"Errore nell'elaborazione frame camera {self.camera_id}: {e}")
            return []
    
    def _get_category_for_class(self, class_id):
        """Determina la categoria per una classe YOLO"""
        for category, class_ids in YOLO_CATEGORY_MAP.items():
            if class_id in class_ids:
                return category
        return None
    
    def capture_snapshot(self, frame, detections):
        """Cattura uno screenshot con le detection evidenziate"""
        try:
            import tempfile
            
            # Copia del frame per il disegno
            annotated_frame = frame.copy()
            
            # Ridimensiona sempre l'immagine a 1280x720 per l'invio al bot Telegram
            original_height, original_width = annotated_frame.shape[:2]
            annotated_frame = cv2.resize(annotated_frame, (1280, 720))
            
            # Calcola i fattori di scala per le coordinate delle detection
            scale_x = 1280 / original_width
            scale_y = 720 / original_height
            
            # Scala le coordinate delle detection per il frame ridimensionato
            scaled_detections = []
            for detection in detections:
                scaled_detection = detection.copy()
                bbox = detection['bbox']
                scaled_bbox = [bbox[0] * scale_x, bbox[1] * scale_y, bbox[2] * scale_x, bbox[3] * scale_y]
                scaled_detection['bbox'] = scaled_bbox
                scaled_detections.append(scaled_detection)
            detections = scaled_detections
            
            # Disegna le bounding box
            for detection in detections:
                bbox = detection['bbox']
                x1, y1, x2, y2 = map(int, bbox)
                
                # Assicurati che le coordinate siano nell'immagine
                height, width = annotated_frame.shape[:2]
                x1 = max(0, min(x1, width - 1))
                y1 = max(0, min(y1, height - 1))
                x2 = max(0, min(x2, width - 1))
                y2 = max(0, min(y2, height - 1))
                
                # Colore per categoria (BGR formato OpenCV)
                color_map = {
                    'people': (0, 255, 0),    # Verde
                    'objects': (255, 0, 0),   # Blu
                    'animals': (0, 0, 255)    # Rosso
                }
                color = color_map.get(detection['category'], (255, 255, 255))
                
                # Disegna rettangolo
                cv2.rectangle(annotated_frame, (x1, y1), (x2, y2), color, 2)
                
                # Etichetta
                confidence_percent = detection['confidence'] * 100
                label = f"{detection['class_name']} {confidence_percent:.1f}%"
                label_size = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.5, 2)[0]
                
                # Assicurati che l'etichetta sia dentro l'immagine
                label_y = max(y1 - 10, label_size[1] + 5)
                cv2.rectangle(annotated_frame, (x1, label_y - label_size[1] - 5), 
                            (x1 + label_size[0] + 5, label_y + 5), color, -1)
                cv2.putText(annotated_frame, label, (x1 + 2, label_y - 2), 
                          cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
            
            # Aggiungi timestamp all'immagine
            timestamp = datetime.now().strftime("%d/%m/%Y %H:%M:%S")
            cv2.putText(annotated_frame, timestamp, (10, 30), 
                      cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 255), 2)
            
            # Salva come file temporaneo JPEG per Telegram
            camera_name = self.camera_config.get('name', f'camera_{self.camera_id}')
            timestamp_file = datetime.now().strftime("%Y%m%d_%H%M%S")
            temp_file = tempfile.NamedTemporaryFile(
                suffix=f"_{camera_name}_{timestamp_file}.jpg", 
                delete=False
            )
            
            # Salva l'immagine usando cv2.imwrite (metodo della versione old)
            cv2.imwrite(temp_file.name, annotated_frame)
            temp_file.close()
            
            # Se abilitato globalmente, salva anche una copia permanente nella cartella configurata
            ai_config = load_ai_config()
            if ai_config.get('save_images', True):
                save_path = ai_config.get('save_path', '/var/lib/ssh_monitor/snapshots')
                try:
                    # Crea la directory se non esiste
                    Path(save_path).mkdir(parents=True, exist_ok=True)
                    
                    # Nome file permanente
                    permanent_filename = f"{camera_name}_{timestamp_file}.jpg"
                    permanent_path = Path(save_path) / permanent_filename
                    
                    # Copia il file nella directory permanente
                    import shutil
                    shutil.copy2(temp_file.name, permanent_path)
                    
                    logger.info(f"Snapshot salvato permanentemente: {permanent_path}")
                except Exception as e:
                    logger.error(f"Errore nel salvataggio permanente snapshot: {e}")
            
            logger.info(f"Snapshot temporaneo salvato: {temp_file.name}")
            return temp_file.name
            
        except Exception as e:
            logger.error(f"Errore nella cattura snapshot camera {self.camera_id}: {e}")
            return None
    
    def _calculate_iou(self, box1, box2):
        """Calcola l'Intersection over Union (IoU) tra due bounding box"""
        x1_1, y1_1, x2_1, y2_1 = box1
        x1_2, y1_2, x2_2, y2_2 = box2
        
        # Calcola l'area di intersezione
        x1_inter = max(x1_1, x1_2)
        y1_inter = max(y1_1, y1_2)
        x2_inter = min(x2_1, x2_2)
        y2_inter = min(y2_1, y2_2)
        
        if x2_inter <= x1_inter or y2_inter <= y1_inter:
            return 0.0
        
        intersection = (x2_inter - x1_inter) * (y2_inter - y1_inter)
        
        # Calcola l'area delle due box
        area1 = (x2_1 - x1_1) * (y2_1 - y1_1)
        area2 = (x2_2 - x1_2) * (y2_2 - y1_2)
        
        # Calcola l'unione
        union = area1 + area2 - intersection
        
        if union == 0:
            return 0.0
        
        return intersection / union
    
    def _is_new_detection_scene(self, current_detections):
        """Verifica se le detection attuali rappresentano una nuova scena rispetto alle precedenti"""
        if not self.previous_detections:
            return True
        
        # Se il numero di detection è molto diverso, è probabilmente una nuova scena
        if abs(len(current_detections) - len(self.previous_detections)) > 2:
            return True
        
        # Verifica se ci sono detection significativamente diverse
        iou_threshold = self.camera_config.get('iou_threshold', 0.3)  # Soglia IoU configurabile
        matched_detections = 0
        
        for current_det in current_detections:
            current_bbox = current_det['bbox']
            current_category = current_det['category']
            
            for prev_det in self.previous_detections:
                prev_bbox = prev_det['bbox']
                prev_category = prev_det['category']
                
                # Confronta solo detection della stessa categoria
                if current_category == prev_category:
                    iou = self._calculate_iou(current_bbox, prev_bbox)
                    if iou > iou_threshold:
                        matched_detections += 1
                        break
        
        # Se la maggior parte delle detection sono simili a quelle precedenti,
        # non è una nuova scena
        similarity_ratio = matched_detections / len(current_detections) if current_detections else 0
        return similarity_ratio < 0.6  # Se meno del 60% delle detection sono simili, è una nuova scena
    
    def run_detection(self):
        """Loop principale di detection per la telecamera"""
        self.running = True
        logger.info(f"Avvio detection per camera {self.camera_id}")
        
        if not self.initialize_model():
            self.running = False
            return
            
        if not self.connect_camera():
            self.running = False
            return
        
        detection_interval = self.ai_config.get('detection_interval', 2.0)
        last_detection_time = 0
        
        try:
            while self.running and not STOP_DETECTION.is_set():
                ret, frame = self.cap.read()
                if not ret:
                    logger.warning(f"Impossibile leggere frame da camera {self.camera_id}")
                    time.sleep(1)
                    continue
                
                current_time = time.time()
                if current_time - last_detection_time >= detection_interval:
                    detections = self.process_frame(frame)
                    
                    if detections:
                        # Verifica se è una nuova scena e se è passato abbastanza tempo dall'ultima notifica
                        is_new_scene = self._is_new_detection_scene(detections)
                        time_since_last_notification = current_time - self.last_notification_time
                        
                        if is_new_scene and time_since_last_notification >= self.notification_cooldown:
                            # Cattura snapshot
                            snapshot = self.capture_snapshot(frame, detections)
                            
                            # Invia notifica Telegram
                            self._send_telegram_notification(detections, snapshot)
                            self.last_notification_time = current_time
                            
                            logger.info(f"Camera {self.camera_id}: Nuova scena rilevata, notifica inviata")
                        else:
                            if not is_new_scene:
                                logger.debug(f"Camera {self.camera_id}: Scena simile alla precedente, notifica saltata")
                            else:
                                logger.debug(f"Camera {self.camera_id}: Cooldown attivo, notifica saltata")
                        
                        # Aggiorna le detection precedenti
                        self.previous_detections = detections.copy()
                    else:
                        # Se non ci sono detection, resetta le detection precedenti
                        self.previous_detections = []
                    
                    last_detection_time = current_time
                
                # Piccola pausa per evitare sovraccarico CPU
                time.sleep(0.1)
                
        except Exception as e:
            logger.error(f"Errore nel loop detection camera {self.camera_id}: {e}")
        finally:
            if self.cap:
                self.cap.release()
            self.running = False
            logger.info(f"Detection arrestata per camera {self.camera_id}")
    
    def _send_telegram_notification(self, detections, snapshot):
        """Invia notifica Telegram per le detection"""
        try:
            from telegram_bot import send_telegram_photo, send_telegram_message
            import os
            
            camera_name = self.camera_config.get('name', f'Camera {self.camera_id}')
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            
            # Raggruppa detection per categoria
            categories_detected = {}
            for detection in detections:
                category = detection['category']
                if category not in categories_detected:
                    categories_detected[category] = []
                categories_detected[category].append(detection)
            
            # Costruisci messaggio (senza Markdown complesso come nella versione old)
            message = "📦 RILEVAMENTO TELECAMERA\n\n"
            message += f"📹 Camera: {camera_name}\n\n"
            
            for category, dets in categories_detected.items():
                category_emoji = {
                    'people': '👤',
                    'objects': '📦', 
                    'animals': '🐾'
                }.get(category, '❓')
                
                # Traduzioni per i tipi di oggetti (come nella versione old)
                type_translations = {
                    'people': 'Persone',
                    'objects': 'Oggetti', 
                    'animals': 'Animali'
                }
                
                category_it = type_translations.get(category, category)
                message += f"{category_emoji} {category_it}:\n"
                for det in dets:
                    confidence_percent = det['confidence'] * 100
                    message += f"  • {det['class_name']} ({confidence_percent:.1f}%)\n"
                message += "\n"
            
            message += f"🕐 Timestamp: {timestamp}"
            
            # Invia con snapshot se disponibile (usando file path come nella versione old)
            if snapshot and isinstance(snapshot, str) and os.path.exists(snapshot):
                logger.info(f"Invio notifica con foto: {snapshot}")
                success = send_telegram_photo(snapshot, message)
                
                # Rimuovi il file temporaneo dopo l'invio (come nella versione old)
                try:
                    os.unlink(snapshot)
                except Exception as cleanup_e:
                    logger.warning(f"Errore nella rimozione file temporaneo: {cleanup_e}")
                
                if not success:
                    logger.warning("Fallback: invio solo messaggio di testo")
                    send_telegram_message(message)
            else:
                logger.info("Invio notifica solo testo")
                send_telegram_message(message)
                
        except Exception as e:
            logger.error(f"Errore nell'invio notifica Telegram: {e}")

def start_camera_detection(camera_id, camera_config, ai_config):
    """Avvia detection per una telecamera specifica"""
    global DETECTION_THREADS
    
    if camera_id in DETECTION_THREADS and DETECTION_THREADS[camera_id].running:
        logger.info(f"Detection già attiva per camera {camera_id}")
        return False
    
    try:
        detector = CameraDetector(camera_id, camera_config, ai_config)
        thread = threading.Thread(target=detector.run_detection, daemon=True)
        thread.detector = detector  # Mantieni riferimento al detector
        thread.start()
        
        DETECTION_THREADS[camera_id] = thread
        logger.info(f"Detection avviata per camera {camera_id}")
        return True
    except Exception as e:
        logger.error(f"Errore nell'avvio detection camera {camera_id}: {e}")
        return False

def stop_camera_detection(camera_id):
    """Ferma detection per una telecamera specifica"""
    global DETECTION_THREADS
    
    if camera_id in DETECTION_THREADS:
        thread = DETECTION_THREADS[camera_id]
        if hasattr(thread, 'detector'):
            thread.detector.running = False
        
        try:
            thread.join(timeout=5)
            del DETECTION_THREADS[camera_id]
            logger.info(f"Detection fermata per camera {camera_id}")
            return True
        except Exception as e:
            logger.error(f"Errore nel fermare detection camera {camera_id}: {e}")
            return False
    
    return True

def start_all_detections():
    """Avvia detection per tutte le telecamere abilitate"""
    if not AI_ENABLED:
        logger.warning("AI Detection non abilitata tramite variabile d'ambiente")
        return False
    
    ai_config = load_ai_config()
    if not ai_config.get('global_enabled', False):
        logger.info("AI Detection globalmente disabilitata")
        return False
    
    cameras_config = load_cameras_config()
    started_count = 0
    
    for camera_id, camera_config in cameras_config.items():
        if camera_config.get('enabled', False):
            if start_camera_detection(camera_id, camera_config, ai_config):
                started_count += 1
    
    logger.info(f"Avviate {started_count} telecamere per detection")
    return started_count > 0

def stop_all_detections():
    """Ferma tutte le detection"""
    global DETECTION_THREADS, STOP_DETECTION
    
    STOP_DETECTION.set()
    
    for camera_id in list(DETECTION_THREADS.keys()):
        stop_camera_detection(camera_id)
    
    STOP_DETECTION.clear()
    logger.info("Tutte le detection sono state fermate")

def get_detection_status():
    """Ottieni stato delle detection"""
    global DETECTION_THREADS
    
    # Carica la configurazione delle telecamere per ottenere i nomi
    cameras_config = load_cameras_config()
    
    status = {
        'ai_enabled': AI_ENABLED,
        'total_cameras': len(DETECTION_THREADS),
        'active_cameras': []
    }
    
    for camera_id, thread in DETECTION_THREADS.items():
        is_running = thread.is_alive() and hasattr(thread, 'detector') and thread.detector.running
        
        # Ottieni il nome della telecamera dalla configurazione
        camera_config = cameras_config.get(camera_id, {})
        camera_name = camera_config.get('name', f'Camera {camera_id}')
        
        # Determina lo stato della telecamera
        if is_running:
            camera_status = 'Attiva'
        elif thread.is_alive():
            camera_status = 'In avvio'
        else:
            camera_status = 'Fermata'
        
        status['active_cameras'].append({
            'camera_id': camera_id,
            'name': camera_name,
            'running': is_running,
            'status': camera_status
        })
    
    return status

def restart_all_detections():
    """Riavvia tutte le detection"""
    logger.info("Riavvio detection...")
    stop_all_detections()
    time.sleep(2)  # Pausa per assicurarsi che tutto sia fermato
    return start_all_detections()
