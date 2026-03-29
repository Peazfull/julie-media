"""
Upload vers Google Drive via OAuth2.
Pour le MVP : si gcp_credentials.json est vide ou absent, la fonction
retourne un flag `not_configured` sans lever d'exception.
"""
import json
import os
from pathlib import Path

CREDENTIALS_PATH = Path(__file__).parent.parent / "secrets" / "gcp_credentials.json"
DRIVE_FOLDER_NAME = "Carrousels TDAH"
SCOPES = ["https://www.googleapis.com/auth/drive.file"]


def is_drive_configured() -> bool:
    """Retourne True si le fichier credentials GCP est rempli."""
    if not CREDENTIALS_PATH.exists():
        return False
    try:
        data = json.loads(CREDENTIALS_PATH.read_text())
        return bool(data)
    except Exception:
        return False


def _get_or_create_folder(service, folder_name: str) -> str:
    """Retourne l'id du dossier Drive, le crée s'il n'existe pas."""
    query = (
        f"name='{folder_name}' and mimeType='application/vnd.google-apps.folder' "
        "and trashed=false"
    )
    results = service.files().list(q=query, fields="files(id, name)").execute()
    files = results.get("files", [])
    if files:
        return files[0]["id"]

    meta = {
        "name": folder_name,
        "mimeType": "application/vnd.google-apps.folder",
    }
    folder = service.files().create(body=meta, fields="id").execute()
    return folder["id"]


def upload_carousel(png_paths: list, carousel_id: str) -> dict:
    """
    Upload les PNG dans Drive/Carrousels TDAH/{carousel_id}/.
    Retourne {"status": "ok", "folder_id": ..., "file_ids": [...]}
    ou       {"status": "not_configured"}
    ou       {"status": "error", "message": ...}
    """
    if not is_drive_configured():
        return {"status": "not_configured"}

    try:
        from google.oauth2.credentials import Credentials
        from google_auth_oauthlib.flow import InstalledAppFlow
        from googleapiclient.discovery import build
        from googleapiclient.http import MediaFileUpload
        import pickle

        token_path = Path(__file__).parent.parent / "secrets" / "token.pickle"

        creds = None
        if token_path.exists():
            with open(token_path, "rb") as f:
                creds = pickle.load(f)

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                from google.auth.transport.requests import Request
                creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(
                    str(CREDENTIALS_PATH), SCOPES
                )
                creds = flow.run_local_server(port=0)
            with open(token_path, "wb") as f:
                import pickle as _p
                _p.dump(creds, f)

        service = build("drive", "v3", credentials=creds)

        root_folder_id = _get_or_create_folder(service, DRIVE_FOLDER_NAME)
        sub_folder_id = _get_or_create_folder(service, carousel_id)

        file_ids = []
        for path in png_paths:
            file_meta = {"name": Path(path).name, "parents": [sub_folder_id]}
            media = MediaFileUpload(path, mimetype="image/png")
            uploaded = (
                service.files()
                .create(body=file_meta, media_body=media, fields="id")
                .execute()
            )
            file_ids.append(uploaded["id"])

        return {"status": "ok", "folder_id": sub_folder_id, "file_ids": file_ids}

    except Exception as exc:
        return {"status": "error", "message": str(exc)}
