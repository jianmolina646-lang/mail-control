import os

EXPECTED_CLIENT_ID = "f92cc133-7233-4765-92db-ebab4df86c2c"

print(
    "MICROSOFT_APP_ID_MATCH="
    + str(os.environ.get("MICROSOFT_CLIENT_ID", "").strip().lower() == EXPECTED_CLIENT_ID)
)
