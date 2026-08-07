import os, uuid, re, io, json
from datetime import datetime
from fastapi import FastAPI, UploadFile, File, Form, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from supabase import create_client

app = FastAPI(title="Cyber Cafe Agent - Phase 3")
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
ALL_DOC_TYPES = [d for v in DOC_CATEGORIES.values() for d in v]

# 10 REAL TEMPLATES - Yahi se 200+ banenge
TEMPLATES = {
    "aadhaar_correction": {"name":"Aadhaar Correction","category":"correction","official_url":"https://myaadhaar.uidai.gov.in/","required_docs":["aadhaar_front","photo"],"fields":[{"id":"full_name","label":"Full Name (Aadhaar ke hisab se)","from_vault":"aadhaar_front","required":True},{"id":"dob","label":"DOB","from_vault":"aadhaar_front","required":True}]},
    "pan_new": {"name":"PAN New","category":"new","official_url":"https://www.tin-nsdl.com/","required_docs":["aadhaar_front","photo","signature"],"fields":[{"id":"name","label":"Name","from_vault":"aadhaar_front"},{"id":"father_name","label":"Father Name","from_vault":"10th_certificate"}]},
    "income_certificate": {"name":"Income Certificate UP","category":"certificate","official_url":"https://edistrict.up.gov.in/","required_docs":["aadhaar_front","ration_card","bank_passbook","photo"],"fields":[{"id":"income","label":"Annual Income"},{"id":"district","label":"District"}]},
    "domicile_certificate": {"name":"Domicile / Niwas","category":"certificate","official_url":"https://edistrict.up.gov.in/","required_docs":["aadhaar_front","ration_card","photo"],"fields":[{"id":"address","label":"Full Address","from_vault":"aadhaar_front"}]},
    "caste_certificate": {"name":"Caste Certificate","category":"certificate","official_url":"https://edistrict.up.gov.in/","required_docs":["aadhaar_front","caste_certificate","photo"],"fields":[]},
    "ssc_gd": {"name":"SSC GD 2025","category":"exam","official_url":"https://ssc.nic.in/","required_docs":["aadhaar_front","10th_certificate","photo","signature"],"fields":[{"id":"name","label":"Name"},{"id":"10th_roll","label":"10th Roll No"}]},
    "up_police_constable": {"name":"UP Police Constable","category":"exam","official_url":"https://uppb.gov.in/","required_docs":["aadhaar_front","12th_marksheet","photo","signature","domicile_certificate"],"fields":[]},
    "up_scholarship": {"name":"UP Scholarship","category":"scholarship","official_url":"https://scholarship.up.gov.in/","required_docs":["aadhaar_front","income_certificate","10th_marksheet","bank_passbook","photo"],"fields":[]},
    "voter_new": {"name":"Voter ID New","category":"new","official_url":"https://voters.eci.gov.in/","required_docs":["aadhaar_front","photo","signature"],"fields":[]},
    "ration_new": {"name":"Ration Card New","category":"new","official_url":"https://fcs.up.gov.in/","required_docs":["aadhaar_front","income_certificate","photo"],"fields":[]},
    "ssc_cgl": {"name":"SSC CGL 2025","category":"exam","official_url":"https://ssc.nic.in/","required_docs":["aadhaar_front","graduation_marksheet","photo","signature"],"fields":[]},
    "railway_group_d": {"name":"Railway Group D","category":"exam","official_url":"https://rrbcdg.gov.in/","required_docs":["aadhaar_front","10th_certificate","photo","signature","caste_certificate"],"fields":[]},
    "cuet_ug": {"name":"CUET UG 2025","category":"exam","official_url":"https://cuet.samarth.ac.in/","required_docs":["aadhaar_front","12th_marksheet","photo","signature"],"fields":[]},
    "nda": {"name":"NDA 2025","category":"exam","official_url":"https://upsc.gov.in/","required_docs":["aadhaar_front","12th_marksheet","photo","signature"],"fields":[]},
    "ibps_po": {"name":"IBPS PO","category":"exam","official_url":"https://ibps.in/","required_docs":["aadhaar_front","graduation_degree","photo","signature","bank_passbook"],"fields":[]},
    "passport_new": {"name":"Passport New","category":"new","official_url":"https://portal2.passportindia.gov.in/","required_docs":["aadhaar_front","pan_card","bank_passbook","photo"],"fields":[]},
    "ews_new": {"name":"EWS Certificate","category":"certificate","official_url":"https://edistrict.up.gov.in/","required_docs":["aadhaar_front","income_certificate","photo"],"fields":[]},
    "pan_correction": {"name":"PAN Correction","category":"correction","official_url":"https://www.tin-nsdl.com/","required_docs":["aadhaar_front","pan_card","photo"],"fields":[]},
    "up_police_si": {"name":"UP Police SI","category":"exam","official_url":"https://uppbpb.gov.in/","required_docs":["aadhaar_front","graduation_degree","domicile_certificate","photo","signature"],"fields":[]},
    "ayushman_new": {"name":"Ayushman Card","category":"new","official_url":"https://beneficiary.nha.gov.in/","required_docs":["aadhaar_front","ration_card","photo"],"fields":[]}
}

def get_sb(): return create_client(SUPABASE_URL, SUPABASE_KEY) if SUPABASE_URL and SUPABASE_KEY else None

HTML_PAGE = """
<!DOCTYPE html><html><head><meta name="viewport" content="width=device-width, initial-scale=1"><script src="https://cdn.tailwindcss.com"></script></head>
<body class="bg-[#0f0f0f] text-white p-4"><div class="max-w-md mx-auto">
<h1 class="text-xl font-bold">Cyber Cafe Agent - Phase 3</h1><p class="text-xs text-zinc-400">Vault + 10 Templates + Auto-Check</p>
<div class="mt-4 bg-zinc-900 p-3 rounded-xl">
<input id="user_id" value="yuvraj_test" class="w-full p-2 rounded bg-black text-sm" placeholder="User ID">
<select id="doc_type" class="w-full mt-2 p-2 rounded bg-black text-sm">""" + "".join([f'<optgroup label="{k}">'+ "".join([f'<option>{d}</option>' for d in v]) +'</optgroup>' for k,v in DOC_CATEGORIES.items()]) + """</select>
<input id="file" type="file" class="w-full mt-2 text-xs"><button onclick="upload()" class="w-full mt-2 bg-white text-black p-2 rounded font-bold text-sm">Upload</button><p id="status" class="text-[10px] mt-1"></p></div>
<div class="mt-3 bg-zinc-900 p-3 rounded-xl"><h2 class="text-sm font-bold">Intent Selector - Kya Banana Hai?</h2><select id="template" class="w-full mt-2 p-2 rounded bg-black text-sm">""" + "".join([f'<option value="{k}">{v["name"]} - {v["category"]}</option>' for k,v in TEMPLATES.items()]) + """</select>
<button onclick="checkFill()" class="w-full mt-2 bg-blue-600 p-2 rounded text-sm font-bold">Check Required Docs & Auto-Fill Preview</button>
<div id="preview" class="mt-2 text-xs bg-black p-2 rounded"></div></div>
<div class="mt-3 bg-zinc-900 p-3 rounded-xl"><div class="flex justify-between"><h2 class="text-sm font-bold">Mera Vault</h2><button onclick="loadVault()" class="text-[10px] bg-zinc-800 px-2 py-1 rounded">Refresh</button></div><div id="vault" class="mt-2 space-y-1 text-xs"></div></div>
</div>
<script>
async function upload(){const uid=document.getElementById('user_id').value;const dtype=document.getElementById('doc_type').value;const f=document.getElementById('file').files[0];if(!uid||!f){alert('ID+File');return;}const fd=new FormData();fd.append('user_id',uid);fd.append('doc_type',dtype);fd.append('file',f);document.getElementById('status').innerText='Uploading...';const r=await fetch('/upload-document',{method:'POST',body:fd});const j=await r.json();document.getElementById('status').innerText=j.success?'Uploaded: '+j.file_url.slice(0,40):JSON.stringify(j);loadVault();}
async function loadVault(){const uid=document.getElementById('user_id').value;const r=await fetch('/vault/'+uid);const j=await r.json();const v=document.getElementById('vault');v.innerHTML='';(j.docs||[]).forEach(d=>{v.innerHTML+=`<div class="flex justify-between bg-black p-1 rounded"><span>${d.doc_type}</span><a href="${d.file_url}" target="_blank" class="text-blue-400">View</a></div>`});}
async function checkFill(){const uid=document.getElementById('user_id').value;const tid=document.getElementById('template').value;const r=await fetch(`/api/fill-preview/${tid}/${uid}`);const j=await r.json();let h=`<b>${j.template_name}</b><br>Required: ${j.required_docs.join(', ')}<br><br>`;if(j.missing.length>0){h+=`<span class="text-red-400">Missing: ${j.missing.join(', ')}</span>`}else{h+=`<span class="text-green-400">All Docs OK - Ready for Auto-Fill</span>`}h+=`<br><br>Vault Docs You Have: ${j.you_have.join(', ')||'None'}`;document.getElementById('preview').innerHTML=h;}
</script></body></html>
"""

@app.get("/", response_class=HTMLResponse)
def home(): return HTML_PAGE

@app.get("/api/status")
def status():
    sb=get_sb()
    try: sb.table("user_vault").select("id").limit(1).execute(); db="connected"
    except: db="error"
    return {"db":db,"bucket":BUCKET,"templates":len(TEMPLATES),"doc_types":len(ALL_DOC_TYPES)}

@app.get("/api/doc-types")
def doc_types(): return DOC_CATEGORIES

@app.get("/api/templates")
def list_templates(): return TEMPLATES

@app.post("/upload-document")
async def upload_doc(user_id: str = Form(...), doc_type: str = Form(...), file: UploadFile = File(...)):
    sb=get_sb()
    data=await file.read()
    path=f"{user_id}/{doc_type}/{uuid.uuid4().hex}_{file.filename}"
    try: sb.storage.from_(BUCKET).upload(path, data, {"content-type": file.content_type, "upsert":"true"})
    except Exception as e: raise HTTPException(500, f"Storage fail {e}")
    url=sb.storage.from_(BUCKET).get_public_url(path)
    try: sb.table("user_vault").insert({"user_id":user_id,"doc_type":doc_type,"file_name":file.filename,"storage_path":path,"file_url":url,"file_size":len(data),"mime_type":file.content_type,"consent_given":True}).execute()
    except: sb.table("user_vault").insert({"user_id":user_id,"doc_type":doc_type,"file_name":file.filename}).execute()
    return {"success":True,"file_url":url}

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
    return {"template_id":template_id,"template_name":tpl["name"],"official_url":tpl["official_url"],"required_docs":tpl["required_docs"],"you_have":you_have,"missing":missing,"can_auto_fill":len(missing)==0,"next_step":"Captcha + Payment only" if len(missing)==0 else f"Upload missing: {', '.join(missing)}"}
