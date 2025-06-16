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
    

def get_latest_group_id(supabase_url, api_key, jwt, table_name="order_groups"):
    url = f"{supabase_url}/rest/v1/{table_name}"
    headers = {
        "apikey": api_key,
        "Authorization": f"Bearer {jwt}",
        "Content-Type": "application/json",
    }
    
    params = {
        "select": "group_id",
        "order": "group_id.desc",
        "limit": 1
    }

    response = requests.get(url, headers=headers, params=params)

    if response.status_code == 200:
        results = response.json()
        if results:
            return results[0].get("group_id", 0)
        else:
            return 1
    else:
        print(f"❌ Failed to fetch latest group_id ({response.status_code}): {response.text}")
        return 0

