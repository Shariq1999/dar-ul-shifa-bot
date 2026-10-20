import os
from dotenv import load_dotenv

load_dotenv()

class Settings:
    CLINIC_NAME: str = os.getenv("CLINIC_NAME", "Dar ul Shifa Diagnostic Center")
    CLINIC_PHONE: str = os.getenv("CLINIC_PHONE", "+91-22-23456789")
    CLINIC_WHATSAPP: str = os.getenv("CLINIC_WHATSAPP", "+91-9876543210")
    CLINIC_ADDRESS: str = os.getenv("CLINIC_ADDRESS", "Ground Floor, Dar ul Shifa Clinic, Mumbai, Maharashtra")
    CLINIC_TIMINGS: str = os.getenv("CLINIC_TIMINGS", "Monday to Saturday: 7:30 AM – 9:00 PM | Sunday: 8:00 AM – 2:00 PM")
    DB_PATH: str = os.getenv("DB_PATH", "darulshifa.db")
    HIGH_CONFIDENCE_THRESHOLD: float = 0.70
    CLARIFICATION_THRESHOLD: float = 0.70

    # Reception Notification Gateways
    TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
    TELEGRAM_RECEPTION_CHAT_ID: str = os.getenv("TELEGRAM_RECEPTION_CHAT_ID", "")
    WHATSAPP_TOKEN: str = os.getenv("WHATSAPP_TOKEN", "")
    WHATSAPP_PHONE_ID: str = os.getenv("WHATSAPP_PHONE_ID", "")
    WHATSAPP_RECEPTION_NUMBER: str = os.getenv("WHATSAPP_RECEPTION_NUMBER", "")

settings = Settings()
