import os
import requests
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
CHAT_ID = os.getenv("TELEGRAM_CHAT_ID")

def test_telegram():
    print(f"Testing Telegram Configuration...")
    print(f"Bot Token: {BOT_TOKEN[:10]}...{BOT_TOKEN[-5:] if BOT_TOKEN else 'None'}")
    print(f"Chat ID: {CHAT_ID}")

    if not BOT_TOKEN or not CHAT_ID:
        print("❌ Error: Missing configuration.")
        return

    url = f"https://api.telegram.org/bot{BOT_TOKEN}/sendMessage"
    payload = {
        "chat_id": CHAT_ID,
        "text": "🔔 Test message from Website Monitor",
        "parse_mode": "Markdown"
    }

    try:
        print("\nSending request...")
        response = requests.post(url, json=payload, timeout=10)
        print(f"Status Code: {response.status_code}")
        print(f"Response: {response.text}")

        if response.status_code == 200:
            print("\n✅ Success! Message sent.")
        elif response.status_code == 403:
            print("\n❌ Error 403: Forbidden.")
            print("Possible causes:")
            print("1. You haven't started the bot yet.")
            print("   -> Go to your bot and click 'Start'.")
            print("2. You blocked the bot.")
            print("   -> Unblock it and click 'Start'.")
            print("3. The Chat ID is incorrect.")
            print("   -> Run 'python get_chat_id.py' again.")
        else:
            print(f"\n❌ Error: {response.status_code}")
            
    except Exception as e:
        print(f"\n❌ Exception: {e}")

if __name__ == "__main__":
    test_telegram()
