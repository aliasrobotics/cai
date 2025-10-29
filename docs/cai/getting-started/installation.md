# Installation

```bash
pip install cai-framework
```

## OS X
```bash
# Install homebrew
/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"

# Install dependencies
brew update && \
    brew install git python@3.12

# Create virtual environment
python3.12 -m venv cai_env

# Install the package from the local directory
source cai_env/bin/activate && pip install cai-framework

# Generate a .env file and set up with defaults
echo -e 'OPENAI_API_KEY="sk-1234"\nANTHROPIC_API_KEY=""\nOLLAMA=""\nPROMPT_TOOLKIT_NO_CPR=1' > .env

# Launch CAI
cai  # first launch it can take up to 30 seconds
```

## Ubuntu 24.04
```bash
sudo apt-get update && \
    sudo apt-get install -y git python3-pip python3.12-venv

# Create the virtual environment
python3.12 -m venv cai_env

# Install the package from the local directory
source cai_env/bin/activate && pip install cai-framework

# Generate a .env file and set up with defaults
echo -e 'OPENAI_API_KEY="sk-1234"\nANTHROPIC_API_KEY=""\nOLLAMA=""\nPROMPT_TOOLKIT_NO_CPR=1' > .env

# Launch CAI
cai  # first launch it can take up to 30 seconds
```

## Ubuntu 20.04
```bash
sudo apt-get update && \
    sudo apt-get install -y software-properties-common

# Fetch Python 3.12
sudo add-apt-repository ppa:deadsnakes/ppa && sudo apt update
sudo apt install python3.12 python3.12-venv python3.12-dev -y

# Create the virtual environment
python3.12 -m venv cai_env

# Install the package from the local directory
source cai_env/bin/activate && pip install cai-framework

# Generate a .env file and set up with defaults
echo -e 'OPENAI_API_KEY="sk-1234"\nANTHROPIC_API_KEY=""\nOLLAMA=""\nPROMPT_TOOLKIT_NO_CPR=1' > .env

# Launch CAI
cai  # first launch it can take up to 30 seconds
```

## Windows WSL
Go to the Microsoft page: `https://learn.microsoft.com/en-us/windows/wsl/install`. 
Here you will find all the instructions to install WSL

From Powershell write: ` wsl --install`

```bash
sudo apt-get update && \
    sudo apt-get install -y git python3-pip python3-venv

# Create the virtual environment
python3 -m venv cai_env

# Install the package from the local directory
source cai_env/bin/activate && pip install cai-framework

# Generate a .env file and set up with defaults
echo -e 'OPENAI_API_KEY="sk-1234"\nANTHROPIC_API_KEY=""\nOLLAMA=""\nPROMPT_TOOLKIT_NO_CPR=1' > .env

# Launch CAI
cai  # first launch it can take up to 30 seconds
```

## Android

We recommend having at least 8 GB of RAM:

1. First of all, install userland https://play.google.com/store/apps/details?id=tech.ula&hl=es

2. Install Kali minimal in basic options (for free). [Or any other kali option if preferred]

3. Update apt keys like in this example: https://superuser.com/questions/1644520/apt-get-update-issue-in-kali, inside UserLand's Kali terminal execute

```bash
# Get new apt keys
wget http://http.kali.org/kali/pool/main/k/kali-archive-keyring/kali-archive-keyring_2024.1_all.deb

# Install new apt keys
sudo dpkg -i kali-archive-keyring_2024.1_all.deb && rm kali-archive-keyring_2024.1_all.deb

# Update APT repository
sudo apt-get update

# CAI requieres python 3.12, lets install it (CAI for kali in Android)
sudo apt-get update && sudo apt-get install -y git python3-pip build-essential zlib1g-dev libncurses5-dev libgdbm-dev libnss3-dev libssl-dev libreadline-dev libffi-dev libsqlite3-dev wget libbz2-dev pkg-config
wget https://www.python.org/ftp/python/3.12.4/Python-3.12.4.tar.xz
tar xf Python-3.12.4.tar.xz
cd ./configure --enable-optimizations
sudo make altinstall # This command takes long to execute

# Clone CAI's source code
git clone https://github.com/aliasrobotics/cai && cd cai

# Create virtual environment
python3.12 -m venv cai_env

# Install the package from the local directory
source cai_env/bin/activate && pip3 install -e .

# Generate a .env file and set up
cp .env.example .env  # edit here your keys/models

# Launch CAI
cai
``` 

### Custom OpenAI Base URL Support

CAI supports configuring a custom OpenAI API base URL via the `OPENAI_BASE_URL` environment variable. This allows users to redirect API calls to a custom endpoint, such as a proxy or self-hosted OpenAI-compatible service.

Example `.env` entry configuration:
```
OLLAMA_API_BASE="https://custom-openai-proxy.com/v1"
```

Or directly from the command line:
```bash
OLLAMA_API_BASE="https://custom-openai-proxy.com/v1" cai
```
