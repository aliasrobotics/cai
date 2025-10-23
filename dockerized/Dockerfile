# CAI Production Container - Minimalistisch & Effizient
FROM kalilinux/kali-rolling

ENV DEBIAN_FRONTEND=noninteractive

# Fix Kali GPG Keys
RUN apt-get update --allow-insecure-repositories && \
    apt-get install -y --no-install-recommends --allow-unauthenticated kali-archive-keyring && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# pentesting stuff
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        python3 \
        python3-pip \
        curl \
        wget \
        git \
        nmap \
        iputils-ping \
        dnsutils \
        ca-certificates \
        netcat-traditional \
        burpsuite \
        sqlmap \
        nikto \
        dirb \
        gobuster \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# FIX: pip system-packages Warning (whatever)
RUN mkdir -p /root/.pip && \
    echo "[global]" > /root/.pip/pip.conf && \
    echo "break-system-packages = true" >> /root/.pip/pip.conf

# pip upgrade
RUN pip3 install --upgrade pip setuptools wheel


WORKDIR /opt/cai

# CAI Framework install
RUN pip3 install cai-framework

# .env Template (overriden by volume mount.. but just to be safe)
RUN echo 'OPENAI_API_KEY="sk-1234"' > /opt/cai/.env && \
    echo 'ANTHROPIC_API_KEY=""' >> /opt/cai/.env && \
	echo 'DEEPSEEK_API_KEY=""' >> /opt/cai/.env && \
    echo 'OLLAMA_API_BASE=""' >> /opt/cai/.env && \
    echo 'PROMPT_TOOLKIT_NO_CPR=1' >> /opt/cai/.env && \
    echo 'CAI_STREAM=false' >> /opt/cai/.env

# Logs 
RUN mkdir -p /opt/cai/logs

# Startup Script
RUN echo '#!/bin/bash' > /opt/cai/start.sh && \
    echo 'if [ -f /config/.env ]; then' >> /opt/cai/start.sh && \
    echo '  echo "Loading .env from /config/.env"' >> /opt/cai/start.sh && \
    echo '  cp /config/.env /opt/cai/.env' >> /opt/cai/start.sh && \
    echo 'fi' >> /opt/cai/start.sh && \
    echo 'cd /opt/cai' >> /opt/cai/start.sh && \
    echo 'exec cai "$@"' >> /opt/cai/start.sh && \
    chmod +x /opt/cai/start.sh

# Healthcheck
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD python3 -c "import cai; print('OK')" || exit 1

# Default: start cai
ENTRYPOINT ["/opt/cai/start.sh"]

# Fallback other stuff goes here?
CMD []
