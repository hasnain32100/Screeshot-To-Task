import os
from dotenv import load_dotenv

load_dotenv()

key = os.getenv("OPENAI_API_KEY")

if key:
    print("✅ API key loaded successfully!")
else:
    print("❌ API key was not found.")