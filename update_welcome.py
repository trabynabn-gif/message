"""One-time helper to update the bot's welcome message in users.json."""

import json
from pathlib import Path

MESSAGE = Path(__file__).with_name("welcome_message.txt").read_text(encoding="utf-8")
DATA_PATH = Path(__file__).with_name("users.json")

with DATA_PATH.open("r", encoding="utf-8") as file:
    data = json.load(file)

data["welcome_msg"] = MESSAGE

with DATA_PATH.open("w", encoding="utf-8") as file:
    json.dump(data, file, ensure_ascii=False, indent=4)
    file.write("\n")

print("Welcome message updated in users.json")
