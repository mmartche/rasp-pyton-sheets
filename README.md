# rasp-pyton-sheets
raspberry pyton google sheets

* with screen
python3 -m venv venv
source venv/bin/activate
pip install -r requirements-dev.txt
python3 index.py

* run auth_setup.py to generate oauth token json

* with systemd
sudo nano /etc/systemd/system/telegram-bot.service

sudo systemctl daemon-reload
sudo systemctl enable telegram-bot
sudo systemctl start telegram-bot

status:
systemctl status telegram-bot

Stop:
sudo systemctl stop telegram-bot

Reset (when updaate):
sudo systemctl restart telegram-bot

Logs real time:
journalctl -u telegram-bot -f