import os, uuid, re, io
from datetime import datetime
from fastapi import FastAPI, UploadFile, File, Form, BackgroundTasks, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from supabase import create_client

try:
    from PIL import Image
    import pytesseract
    OCR_AVAILABLE = True
except:
    OCR_AVAILABLE = False

app = FastAPI(title="Cyber Cafe Agent - Phase 4B")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SECRET_KEY") or os.getenv("SUPABASE_KEY")
BUCKET = "user-documents"

DOC_CATEGORIES = {
    "Identity": ["aadhaar_front", "aadhaar_back", "aadhaar_combined", "pan_card", "voter_id_front"],
    "Photo & Sign": ["photo", "signature", "selfie"],
    "Education": ["10th_marksheet", "12th_marksheet", "graduation_marksheet", "graduation_degree"],
    "Caste/Income": ["domicile_certificate", "income_certificate", "caste_certificate", "ews_certificate"],
    "Bank/Other": ["bank_passbook", "ration_card"]
}

TEMPLATES = {
    "aadhaar_correction": {"name":"Aadhaar Correction","category":"correction","required_docs":["aadhaar_front","photo"]},
    "pan_new": {"name":"PAN New","category":"new","required_docs":["aadhaar_front","photo","signature"]},
    "pan_correction": {"name":"PAN Correction","category":"correction","required_docs":["aadhaar_front","pan_card","photo"]},
    "income_certificate": {"name":"Income Certificate UP","category":"certificate","required_docs":["aadhaar_front","ration_card","bank_passbook","photo"]},
    "domicile_certificate": {"name":"Domicile / Niwas","category":"certificate","required_docs":["aadhaar_front","ration_card","photo"]},
    "caste_certificate": {"name":"Caste Certificate","category":"certificate","required_docs":["aadhaar_front","caste_certificate","photo"]},
    "ews_new": {"name":"EWS Certificate","category":"certificate","required_docs":["aadhaar_front","income_certificate","photo"]},
    "voter_new": {"name":"Voter ID New","category":"new","required_docs":["aadhaar_front","photo","signature"]},
    "passport_new": {"name":"Passport New","category":"new","required_docs":["aadhaar_front","pan_card","bank_passbook","photo"]},
    "ayushman_new": {"name":"Ayushman Card","category":"new","required_docs":["aadhaar_front","ration_card","photo"]},
    "ration_new": {"name":"Ration Card New","category":"new","required_docs":["aadhaar_front","income_certificate","photo"]},
    "ssc_gd": {"name":"SSC GD 2025","category":"exam","required_docs":["aadhaar_front","10th_certificate","photo","signature"]},
    "ssc_cgl": {"name":"SSC CGL 2025","category":"exam","required_docs":["aadhaar_front","graduation_marksheet","photo","signature"]},
    "up_police_constable": {"name":"UP Police Constable","category":"exam","required_docs":["aadhaar_front","12th_marksheet","photo","signature","domicile_certificate"]},
    "up_police_si": {"name":"UP Police SI","category":"exam","required_docs":["aadhaar_front","graduation_degree","domicile_certificate","photo","signature"]},
    "railway_group_d": {"name":"Railway Group D","category":"exam","required_docs":["aadhaar_front","10th_certificate","photo","signature","caste_certificate"]},
    "cuet_ug": {"name":"CUET UG 2025","category":"exam","required_docs":["aadhaar_front","12th_marksheet","photo","signature"]},
    "nda": {"name":"NDA 2025","category":"exam","required_docs":["aadhaar_front","12th_marksheet","photo","signature"]},
    "ibps_po": {"name":"IBPS PO","category":"exam","required_docs":["aadhaar_front","graduation_degree","photo","signature","bank_passbook"]},
    "up_scholarship": {"name":"UP Scholarship","category":"scholarship","required_docs":["aadhaar_front","income_certificate","10th_marksheet","bank_passbook","photo"]},
}

def get_sb():
    return create_client(SUPABASE_URL, SUPABASE_KEY) if SUPABASE_URL and SUPABASE_KEY else None

def extract_ocr(file_bytes, doc_type):
    if doc_type not in ["aadhaar_front","aadhaar_back","aadhaar_combined","pan_card"]:
        return None
    try:
        import pytesseract
        pytesseract.pytesseract.tesseract_cmd = "/usr/bin/tesseract"
        img = Image.open(io.BytesIO(file_bytes))
        if img.width > 1200:
            w = 1200 / float(img.width)
            h = int(float(img.height) * w)
            img = img.resize((1200, h))
        img = img.convert('L')
        text = pytesseract.image_to_string(img, config='--oem 3 --psm 6')
        data = {}
        aadhaar = re.search(r'\d{4}\s\d{4}\s\d{4}', text)
        pan = re.search(r'[A-Z]{5}[0-9]{4}[A-Z]{1}', text)
        if aadhaar: data["aadhaar_no"] = aadhaar.group()
        if pan: data["pan_no"] = pan.group()
        return data if data else {"raw_text": text[:150]}
    except Exception as e:
        print(f"OCR err: {e}")
        return None

def do_ocr_background(record_id, file_bytes, doc_type):
    try:
        ocr = extract_ocr(file_bytes, doc_type)
        if ocr:
            sb = get_sb()
            sb.table("user_vault").update({"ocr_data": ocr}).eq("id", record_id).execute()
            print(f"OCR done for {record_id}: {ocr}")
    except Exception as e:
        print(f"BG OCR fail {record_id}: {e}")

# HTML with Category Filter
TEMPLATES_JSON = str(list(TEMPLATES.items())).replace("'", '"') # not used, we build JS manually

HTML_PAGE = """
<!DOCTYPE html><html><head><meta name="viewport" content="width=device-width, initial-scale=1"><script src="https://cdn.tailwindcss.com"></script></head>
<body class="bg-[#0f0f0f] text-white p-3"><div class="max-w-md mx-auto">
<h1 class="text-xl font-bold">Cyber Cafe Agent - Phase 4B</h1><p class="text-[11px] text-zinc-400">Fast Upload + Category + Background OCR</p>

<div class="mt-3 bg-zinc-900 p-3 rounded-xl">
<input id="user_id" value="yuvraj_test" class="w-full p-2 rounded bg-black text-sm border border-zinc-800">
<div class="flex gap-1 mt-2 overflow-x-auto text-[10px] pb-1">
<button onclick="filterCat('all')" class="cat-btn bg-white text-black px-3 py-1 rounded-full font-bold" data-cat="all">All</button>
<button onclick="filterCat('exam')" class="cat-btn bg-zinc-800 px-3 py-1 rounded-full" data-cat="exam">Exam</button>
<button onclick="filterCat('certificate')" class="cat-btn bg-zinc-800 px-3 py-1 rounded-full" data-cat="certificate">Certificate</button>
<button onclick="filterCat('new')" class="cat-btn bg-zinc-800 px-3 py-1 rounded-full" data-cat="new">New ID</button>
<button onclick="filterCat('correction')" class="cat-btn bg-zinc-800 px-3 py-1 rounded-full" data-cat="correction">Correction</button>
<button onclick="filterCat('scholarship')" class="cat-btn bg-zinc-800 px-3 py-1 rounded-full" data-cat="scholarship">Scholarship</button>
</div>
<select id="template" class="w-full mt-2 p-2 rounded bg-black text-sm border border-zinc-800"></select>
<button onclick="checkFill()" class="w-full mt-2 bg-blue-600 p-2 rounded text-sm font-bold">Check Docs & Preview</button>
<div id="preview" class="mt-2 text-xs bg-black p-2 rounded min-h-[50px] border border-zinc-800"></div>
</div>

<div class="mt-3 bg-zinc-900 p-3 rounded-xl">
<h2 class="text-sm font-bold">Upload (Fast)</h2>
<select id="doc_type" class="w-full mt-2 p-2 rounded bg-black text-sm border border-zinc-800">
<option>aadhaar_front</option><option>aadhaar_back</option><option>pan_card</option><option>photo</option><option>signature</option><option>10th_marksheet</option><option>income_certificate</option><option>domicile_certificate</option><option>bank_passbook</option><option>caste_certificate</option>
</select>
<input id="file" type="file" class="w-full mt-2 text-xs">
<button onclick="upload()" class="w-full mt-2 bg-white text-black p-2 rounded font-bold text-sm">Upload Fast</button>
<p id="status" class="text-[11px] mt-1 text-zinc-400"></p>
</div>

<div class="mt-3 bg-zinc-900 p-3 rounded-xl">
<div class="flex justify-between"><h2 class="text-sm font-bold">Mera Vault (Auto)</h2><button onclick="loadVault()" class="text-[10px] bg-zinc-800 px-2 py-1 rounded">Refresh</button></div>
<div id="vault" class="mt-2 space-y-2 text-xs"></div>
</div>

</div>
<script>
const TEMPLATES = {
  "aadhaar_correction": {"name":"Aadhaar Correction","category":"correction","required_docs":["aadhaar_front","photo"]},
  "pan_new": {"name":"PAN New","category":"new","required_docs":["aadhaar_front","photo","signature"]},
  "pan_correction": {"name":"PAN Correction","category":"correction","required_docs":["aadhaar_front","pan_card","photo"]},
  "income_certificate": {"name":"Income Certificate UP","category":"certificate","required_docs":["aadhaar_front","ration_card","bank_passbook","photo"]},
  "domicile_certificate": {"name":"Domicile / Niwas","category":"certificate","required_docs":["aadhaar_front","ration_card","photo"]},
  "caste_certificate": {"name":"Caste Certificate","category":"certificate","required_docs":["aadhaar_front","caste_certificate","photo"]},
  "ews_new": {"name":"EWS Certificate","category":"certificate","required_docs":["aadhaar_front","income_certificate","photo"]},
  "voter_new": {"name":"Voter ID New","category":"new","required_docs":["aadhaar_front","photo","signature"]},
  "passport_new": {"name":"Passport New","category":"new","required_docs":["aadhaar_front","pan_card","bank_passbook","photo"]},
  "ayushman_new": {"name":"Ayushman Card","category":"new","required_docs":["aadhaar_front","ration_card","photo"]},
  "ration_new": {"name":"Ration Card New","category":"new","required_docs":["aadhaar_front","income_certificate","photo"]},
  "ssc_gd": {"name":"SSC GD 2025","category":"exam","required_docs":["aadhaar_front","10th_certificate","photo","signature"]},
  "ssc_cgl": {"name":"SSC CGL 2025","category":"exam","required_docs":["aadhaar_front","graduation_marksheet","photo","signature"]},
  "up_police_constable": {"name":"UP Police Constable","category":"exam","required_docs":["aadhaar_front","12th_marksheet","photo","signature","domicile_certificate"]},
  "up_police_si": {"name":"UP Police SI","category":"exam","required_docs":["aadhaar_front","graduation_degree","domicile_certificate","photo","signature"]},
  "railway_group_d": {"name":"Railway Group D","category":"exam","required_docs":["aadhaar_front","10th_certificate","photo","signature","caste_certificate"]},
  "cuet_ug": {"name":"CUET UG 2025","category":"exam","required_docs":["aadhaar_front","12th_marksheet","photo","signature"]},
  "nda": {"name":"NDA 2025","category":"exam","required_docs":["aadhaar_front","12th_marksheet","photo","signature"]},
  "ibps_po": {"name":"IBPS PO","category":"exam","required_docs":["aadhaar_front","graduation_degree","photo","signature","bank_passbook"]},
  "up_scholarship": {"name":"UP Scholarship","category":"scholarship","required_docs":["aadhaar_front","income_certificate","10th_marksheet","bank_passbook","photo"]}
};

function filterCat(cat){
  document.querySelectorAll('.cat-btn').forEach(b=>{b.className='cat-btn bg-zinc-800 px-3 py-1 rounded-full';});
  document.querySelector(`[data-cat="${cat}"]`).className='cat-btn bg-white text-black px-3 py-1 rounded-full font-bold';
  const sel=document.getElementById('template'); sel.innerHTML='';
  Object.entries(TEMPLATES).forEach(([k,v])=>{
    if(cat==='all' || v.category===cat){
      const o=document.createElement('option'); o.value=k; o.textContent=v.name; sel.appendChild(o);
    }
  });
}

async function upload(){
  const uid=document.getElementById('user_id').value;
  const dtype=document.getElementById('doc_type').value;
  const f=document.getElementById('file').files[0];
  if(!uid||!f){alert('File select kar');return;}
  const fd=new FormData(); fd.append('user_id',uid); fd.append('doc_type',dtype); fd.append('file',f);
  document.getElementById('status').innerText='Uploading... (2 sec)';
  try{
    const r=await fetch('/upload-document',{method:'POST',body:fd});
    const j=await r.json();
    if(j.success){
      document.getElementById('status').innerText='✅ Uploaded! OCR background me chal raha hai, 30 sec baad Refresh dabana';
      loadVault();
      setTimeout(loadVault, 30000);
      setTimeout(loadVault, 60000);
    }else{document.getElementById('status').innerText='Fail: '+(j.error||'unknown');}
  }catch(e){document.getElementById('status').innerText='Network error, fir try kar';}
}

async function loadVault(){
  const uid=document.getElementById('user_id').value; if(!uid)return;
  const v=document.getElementById('vault'); v.innerHTML='Loading...';
  const r=await fetch('/vault/'+uid); const j=await r.json();
  v.innerHTML='';
  (j.docs||[]).forEach(d=>{
    let ocrTxt='';
    if(d.ocr_data){
      if(d.ocr_data.aadhaar_no) ocrTxt=`<span class="text-green-400">Aadhaar:${d.ocr_data.aadhaar_no}</span>`;
      else if(d.ocr_data.pan_no) ocrTxt=`<span class="text-green-400">PAN:${d.ocr_data.pan_no}</span>`;
      else if(d.ocr_data.status==='processing') ocrTxt=`<span class="text-yellow-400">OCR processing...</span>`;
    }
    v.innerHTML+=`<div class="bg-black p-2 rounded border border-zinc-800"><div class="flex justify-between"><b>${d.doc_type}</b><a href="${d.file_url}" target="_blank" class="text-blue-400">View</a></div><div class="text-[10px] text-zinc-500">${d.file_name||''}<br>${ocrTxt}</div></div>`;
  });
}

async function checkFill(){
  const uid=document.getElementById('user_id').value;
  const tid=document.getElementById('template').value;
  const r=await fetch(`/api/fill-preview/${tid}/${uid}`); const j=await r.json();
  let h=`<b>${j.template_name}</b><br><span class="text-zinc-400">Need: ${j.required_docs.join(', ')}</span><br><br>`;
  if(j.missing.length>0) h+=`<span class="text-red-400">❌ Missing: ${j.missing.join(', ')}</span>`;
  else h+=`<span class="text-green-400 font-bold">✅ All Docs Ready - Apply kar sakte ho</span>`;
  h+=`<br><br><span class="text-zinc-500">You have: ${j.you_have.join(', ')||'none'}</span>`;
  document.getElementById('preview').innerHTML=h;
}

window.addEventListener('load', ()=>{filterCat('all'); setTimeout(loadVault, 1000);});
</script></body></html>
"""

@app.get("/", response_class=HTMLResponse)
def home(): return HTML_PAGE

@app.get("/api/status")
def status():
    return {"templates": len(TEMPLATES), "ocr_available": OCR_AVAILABLE, "mode": "Phase 4B Fast"}

@app.post("/upload-document")
async def upload_doc(background_tasks: BackgroundTasks, user_id: str = Form(...), doc_type: str = Form(...), file: UploadFile = File(...)):
    sb = get_sb()
    if not sb:
        raise HTTPException(500, "DB not configured")
    data = await file.read()
    path = f"{user_id}/{doc_type}/{uuid.uuid4().hex}_{file.filename}"
    sb.storage.from_(BUCKET).upload(path, data, {"content-type": file.content_type, "upsert":"true"})
    url = sb.storage.from_(BUCKET).get_public_url(path)
    try:
        ins = sb.table("user_vault").insert({"user_id": user_id,"doc_type": doc_type,"file_name": file.filename,"storage_path": path,"file_url": url,"file_size": len(data),"mime_type": file.content_type,"ocr_data": {"status":"processing"},"consent_given": True}).execute()
        rec_id = ins.data[0]["id"] if ins.data else None
    except Exception as e:
        # fallback if id column not exist
        ins = sb.table("user_vault").insert({"user_id": user_id,"doc_type": doc_type,"file_name": file.filename,"file_url": url,"ocr_data": {"status":"processing"}}).execute()
        rec_id = ins.data[0].get("id") if ins.data else None

    if rec_id:
        background_tasks.add_task(do_ocr_background, rec_id, data, doc_type)
    return {"success": True, "file_url": url, "ocr_status": "processing", "record_id": rec_id}

@app.get("/vault/{user_id}")
def vault(user_id: str):
    sb = get_sb()
    res = sb.table("user_vault").select("*").eq("user_id", user_id).order("created_at", desc=True).execute()
    return {"user_id": user_id, "count": len(res.data), "docs": res.data}

@app.get("/api/fill-preview/{template_id}/{user_id}")
def fill_preview(template_id: str, user_id: str):
    if template_id not in TEMPLATES:
        raise HTTPException(404, "Template not found")
    tpl = TEMPLATES[template_id]
    sb = get_sb()
    res = sb.table("user_vault").select("doc_type").eq("user_id", user_id).execute()
    you_have = list(set([r["doc_type"] for r in res.data]))
    missing = [d for d in tpl["required_docs"] if d not in you_have]
    return {"template_name": tpl["name"], "category": tpl["category"], "required_docs": tpl["required_docs"], "you_have": you_have, "missing": missing}
