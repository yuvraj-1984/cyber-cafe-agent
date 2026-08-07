import os
from fastapi import FastAPI, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI(title="Cyber Cafe Agent - Vault - Permanent")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

supabase = None
try:
    from supabase import create_client
    URL = os.getenv("SUPABASE_URL")
    KEY = os.getenv("SUPABASE_SECRET_KEY") or os.getenv("SUPABASE_KEY")
    if URL and KEY:
        supabase = create_client(URL, KEY)
except Exception as e:
    print(e)

@app.get("/")
def home():
    return {"status": "Cyber Cafe Agent Running", "vault_ready": True, "db": "connected" if supabase else "not configured"}

@app.post("/upload-document")
async def upload_doc(user_id: str = Form(...), doc_type: str = Form(...), file: UploadFile = File(...)):
    if supabase:
        try:
            supabase.table("user_vault").insert({"user_id": user_id, "doc_type": doc_type, "file_name": file.filename}).execute()
            return {"success": True, "msg": f"{doc_type} permanent save ho gaya", "saved_in": "supabase"}
        except Exception as e:
            return {"success": False, "error": str(e)}
    return {"success": False, "msg": "DB not connected"}

@app.get("/vault/{user_id}")
def get_vault(user_id: str):
    if supabase:
        res = supabase.table("user_vault").select("*").eq("user_id", user_id).execute()
        return {"user_id": user_id, "docs": res.data, "source": "supabase"}
    return {"user_id": user_id, "docs": []}

@app.get("/form-template/army-agniveer")
def get_army_template():
    return {"form_name": "ARMY Agniveer", "fields": [{"id": "candidate_name", "from_vault": "aadhaar_name"}], "official_url": "https://joinindianarmy.nic.in"}   
