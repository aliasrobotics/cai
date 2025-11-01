# Installation Guide for CAI Pro v0.6

← [Back to Installation Guide](../README.md#nut_and_bolt-install)

## Welcome to CAI Pro!

If your subscription is active, you have received a confirmation email. Then, get and save your API-Key and please follow these instructions to install CAI Pro on your system.

### Important

- Your API Key is personal and non-transferable.
- It will be permanently linked to the first system where it is used.

## System Requirements

- OS: Ubuntu 24.04 (x86_64, 64-bit)
- Language: English
- Python: 3.8+ (installed automatically)
- Memory: Minimum 4 GB RAM

## Installation Steps

- Create a folder in your preferred directory.
- Open a terminal in that directory.
- Create a virtual environment, activate it, and install CAI Pro with the following commands:
  - `sudo apt update`
  - `python3.12 -m venv cai_env`
  - `source cai_env/bin/activate`
  - `pip install --index-url https://packages.aliasrobotics.com:664/<api-key>/ cai-framework`
- Important note:
  - The last command requires customization. Replace `<api-key>` with the API Key provided in the confirmation email for your subscription, for example: `sk--xxxxxxxxxxxxxxxx`
- Once the installation is complete, run:
  - `cai –tui`

## Accessing CAI

- Command Line → run: `cai –tui`

## Support

If you encounter any issues, contact us at: contact@aliasrobotics.com

Although we do not provide official support for other operating systems, we offer the recommended installation steps below.

## Installation Steps for Other OS

### OS X

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
echo -e 'OPENAI_API_KEY="sk-1234"\nANTHROPIC_API_KEY=""\nOLLAMA=""\nPROMPT_TOOLKIT_NO_CPR=1\nCAI_STREAM=false' > .env

# Launch CAI
cai  # first launch it can take up to 30 seconds
```

### Windows WSL

Go to the Microsoft page: https://learn.microsoft.com/en-us/windows/wsl/install

Here you will find all the instructions to install WSL. From Powershell write: `wsl --install`

```bash
sudo apt-get update && \
sudo apt-get install -y git python3-pip python3-venv

# Create the virtual environment
python3 -m venv cai_env

# Install the package from the local directory
source cai_env/bin/activate && pip install cai-framework

# Generate a .env file and set up with defaults
echo -e 'OPENAI_API_KEY="sk-1234"\nANTHROPIC_API_KEY=""\nOLLAMA=""\nPROMPT_TOOLKIT_NO_CPR=1\nCAI_STREAM=false' > .env

# Launch CAI
cai  # first launch it can take up to 30 seconds
```

### Android

We recommend having at least 8 GB of RAM:

1. First of all, install userland: https://play.google.com/store/apps/details?id=tech.ula&hl=es
2. Install Kali minimal in basic options (for free). [Or any other kali option if preferred]
3. Update apt keys like in this example: https://superuser.com/questions/1644520/apt-get-update-issue-in-kali, inside UserLand's Kali terminal execute:

```bash
# Get new apt keys
wget http://http.kali.org/kali/pool/main/k/kali-archive-keyring/kali-archive-keyring_2024.1_all.deb

# Install new apt keys
sudo dpkg -i kali-archive-keyring_2024.1_all.deb && rm kali-archive-keyring_2024.1_all.deb

# Update APT repository
sudo apt-get update

# CAI requires python 3.12, lets install it (CAI for kali in Android)
sudo apt-get update && sudo apt-get install -y git python3-pip build-essential zlib1g-dev \
libncurses5-dev libgdbm-dev libnss3-dev libssl-dev libreadline-dev libffi-dev libsqlite3-dev \
wget libbz2-dev pkg-config

wget https://www.python.org/ftp/python/3.12.4/Python-3.12.4.tar.xz
tar xf Python-3.12.4.tar.xz
cd Python-3.12.4
./configure --enable-optimizations
sudo make altinstall  # This command takes long to execute

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

---

**[⬅️ Return to Main Installation Guide](../README.md#nut_and_bolt-install)**

