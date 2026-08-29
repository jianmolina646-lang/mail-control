from __future__ import annotations

import os

import httpx


def main() -> None:
    response = httpx.post(
        "https://login.microsoftonline.com/5aff66d8-2602-46c4-9aa1-7137fab89f87/oauth2/v2.0/token",
        data={
            "client_id": os.environ["MICROSOFT_CLIENT_ID"],
            "client_secret": os.environ["MICROSOFT_CLIENT_SECRET"],
            "grant_type": "client_credentials",
            "scope": "https://graph.microsoft.com/.default",
        },
        timeout=10,
    )
    payload = response.json()
    description = str(payload.get("error_description", ""))
    print(f"status={response.status_code}")
    print(f"error={payload.get('error', '')}")
    print(f"error_codes={payload.get('error_codes', [])}")
    print(f"description_code={description.split(':', 1)[0]}")
    print(f"client_secret_valid={response.status_code == 200}")


if __name__ == "__main__":
    main()
