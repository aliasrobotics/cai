FROM kalilinux/kali-rolling

# Set environment variable to non-interactive
ENV DEBIAN_FRONTEND=noninteractive

# Fix Kali Linux repository GPG key issues
RUN apt-get update --allow-insecure-repositories && \
    apt-get install -y --no-install-recommends --allow-unauthenticated kali-archive-keyring && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# [Optional] Uncomment this section to install additional OS packages.
RUN apt-get update && export DEBIAN_FRONTEND=noninteractive \
    && apt-get -y install --no-install-recommends \
        net-tools python3 python3-pip python3-venv \
        curl gnupg nmap iputils-ping ssh git \
        graphviz pkg-config libhdf5-dev \
        build-essential python3-dev \
        asciinema dnsutils \
        apt-transport-https ca-certificates \
        wget dirb gobuster whatweb gfortran \
        cmake libopenblas-dev sshpass seclists \
        golang-go

# # Install Metasploit - path 1
# RUN curl https://raw.githubusercontent.com/rapid7/metasploit-omnibus/master/config/templates/metasploit-framework-wrappers/msfupdate.erb > /tmp/msfinstall \
#     && chmod 755 /tmp/msfinstall \
#     && /tmp/msfinstall

# # Install Metasploit - path 2
# RUN curl https://apt.metasploit.com/metasploit-framework.gpg.key | apt-key add -
# RUN echo "deb https://apt.metasploit.com/ lucid main" | tee /etc/apt/sources.list.d/metasploit-framework.list
# RUN apt-get update && apt-get install metasploit-framework

# Install Metasploit - path 3
RUN curl https://raw.githubusercontent.com/rapid7/metasploit-omnibus/master/config/templates/metasploit-framework-wrappers/msfupdate.erb > msfinstall && chmod 755 msfinstall && ./msfinstall

# Update Kali Linux repositories
RUN apt-get update \
    && apt-get upgrade -y

# # Create a virtual environment
# ENV VIRTUAL_ENV=/opt/venv
# RUN python3 -m venv $VIRTUAL_ENV
# ENV PATH="$VIRTUAL_ENV/bin:$PATH"

# # [Optional] If your pip requirements rarely change, uncomment this section to add them to the image.
# #  alternatively, this also helps avoid having to pull requirements from the internet every single time
# COPY requirements.txt /tmp/pip-tmp/
# RUN pip3 --disable-pip-version-check --no-cache-dir install -r /tmp/pip-tmp/requirements.txt \
#    && rm -rf /tmp/pip-tmp

# FIX for:
#
# Python packages system-wide, try apt install
# python3-xyz, where xyz is the package you are trying to
# install.
#
# see https://github.com/raspiblitz/raspiblitz/issues/4170
RUN mkdir -p /root/.pip && touch /root/.pip/pip.conf
RUN echo "[global]" > /root/.pip/pip.conf && \
    echo "break-system-packages = true" >> /root/.pip/pip.conf

RUN pip3 install --upgrade setuptools
RUN pip3 install pandas  \
                 opentelemetry-sdk opentelemetry-exporter-otlp \
                 mem0ai PyPDF2 sentence_transformers tf-keras \
                 pytest-repeat parameterized pytest-rerunfailures \
                 pytest-clarity tiktoken blobfile pytest-timeout \
                 invoke fabric

# Install rust compiler - dependency of outlines-core
RUN apt-get update && \
    apt-get install -y curl && \
    curl --proto '=https' --tlsv1.2 -sSf https://sh.rustup.rs | sh -s -- -y && \
    . $HOME/.cargo/env && \
    rustup default stable && \
    rustup component add rustfmt clippy && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

ENV PATH="/root/.cargo/bin:${PATH}"
RUN wget https://raw.githubusercontent.com/adfoster-r7/metasploit-info/master/info/module_metadata.json -O /tmp/module_metadata.json

# NOTE: align dev env in Linux
# work
# RUN echo "192.168.3.1 host.docker.internal" >> /etc/hosts
# Update and upgrade packages
# Preconfigure console-setup and install kali-linux-headless fixers
RUN apt-get update && \
    echo "console-setup console-setup/variant select Latin1 and Latin5 - western Europe and Turkic languages" | debconf-set-selections && \
    DEBIAN_FRONTEND=noninteractive apt-get install -y --no-install-recommends kali-linux-headless

# Update pip again -> python3 -m pip install --upgrade pip causes crashes
# Install spacy deps - en_core_web_sm
# RUN python3 -m spacy download en_core_web_sm

# Install docker inside of dev env
RUN apt-get update && \
    apt-get install -y apt-transport-https ca-certificates curl gnupg && \
    curl -fsSL https://download.docker.com/linux/debian/gpg | gpg --dearmor -o /usr/share/keyrings/docker-archive-keyring.gpg && \
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/usr/share/keyrings/docker-archive-keyring.gpg] https://download.docker.com/linux/debian bullseye stable" | tee /etc/apt/sources.list.d/docker.list > /dev/null && \
    apt-get update && \
    apt-get install -y docker-ce docker-ce-cli containerd.io cloc

# # Activate virtual environment by default
# RUN echo "source $VIRTUAL_ENV/bin/activate" >> ~/.bashrc

RUN cargo install --git https://github.com/asciinema/agg

# Remove system's python3 libs to avoid conflicts with pip packages
RUN apt-get remove -y python3-jsonschema && \
    apt-get remove -y python3-numpy && \
    apt-get remove -y python3-uvicorn && \
    apt-get remove -y python3-fastapi && \
    apt-get autoremove -y
