# JobRadar - Telegram AI-Recruiter

An AI-powered Telegram bot that automates job searching by parsing public Telegram channels, matching vacancies against your profile and filters using an LLM (Pydantic AI), and sending relevant job notifications directly to you.

## Features
- **Security:** Strict allowlist (only the admin can use the bot).
- **Automated Parsing:** Incremental and backfill parsing of public Telegram channels (without using user accounts).
- **AI Matching:** Uses Pydantic AI to evaluate the relevance of a vacancy to your resume and filters.
- **Automated Pipeline:** Scheduled tasks (Collect -> Analyze -> Notify) via APScheduler.
- **VPS Ready:** Designed to be run as a `systemd` daemon on a Linux VPS using SQLite.

## Deployment on Ubuntu VPS

### 1. Initial Setup
SSH into your VPS and install dependencies:
```bash
sudo apt update
sudo apt install python3 python3-venv python3-pip sqlite3 git -y
```

### 2. Clone the Repository
```bash
cd /opt
sudo git clone <YOUR_REPO_URL> JobRadar
sudo chown -R $USER:$USER /opt/JobRadar
cd /opt/JobRadar
```

### 3. Setup Virtual Environment
```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 4. Configuration
Copy the example environment file and fill in your details:
```bash
cp .env.example .env
nano .env
```
Ensure you set:
- `BOT_TOKEN`: Your Telegram Bot Token.
- `ADMIN_TG_ID`: Your Telegram User ID.
- `LLM_API_KEY`: Your OpenRouter (or other provider) API Key.

Set file permissions to protect secrets:
```bash
chmod 600 .env
```

### 5. Setup Systemd Service
Copy the provided service file to the systemd directory:
```bash
sudo cp recruiter-bot.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now recruiter-bot
```

### 6. Verification & Logs
Check if the bot is running:
```bash
sudo systemctl status recruiter-bot
```

View the logs:
```bash
journalctl -u recruiter-bot -f
```

## Database Backups
A script `backup.py` is included to safely backup the SQLite database.
You can run it manually:
```bash
python backup.py
```
Or set it up via `crontab` to run daily.
