from fastapi import FastAPI, UploadFile
from fastapi.middleware.cors import CORSMiddleware
import os

app = FastAPI(title="Cyber Cafe Agent - Vault")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

USER_VAULT = {}

@app.get("/")
def home():
    return {"status": "Cyber Cafe Agent Running", "vault_ready": True}

@app.post("/upload-document")
async def upload_doc(user_id: str, doc_type: str, file: UploadFile):
    if user_id not in USER_VAULT:
        USER_VAULT[user_id] = {}
    USER_VAULT[user_id][doc_type] = file.filename
    return {"success": True, "msg": f"{doc_type} save ho gaya"}

@app.get("/form-template/army-agniveer")
def get_army_template():
    return {
        "form_name": "ARMY Agniveer",
        "fields": [
            {"id": "candidate_name", "from_vault": "aadhaar_name"},
            {"id": "father_name", "from_vault": "father_name"},
            {"id": "dob", "from_vault": "dob"},
            {"id": "aadhaar_no", "from_vault": "aadhaar_no"}
        ],
        "official_url": "https://joinindianarmy.nic.in"
    }

@app.get("/vault/{user_id}")
def get_vault(user_id: str):
    return USER_VAULT.get(user_id, {})
