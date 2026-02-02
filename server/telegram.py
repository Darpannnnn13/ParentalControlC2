#!/usr/bin/env python3
"""
🤖 TEST YOUR BOT TOKEN
"""

from server.config import TELEGRAM_BOT_TOKEN, ADMIN_CHAT_ID
import requests

def test_bot():
    url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/getMe"
    resp = requests.get(url).json()
    
    if resp['ok']:
        bot_info = resp['result']
        print(f"✅ BOT ACTIVE!")
        print(f"   Name: {bot_info['first_name']}")
        print(f"   Username: @{bot_info['username']}")
        
        # Test message
        send_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
        data = {
            'chat_id': ADMIN_CHAT_ID,
            'text': '🚀 C2 Bot Test - Atlas Multi-Tenant Ready!'
        }
        send_resp = requests.post(send_url, data=data).json()
        
        if send_resp['ok']:
            print("✅ MESSAGE SENT TO YOUR CHAT!")
        else:
            print(f"❌ Chat ID Error: {ADMIN_CHAT_ID}")
            print("🔧 Fix: Get Chat ID from @userinfobot")
    else:
        print("❌ BOT TOKEN INVALID!")

if __name__ == "__main__":
    test_bot()