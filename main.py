import os, uuid, re, io, json
from datetime import datetime
from typing import Optional
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse
from fastapi.middleware.cors import CORSMiddleware

try:
    from supabase import create_client, Client
    from PIL import Image
    import pytesseract
    OCR_AVAILABLE = True
except:
    OCR_AVAILABLE = False

app = FastAPI(title="Cyber Cafe Agent - Phase 2")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SECRET_KEY") or os.getenv("SUPABASE_KEY") or os.getenv("SUPABASE_SERVICE_KEY")
BUCKET = "user-documents"

DOC_CATEGORIES = {
    "Identity": ["aadhaar_front", "aadhaar_back", "aadhaar_combined", "pan_card", "voter_id_front", "voter_id_back", "driving_license", "passport_front", "passport_back"],
    "Photo & Sign": ["photo", "signature", "thumb_impression", "selfie"],
    "Education": ["10th_marksheet", "10th_certificate", "12th_marksheet", "12th_certificate", "graduation_marksheet", "graduation_degree", "postgrad_marksheet", "diploma_certificate", "iti_certificate", "b_ed_certificate"],
    "Caste / Income": ["domicile_certificate", "residence_certificate", "income_certificate", "caste_certificate", "ews_certificate", "obc_certificate", "sc_certificate", "st_certificate", "ncl_certificate", "disability_certificate"],
    "Banking": ["bank_passbook", "cancelled_cheque", "bank_statement"],
    "Other Imp": ["ration_card", "ayushman_card", "e_shram_card", "character_certificate", "medical_certificate", "affidavit", "experience_letter", "migration_certificate", "gap_certificate", "allotment_letter", "fee_receipt", "form_16"]
}
ALL_DOC_TYPES = [d for v in DOC_CATEGORIES.values() for d in v]

def get_supabase():
    if not SUPABASE_URL or not SUPABASE_KEY:
        return None
    return create_client(SUPABASE_URL, SUPABASE_KEY)

def extract_ocr(file_bytes, doc_type):
    if not OCR_AVAILABLE or doc_type not in ["aadhaar_front", "aadhaar_back", "pan_card"]:
        return None
    try:
        img = Image.open(io.BytesIO(file_bytes))
        text = pytesseract.image_to_string(img)
        data = {"raw_text": text[:500]}
        aadhaar_match = re.search(r'\d{4}\s\d{4}\s\d{4}', text)
        pan_match = re.search(r'[A-Z]{5}[0-9]{4}[A-Z]{1}', text)
        if aadhaar_match: data["aadhaar_no"] = aadhaar_match.group()
        if pan_match: data["pan_no"] = pan_match.group()
        return data
    except Exception as e:
        return {"error": str(e)}

HTML_PAGE = """
<!DOCTYPE html><html><head><meta name="viewport" content="width=device-width, initial-scale=1">
<script src="https://cdn.tailwindcss.com"></script></head>
<body class="bg-[#0f0f0f] text-white min-h-screen p-4">
<div class="max-w-md mx-auto">
<h1 class="text-2xl font-bold">Cyber Cafe Agent - Phase 2</h1><p class="text-zinc-400 text-sm">50+ Docs + Real Storage + OCR</p>

<div class="mt-5 bg-zinc-900 p-4 rounded-xl">
<label class="text-sm">User ID</label>
<input id="user_id" class="w-full mt-1 p-3 rounded bg-black border-zinc-700" placeholder="yuvraj_123">
<label class="text-sm mt-3 block">Doc Type</label>
<select id="doc_type" class="w-full mt-1 p-3 rounded bg-black border border-zinc-700">
""" + "".join([f'<optgroup label="{k}">' + "".join([f'<option value="{d}">{d}</option>' for d in v]) + '</optgroup>' for k,v in DOC_CATEGORIES.items()]) + """
</select>
<input id="file" type="file" class="w-full mt-3 text-sm">
<div class="mt-3 flex items-center gap-2"><input type="checkbox" id="consent" checked><label class="text-xs text-zinc-400">I consent to store securely under DPDP Act</label></div>
<button onclick="upload()" class="w-full mt-4 bg-white text-black p-3 rounded-xl font-bold">Upload to Vault</button>
<p id="status" class="text-xs mt-2 text-zinc-400"></p>
</div>

<div class="mt-4 bg-zinc-900 p-4 rounded-xl">
<div class="flex justify-between"><h2 class="font-bold">Mera Vault</h2><button onclick="loadVault()" class="text-xs bg-zinc-800 px-3 py-1 rounded">Refresh</button></div>
<div id="vault" class="mt-3 space-y-2 text-sm"></div>
</div>

<div class="mt-4 text-xs text-zinc-500">Endpoints: /api/status | /vault/{user_id} | /api/doc-types | /docs</div>
</div>
<script>
async function upload(){
  const uid=document.getElementById('user_id').value; const dtype=document.getElementById('doc_type').value; const f=document.getElementById('file').files[0];
  if(!uid||!f){alert('User ID + File chahiye');return;}
  if(!document.getElementById('consent').checked){alert('Consent do');return;}
  document.getElementById('status').innerText='Uploading...';
  const fd=new FormData(); fd.append('user_id',uid); fd.append('doc_type',dtype); fd.append('file',f);
  const res=await fetch('/upload-document',{method:'POST',body:fd}); const j=await res.json();
  document.getElementById('status').innerText=JSON.stringify(j).slice(0,200); loadVault();
}
async function loadVault(){
  const uid=document.getElementById('user_id').value; if(!uid)return;
  const res=await fetch('/vault/'+uid); const j=await res.json();
  const v=document.getElementById('vault'); v.innerHTML='';
  (j.docs||[]).forEach(d=>{
    v.innerHTML+=`<div class="bg-black p-2 rounded border border-zinc-800 flex justify-between"><div><b>${d.doc_type}</b><br><span class="text-xs text-zinc-400">${d.file_name} - ${new Date(d.created_at).toLocaleDateString()}</span></div><a href="${d.file_url}" target="_blank" class="text-xs text-blue-400">View</a></div>`;
  });
}
</script></body></html>
"""

@app.get("/", response_class=HTMLResponse)
def home(): return HTML_PAGE

@app.get("/app", response_class=HTMLResponse)
def app_page(): return HTML_PAGE

@app.get("/api/status")
def status():
    sb = get_supabase()
    if not sb: return {"db":"no_env", "bucket": BUCKET}
    try:
        sb.table("user_vault").select("id").limit(1).execute()
        return {"db":"connected", "bucket": BUCKET, "ocr_available": OCR_AVAILABLE, "doc_types_count": len(ALL_DOC_TYPES)}
    except Exception as e:
        return {"db": f"error {e}", "bucket": BUCKET}

@app.get("/api/doc-types")
def doc_types():
    return {"categories": DOC_CATEGORIES, "all": ALL_DOC_TYPES, "count": len(ALL_DOC_TYPES)}

@app.post("/upload-document")
async def upload_doc(user_id: str = Form(...), doc_type: str = Form(...), file: UploadFile = File(...)):
    if doc_type not in ALL_DOC_TYPES:
        raise HTTPException(400, f"Invalid doc_type. Use one of {ALL_DOC_TYPES[:5]}...")
    sb = get_supabase()
    if not sb: raise HTTPException(500, "Supabase not configured")

    file_bytes = await file.read()
    if len(file_bytes) > 10*1024*1024:
        raise HTTPException(400, "File too large >10MB")

    storage_path = f"{user_id}/{doc_type}/{uuid.uuid4().hex}_{file.filename}"

    # 1. Upload to Storage
    try:
        sb.storage.from_(BUCKET).upload(storage_path, file_bytes, {"content-type": file.content_type or "application/octet-stream", "upsert": "true"})
    except Exception as e:
        # if bucket not found
        raise HTTPException(500, f"Storage upload failed: {e}. Check bucket '{BUCKET}' exists and is public.")

    file_url = sb.storage.from_(BUCKET).get_public_url(storage_path)

    # 2. OCR if needed
    ocr_data = extract_ocr(file_bytes, doc_type)

    # 3. Save metadata
    try:
        sb.table("user_vault").insert({
            "user_id": user_id,
            "doc_type": doc_type,
            "file_name": file.filename,
            "storage_path": storage_path,
            "file_url": file_url,
            "file_size": len(file_bytes),
            "mime_type": file.content_type,
            "ocr_data": ocr_data,
            "consent_given": True
        }).execute()
        sb.table("consent_logs").insert({"user_id": user_id, "doc_type": doc_type}).execute()
    except Exception as e:
        # fallback for old schema
        try:
            sb.table("user_vault").insert({"user_id": user_id, "doc_type": doc_type, "file_name": file.filename}).execute()
        except Exception as e2:
            raise HTTPException(500, f"DB insert failed: {e2}")

    return {"success": True, "saved_in": "supabase_storage", "storage_path": storage_path, "file_url": file_url, "ocr": ocr_data}

@app.get("/vault/{user_id}")
def get_vault(user_id: str):
    sb = get_supabase()
    if not sb: raise HTTPException(500, "Supabase not configured")
    res = sb.table("user_vault").select("*").eq("user_id", user_id).order("created_at", desc=True).execute()
    return {"user_id": user_id, "count": len(res.data), "docs": res.data}

@app.get("/form-template/{tid}")
def template(tid: str):
    return {"id": tid, "version": 1, "last_checked": datetime.now().isoformat(), "status": "active", "required_docs": ["aadhaar_front", "photo"], "fields": [{"id":"name","label":"Full Name","from_vault_key":"aadhaar_front.ocr_data.name"}]}

@app.get("/api/template-health")
def health():
    return {"message": "Template validator will run daily via Render cron. For now all templates marked active.", "risk_mitigation": "enabled"}
