# Script to set up claude code

# Using nvm (recommended)
curl -fsSL https://raw.githubusercontent.com/nvm-sh/nvm/v0.39.7/install.sh | bash
# Restart your terminal or source nvm
source ~/.nvm/nvm.sh
# Install latest LTS version of Node.js
nvm install --lts
# Install claude code
npm install -g @anthropic-ai/claude-code
