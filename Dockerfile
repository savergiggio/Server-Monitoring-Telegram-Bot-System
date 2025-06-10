FROM python:3.9-slim

# Installa le dipendenze necessarie
RUN apt-get update && apt-get install -y --no-install-recommends \
    locales \
    ssh \
    net-tools \
    iproute2 \
    docker.io \
    psmisc \
    && rm -rf /var/lib/apt/lists/* \
    && sed -i -e 's/# it_IT.UTF-8 UTF-8/it_IT.UTF-8 UTF-8/' /etc/locale.gen \
    && locale-gen

# Imposta la localizzazione
ENV LANG it_IT.UTF-8
ENV LANGUAGE it_IT:it
ENV LC_ALL it_IT.UTF-8

# Imposta il workdir
WORKDIR /app

# Crea le directory necessarie
RUN mkdir -p /etc/ssh_monitor /var/lib/ssh_monitor

# Copia il file requirements e installa le dipendenze base
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Installa dipendenze AI se abilitato tramite build arg
ARG ENABLE_AI_DETECTION=false
COPY requirements_ai.txt .
RUN if [ "$ENABLE_AI_DETECTION" = "true" ]; then \
        apt-get update && apt-get install -y --no-install-recommends \
            build-essential \
            gcc \
            g++ \
            libglib2.0-0 \
            libsm6 \
            libxext6 \
            libxrender1 \
            libgomp1 \
            libgl1-mesa-glx \
            libglib2.0-dev \
            && rm -rf /var/lib/apt/lists/* \
            && pip install --no-cache-dir -r requirements_ai.txt; \
    fi

# Copia l'applicazione e i file statici
COPY app.py .
COPY telegram_bot.py .
COPY ai_detection.py .
COPY templates templates/
COPY static static/
COPY translations translations/

# Copia lo script di entrypoint e rendilo eseguibile
COPY entrypoint.sh .
RUN chmod +x entrypoint.sh

# Esponi i volumi per la configurazione e i dati persistenti
VOLUME ["/etc/ssh_monitor", "/var/lib/ssh_monitor"]

# Crea le directory per i punti di mount di default
RUN mkdir -p /uploads /data /backups

# Esponi la porta per l'interfaccia web
EXPOSE 5000

# Imposta l'entrypoint
ENTRYPOINT ["./entrypoint.sh"]