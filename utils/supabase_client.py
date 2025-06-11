import requests
import time

def log_into_supabase(data, supabase_url, api_key, jwt, table_name="order_groups"):
    
    url = f"{supabase_url}/rest/v1/{table_name}"
    headers = {
        "apikey": api_key,
        "Authorization": f"Bearer {jwt}",
        "Content-Type": "application/json",
        "Prefer": "return=representation"
    }

    response = requests.post(url, headers=headers, json=data)

    if response.status_code in (200, 201):
        print("✅ Successfully logged data:", response.json())
        return response.json()
    else:
        print(f"❌ Failed to log data ({response.status_code}): {response.text}")
        return {"error": response.text, "status_code": response.status_code}

