import os
import time
import requests
from dotenv import load_dotenv

load_dotenv()

BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")

def get_chat_id():
    if not BOT_TOKEN:
        print("Error: BOT_TOKEN not found in .env")
        return

    # 1. Verify Bot Identity
    try:
        me_url = f"https://api.telegram.org/bot{BOT_TOKEN}/getMe"
        me_response = requests.get(me_url)
        me_data = me_response.json()
        
        if not me_data.get("ok"):
            print(f"❌ Error: Invalid Bot Token. Telegram said: {me_data.get('description')}")
            return
            
        bot_user = me_data.get("result", {})
        bot_username = bot_user.get("username")
        first_name = bot_user.get("first_name")
        
        print(f"🤖 Bot Identity Verified: {first_name} (@{bot_username})")
        print(f"👉 Please make sure you are messaging this specific bot: https://t.me/{bot_username}")
        
    except Exception as e:
        print(f"❌ Error connecting to Telegram: {e}")
        return

    # 2. Get Updates
    print("\n🕵️  Waiting for a message from YOU to the bot...")
    print(f"👉  Go to Telegram, open @{bot_username}, and send: Hello")
    print("    (I will wait for 60 seconds...)")
    
    start_time = time.time()
    while time.time() - start_time < 60:
        try:
            url = f"https://api.telegram.org/bot{BOT_TOKEN}/getUpdates"
            response = requests.get(url)
            data = response.json()
            
            if data.get("ok"):
                results = data.get("result", [])
                if results:
                    # Look for the last message from a 'private' chat (usually the user)
                    for update in reversed(results):
                        message = update.get("message", {})
                        chat = message.get("chat", {})
                        
                        if chat.get("type") == "private":
                            chat_id = chat.get("id")
                            user = chat.get("username")
                            name = chat.get("first_name")
                            
                            print(f"\n✅ FOUND IT! Your Personal Chat ID is: {chat_id}")
                            print(f"   (This is DIFFERENT from the Bot ID)")
                            print(f"   User: {name} (@{user})")
                            
                            # Automatically update .env if found
                            # We can't easily overwrite .env safely here without regex, but we can print it clearly.
                            return chat_id
                        
            print(".", end="", flush=True)
            time.sleep(2)
            
        except Exception as e:
            print(f"Error: {e}")
            time.sleep(2)
            
    print("\n\n❌ Time out. I didn't see any new messages.")
    print("Make sure you are sending a message to the verified Bot Username above.")
    return None

if __name__ == "__main__":
    get_chat_id()
