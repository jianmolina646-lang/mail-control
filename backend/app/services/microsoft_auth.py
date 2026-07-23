import imaplib
import msal

CLIENT_ID = "04b07795-8ddb-461a-bbee-02f9e1bf7b46"
SCOPES = ["https://outlook.office365.com/IMAP.AccessAsUser.All", "offline_access"]

def iniciar_autenticacion():
    app = msal.PublicClientApplication(
        CLIENT_ID, 
        authority="https://login.microsoftonline.com/common"
    )

    flow = app.initiate_device_flow(scopes=SCOPES)
    
    print("\n" + "=" * 60)
    print(flow["message"])
    print("=" * 60 + "\n")

    result = app.acquire_token_by_device_flow(flow)

    if "access_token" in result:
        access_token = result["access_token"]
        refresh_token = result.get("refresh_token")
        email = result.get("id_token_claims", {}).get("preferred_username")
        
        print(f"¡Éxito! Cuenta conectada: {email}")
        print(f"Refresh Token: {refresh_token}")
        return access_token, refresh_token
    else:
        print("Error:", result.get("error_description"))
        return None, None

if name == "main":
    iniciar_autenticacion()
