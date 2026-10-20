import httpx
from app.config import settings

def notify_reception_whatsapp_sync(appt_id: int, name: str, phone: str, service: str, slot: str) -> bool:
    """
    Sends WhatsApp message via Meta WhatsApp Business Cloud API.
    Silently no-ops if credentials are not configured.
    """
    if not (settings.WHATSAPP_TOKEN and settings.WHATSAPP_PHONE_ID and settings.WHATSAPP_RECEPTION_NUMBER):
        return False

    url = f"https://graph.facebook.com/v20.0/{settings.WHATSAPP_PHONE_ID}/messages"
    body_text = (
        f"📋 *New Appointment at Dar ul Shifa*\n\n"
        f"• *Ref #:* {appt_id}\n"
        f"• *Patient:* {name}\n"
        f"• *Phone:* {phone}\n"
        f"• *Service:* {service}\n"
        f"• *Slot:* {slot}\n\n"
        f"Please confirm with patient."
    )
    payload = {
        "messaging_product": "whatsapp",
        "to": settings.WHATSAPP_RECEPTION_NUMBER,
        "type": "text",
        "text": {"body": body_text},
    }
    headers = {
        "Authorization": f"Bearer {settings.WHATSAPP_TOKEN}",
        "Content-Type": "application/json",
    }
    try:
        with httpx.Client(timeout=2.0) as client:
            resp = client.post(url, json=payload, headers=headers)
            return resp.status_code == 200
    except Exception:
        return False

async def notify_reception_whatsapp(appt_id: int, name: str, phone: str, service: str, slot: str) -> bool:
    """Async variant for background tasks."""
    if not (settings.WHATSAPP_TOKEN and settings.WHATSAPP_PHONE_ID and settings.WHATSAPP_RECEPTION_NUMBER):
        return False

    url = f"https://graph.facebook.com/v20.0/{settings.WHATSAPP_PHONE_ID}/messages"
    body_text = (
        f"📋 *New Appointment at Dar ul Shifa*\n\n"
        f"• *Ref #:* {appt_id}\n"
        f"• *Patient:* {name}\n"
        f"• *Phone:* {phone}\n"
        f"• *Service:* {service}\n"
        f"• *Slot:* {slot}"
    )
    payload = {
        "messaging_product": "whatsapp",
        "to": settings.WHATSAPP_RECEPTION_NUMBER,
        "type": "text",
        "text": {"body": body_text},
    }
    headers = {
        "Authorization": f"Bearer {settings.WHATSAPP_TOKEN}",
        "Content-Type": "application/json",
    }
    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            resp = await client.post(url, json=payload, headers=headers)
            return resp.status_code == 200
    except Exception:
        return False
