#!/usr/bin/env python3
"""
🔥 MONGODB ATLAS DATABASE SETUP
Creates admin/parent accounts automatically
"""

import pymongo
from werkzeug.security import generate_password_hash
from datetime import datetime
import sys, os

# 🔥 ATLAS CONNECTION - UPDATE YOUR DETAILS!
MONGODB_URI = "mongodb+srv://c2admin:8JYJY3x3YDE3LFsZ@parentalcontrolc2.psjbmud.mongodb.net/?appName=ParentalControlC2"

try:
    # Connect to Atlas
    print("☁️ Connecting to MongoDB Atlas...")
    client = pymongo.MongoClient(MONGODB_URI)
    client.admin.command('ping')  # Test connection
    db = client['ParentalControlC2']
    print("✅ ATLAS CONNECTION SUCCESS!")
    
    # Collections
    admins = db['admins']
    parents = db['parents']
    
    # 🔥 CREATE ADMIN ACCOUNT
    admin_exists = admins.find_one({'email': 'admin@control.com'})
    if not admin_exists:
        admins.insert_one({
            'email': 'admin@control.com',
            'password': generate_password_hash('admin123'),
            'role': 'admin',
            'created': datetime.now()
        })
        print("👨‍💼 ADMIN CREATED: admin@control.com / admin123")
    else:
        print("👨‍💼 Admin already exists")
    
    # 🔥 CREATE PARENT ACCOUNT
    parent_exists = parents.find_one({'email': 'parent@test.com'})
    if not parent_exists:
        parents.insert_one({
            'email': 'parent@test.com',
            'password': generate_password_hash('parent123'),
            'role': 'parent',
            'children': [],
            'created': datetime.now()
        })
        print("👨‍👩‍👧 PARENT CREATED: parent@test.com / parent123")
    else:
        print("👨‍👩‍👧 Parent already exists")
    
    # Test collections
    print(f"📊 Collections ready:")
    print(f"   - admins: {admins.count_documents({})}")
    print(f"   - parents: {parents.count_documents({})}")
    
    print("\n✅ CLOUD DATABASE SETUP COMPLETE!")
    print("🌐 Login: http://localhost:5000/admin/login")
    
except Exception as e:
    print(f"❌ ATLAS ERROR: {e}")
    print("\n🔧 FIX:")
    print("1. Update MONGODB_URI with YOUR Atlas connection string")
    print("2. Check Network Access: 0.0.0.0/0")
    print("3. Verify username/password")