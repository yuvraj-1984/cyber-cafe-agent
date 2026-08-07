import os, uuid, re, io
from datetime import datetime
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from supabase import create_client

try:
    from PIL import Image
    import pytesseract
    OCR_AVAILABLE = True
except:
    OCR_AVAILABLE = False

app = FastAPI(title="Cyber Cafe Agent - Phase 4A OCR")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SECRET_KEY") or os.getenv("SUPABASE_KEY")
BUCKET = "user-documents"

DOC_CATEGORIES = {
    "Identity": ["aadhaar_front", "aadhaar_back", "aadhaar_combined", "pan_card", "voter_id_front", "voter_id_back", "driving_license", "passport_front", "passport_back"],
    "Photo & Sign": ["photo", "signature", "thumb_impression", "selfie"],
    "Education": ["10th_marksheet", "10th_certificate", "12th_marksheet", "12th_certificate", "graduation_marksheet", "graduation_degree", "postgrad_marksheet", "diploma_certificate", "iti_certificate"],
    "Caste/Income": ["domicile_certificate", "income_certificate", "caste_certificate", "ews_certificate", "obc_certificate", "sc_certificate", "ncl_certificate"],
    "Bank/Other": ["bank_passbook", "cancelled_cheque", "ration_card", "ayushman_card", "e_shram_card", "character_certificate", "medical_certificate"]
}

TEMPLATES = {
    "aadhaar_correction": {"name":"Aadhaar Correction","category":"correction","official_url":"https://myaadhaar.uidai.gov.in/","required_docs":["aadhaar_front","photo"]},
    "pan_new": {"name":"PAN New","category":"new","official_url":"https://www.tin-nsdl.com/","required_docs":["aadhaar_front","photo","signature"]},
    "income_certificate": {"name":"Income Certificate UP","category":"certificate","official_url":"https://edistrict.up.gov.in/","required_docs":["aadhaar_front","ration_card","bank_passbook","photo"]},
    "domicile_certificate": {"name":"Domicile / Niwas","category":"certificate","official_url":"https://edistrict.up.gov.in/","required_docs":["aadhaar_front","ration_card","photo"]},
    "caste_certificate": {"name":"Caste Certificate","category":"certificate","official_url":"https://edistrict.up.gov.in/","required_docs":["aadhaar_front","caste_certificate","photo"]},
    "ssc_gd": {"name":"SSC GD 2025","category":"exam","official_url":"https://ssc.nic.in/","required_docs":["aadhaar_front","10th_certificate","photo","signature"]},
    "up_police_constable": {"name":"UP Police Constable","category":"exam","official_url":"https://uppb.gov.in/","required_docs":["aadhaar_front","12th_marksheet","photo","signature","domicile_certificate"]},
    "up_scholarship": {"name":"UP Scholarship","category":"scholarship","official_url":"https://scholarship.up.gov.in/","required_docs":["aadhaar_front","income_certificate","10th_marksheet","bank_passbook","photo"]},
    "voter_new": {"name":"Voter ID New","category":"new","official_url":"https://voters.eci.gov.in/","required_docs":["aadhaar_front","photo","signature"]},
    "ration_new": {"name":"Ration Card New","category":"new","official_url":"https://fcs.up.gov.in/","required_docs":["aadhaar_front","income_certificate","photo"]},
    "ssc_cgl": {"name":"SSC CGL 2025","category":"exam","official_url":"https://ssc.nic.in/","required_docs":["aadhaar_front","graduation_marksheet","photo","signature"]},
    "railway_group_d": {"name":"Railway Group D","category":"exam","official_url":"https://rrbcdg.gov.in/","required_docs":["aadhaar_front","10th_certificate","photo","signature","caste_certificate"]},
    "cuet_ug": {"name":"CUET UG 2025","category":"exam","official_url":"https://cuet.samarth.ac.in/","required_docs":["aadhaar_front","12th_marksheet","photo","signature"]},
    "nda": {"name":"NDA 2025","category":"exam","official_url":"https://upsc.gov.in/","required_docs":["aadhaar_front","12th_marksheet","photo","signature"]},
    "ibps_po": {"name":"IBPS PO","category":"exam","official_url":"https://ibps.in/","required_docs":["aadhaar_front","graduation_degree","photo","signature","bank_passbook"]},
    "passport_new": {"name":"Passport New","category":"new","official_url":"https://portal2.passportindia.gov.in/","required_docs":["aadhaar_front","pan_card","bank_passbook","photo"]},
    "ews_new": {"name":"EWS Certificate","category":"certificate","official_url":"https://edistrict.up.gov.in/","required_docs":["aadhaar_front","income_certificate","photo"]},
    "pan_correction": {"name":"PAN Correction","category":"correction","official_url":"https://www.tin-nsdl.com/","required_docs":["aadhaar_front","pan_card","photo"]},
    "up_police_si": {"name":"UP Police SI","category":"exam","official_url":"https://uppbpb.gov.in/","required_docs":["aadhaar_front","graduation_degree","domicile_certificate","photo","signature"]},
    "ayushman_new": {"name":"Ayushman Card","category":"new","official_url":"https://beneficiary.nha.gov.in/","required_docs":["aadhaar_front","ration_card","photo"]}
}

def get_sb(): return create_client(SUPABASE_URL, SUPABASE_KEY) if SUPABASE_URL and SUPABASE_KEY else None

def extract_ocr(file_bytes, doc_type):
    if not OCR_AVAILABLE:
        return {"error": "ocr_lib_not_found"}
    if doc_type not in ["aadhaar_front", "aadhaar_back", "aadhaar_combined", "pan_card", "10th_marksheet", "12th_marksheet"]:
        return None
    try:
        img = Image.open(io.BytesIO(file_bytes))
        # thoda resize for better OCR
        if img.width < 1000:
            img = img.resize((img.width*2, img.height*2))
        text = pytesseract.image_to_string(img, lang='eng')
        data = {"raw_text": text[:1000]}
        aadhaar = re.search(r'\d{4}\s\d{4}\s\d{4}', text)
        pan = re.search(r'[A-Z]{5}[0-9]{4}[A-Z]{1}', text)
        if aadhaar: data["aadhaar_no"] = aadhaar.group()
        if pan: data["pan_no"] = pan.group()
        # DOB try
        dob = re.search(r'\d{2}/\d{2}/\d{4}', text)
        if dob: data["dob"] = dob.group()
        return data
    except Exception as e:
        return {"error": str(e)[:200]}

HTML_PAGE = """
<!DOCTYPE html><html><head><meta name="viewport" content="width=device-width, initial-scale=1"><script src="https://cdn.tailwindcss.com"></script></head>
<body class="bg-[#0f0f0f] text-white p-4"><div class="max-w-md mx-auto">
<h1 class="text-xl font-bold">Cyber Cafe Agent - Phase 4A</h1><p class="text-xs text-zinc-400">20 Templates + Auto Vault + OCR Enabled</p>
<div class="mt-4 bg-zinc-900 p-3 rounded-xl">
<input id="user_id" value="yuvraj_test" class="w-full p-2 rounded bg-black text-sm">
<select id="doc_type" class="w-full mt-2 p-2 rounded bg-black text-sm"><option>aadhaar_front</option><option>pan_card</option><option>photo</option><option>signature</option><option>10th_marksheet</option><option>12th_marksheet</option><option>income_certificate</option><option>domicile_certificate</option><option>bank_passbook</option></select>
<input id="file" type="file" class="w-full mt-2 text-xs"><button onclick="upload()" class="w-full mt-2 bg-white text-black p-2 rounded font-bold text-sm">Upload + OCR</button><p id="status" class="text-[10px] mt-1 text-zinc-400"></p></div>
<div class="mt-3 bg-zinc-900 p-3 rounded-xl"><h2 class="text-sm font-bold">Intent Selector</h2><select id="template" class="w-full mt-2 p-2 rounded bg-black text-sm">""" + "".join([f'<option value="{k}">{v["name"]}</option>' for k,v in TEMPLATES.items()]) + """</select>
<button onclick="checkFill()" class="w-full mt-2 bg-blue-600 p-2 rounded text-sm font-bold">Check Docs & Preview</button><div id="preview" class="mt-2 text-xs bg-black p-2 rounded min-h-[60px]"></div></div>
<div class="mt-3 bg-zinc-900 p-3 rounded-xl"><div class="flex justify-between"><h2 class="text-sm font-bold">Mera Vault (Auto Load)</h2><button onclick="loadVault()" class="text-[10px] bg-zinc-800 px-2 py-1 rounded">Refresh</button></div><div id="vault" class="mt-2 space-y-1 text-xs"></div></div>
</div>
<script>
async function upload(){const uid=document.getElementById('user_id').value;const dtype=document.getElementById('doc_type').value;const f=document.getElementById('file').files[0];if(!uid||!f){alert('ID+File');return;}const fd=new FormData();fd.append('user_id',uid);fd.append('doc_type',dtype);fd.append('file',f);document.getElementById('status').innerText='Uploading + OCR running...';const r=await fetch('/upload-document',{method:'POST',body:fd});const j=await r.json();document.getElementById('status').innerText=j.success? 'Uploaded + OCR: '+(j.ocr? JSON.stringify(j.ocr).slice(0,100) : 'No OCR') : 'Fail';loadVault();}
async function loadVault(){const uid=document.getElementById('user_id').value;if(!uid)return;const v=document.getElementById('vault');v.innerHTML='Loading...';const r=await fetch('/vault/'+uid);const j=await r.json();v.innerHTML='';(j.docs||[]).forEach(d=>{let ocrInfo=d.ocr_data && d.ocr_data.aadhaar_no? 'Aadhaar:'+d.ocr_data.aadhaar_no : (d.ocr_data && d.ocr_data.pan_no? 'PAN:'+d.ocr_data.pan_no : '');v.innerHTML+=`<div class="bg-black p-2 rounded border border-zinc-800"><div class="flex justify-between"><b>${d.doc_type}</b><a href="${d.file_url}" target="_blank" class="text-blue-400">View</a></div><div class="text-[10px] text-zinc-500">${d.file_name||''} ${ocrInfo? '<br><span class=text-green-400>'+ocrInfo+'</span>':''}</div></div>`});}
async function checkFill(){const uid=document.getElementById('user_id').value;const tid=document.getElementById('template').value;const r=await fetch(`/api/fill-preview/${tid}/${uid}`);const j=await r.json();let h=`<b>${j.template_name}</b><br>Req: ${j.required_docs.join(', ')}<br><br>`;if(j.missing.length>0){h+=`<span class="text-red-400">Missing: ${j.missing.join(', ')}</span>`}else{h+=`<span class="text-green-400 font-bold">✓ All Docs OK - Ready</span>`}h+=`<br><br>Have: ${j.you_have.join(', ')}`;document.getElementById('preview').innerHTML=h;}
window.addEventListener('load', ()=>{setTimeout(loadVault, 1200);});
</script></body></html>
"""

@app.get("/", response_class=HTMLResponse)
def home(): return HTML_PAGE

@app.get("/api/status")
def status():
    return {"db":"connected","bucket":BUCKET,"templates":len(TEMPLATES),"ocr_available":OCR_AVAILABLE,"ocr_binary":"installed_via_dockerfile"}

@app.post("/upload-document")
async def upload_doc(user_id: str = Form(...), doc_type: str = Form(...), file: UploadFile = File(...)):
    sb=get_sb()
    data=await file.read()
    path=f"{user_id}/{doc_type}/{uuid.uuid4().hex}_{file.filename}"
    sb.storage.from_(BUCKET).upload(path, data, {"content-type": file.content_type, "upsert":"true"})
    url=sb.storage.from_(BUCKET).get_public_url(path)
    ocr = extract_ocr(data, doc_type)
    try:
        sb.table("user_vault").insert({"user_id":user_id,"doc_type":doc_type,"file_name":file.filename,"storage_path":path,"file_url":url,"file_size":len(data),"mime_type":file.content_type,"ocr_data":ocr,"consent_given":True}).execute()
    except:
        sb.table("user_vault").insert({"user_id":user_id,"doc_type":doc_type,"file_name":file.filename,"file_url":url,"ocr_data":ocr}).execute()
    return {"success":True,"file_url":url,"ocr":ocr}

@app.get("/vault/{user_id}")
def vault(user_id: str):
    sb=get_sb()
    res=sb.table("user_vault").select("*").eq("user_id",user_id).order("created_at",desc=True).execute()
    return {"user_id":user_id,"count":len(res.data),"docs":res.data}

@app.get("/api/fill-preview/{template_id}/{user_id}")
def fill_preview(template_id: str, user_id: str):
    if template_id not in TEMPLATES: raise HTTPException(404,"Template not found")
    tpl=TEMPLATES[template_id]
    sb=get_sb()
    res=sb.table("user_vault").select("doc_type").eq("user_id",user_id).execute()
    you_have=list(set([r["doc_type"] for r in res.data]))
    missing=[d for d in tpl["required_docs"] if d not in you_have]
    return {"template_name":tpl["name"],"required_docs":tpl["required_docs"],"you_have":you_have,"missing":missing}
