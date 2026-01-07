
import requests

def update_vercel_api(public_url: str, serial: int = 1):
    """
    Sends PUT request to Vercel Mongo API
    """
    vercel_api_url = f"https://project-vercel-msg.vercel.app/update/{serial}"

    payload = {
        "message_content": public_url
    }

    try:
        resp = requests.put(vercel_api_url, json=payload, timeout=10)
        resp.raise_for_status()
        print("✅ Vercel API updated successfully")
        print("📦 Response:", resp.json())
    except Exception as e:
        print("❌ Failed to update Vercel API:", e)
