import os, uuid, re, io
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

app = FastAPI(title="Cyber Cafe Agent - Phase 4C")
app.add_middleware(CORSMiddleware, allow_origins=["*"], allow_methods=["*"], allow_headers=["*"])

SUPABASE_URL = os.getenv("SUPABASE_URL")
SUPABASE_KEY = os.getenv("SUPABASE_SECRET_KEY") or os.getenv("SUPABASE_KEY")
BUCKET = "user-documents"

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
  "up_scholarship": {"name":"UP Scholarship","category":"scholarship","required_docs":["aadhaar_front","income_certificate","10th_marksheet","bank_passbook","photo"]}
}
OFFICIAL_URLS = {
 "aadhaar_correction":"https://myaadhaar.uidai.gov.in/","pan_new":"https://www.tin-nsdl.com/services/pan/","pan_correction":"https://www.tin-nsdl.com/services/pan/","income_certificate":"https://edistrict.up.gov.in/","domicile_certificate":"https://edistrict.up.gov.in/","caste_certificate":"https://edistrict.up.gov.in/","ews_new":"https://edistrict.up.gov.in/","voter_new":"https://voters.eci.gov.in/","passport_new":"https://portal2.passportindia.gov.in/","ayushman_new":"https://beneficiary.nha.gov.in/","ration_new":"https://fcs.up.gov.in/","ssc_gd":"https://ssc.nic.in/","ssc_cgl":"https://ssc.nic.in/","up_police_constable":"https://uppbpb.gov.in/","up_police_si":"https://uppbpb.gov.in/","railway_group_d":"https://www.rrbcdg.gov.in/","cuet_ug":"https://cuet.samarth.ac.in/","nda":"https://www.upsc.gov.in/","ibps_po":"https://www.ibps.in/","up_scholarship":"https://scholarship.up.gov.in/"
}

def get_sb():
    return create_client(SUPABASE_URL, SUPABASE_KEY) if SUPABASE_URL and SUPABASE_KEY else None

def extract_ocr(file_bytes, doc_type):
    if doc_type not in ["aadhaar_front","aadhaar_back","aadhaar_combined","pan_card"]: return None
    try:
        import pytesseract
        pytesseract.pytesseract.tesseract_cmd = "/usr/bin/tesseract"
        img = Image.open(io.BytesIO(file_bytes))
        if img.width > 1200:
            w = 1200 / float(img.width); h = int(float(img.height) * w)
            img = img.resize((1200, h))
        img = img.convert('L')
        text = pytesseract.image_to_string(img, config='--oem 3 --psm 6')
        data = {}
        aadhaar = re.search(r'\d{4}\s\d{4}\s\d{4}', text)
        pan = re.search(r'[A-Z]{5}[0-9]{4}[A-Z]{1}', text)
        if aadhaar: data["aadhaar_no"] = aadhaar.group()
        if pan: data["pan_no"] = pan.group()
        return data if data else None
    except: return None

def do_ocr_background(record_id, file_bytes, doc_type):
    try:
        ocr = extract_ocr(file_bytes, doc_type)
        if ocr:
            sb = get_sb()
            sb.table("user_vault").update({"ocr_data": ocr}).eq("id", record_id).execute()
    except: pass

HTML_PAGE = """
<!DOCTYPE html><html><head><meta name="viewport" content="width=device-width, initial-scale=1">
<script src="https://cdn.tailwindcss.com"></script>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;800&display=swap" rel="stylesheet">
<style>body{font-family:'Inter',sans-serif}</style>
</head>
<body class="bg-[#08080A] text-white min-h-screen">
<div id="consentModal" class="fixed inset-0 bg-black/80 backdrop-blur-sm z-[99] flex items-center justify-center p-4">
<div class="bg-[#121214] border border-zinc-700 rounded-[20px] p-5 max-w-[380px] w-full">
<h3 class="font-bold text-sm">🔒 DPDP Consent (Govt. Rule)</h3>
<p class="text-[11px] text-zinc-400 mt-2">Aapke documents sirf is form ko bharne ke liye use honge, Supabase encrypted vault me save rahenge. 30 din me auto delete.</p>
<label class="flex gap-2 mt-3 text-[11px]"><input type="checkbox" id="consentCheck"> <span>Main sehmat hu, apne docs upload karne ke liye</span></label>
<button onclick="if(document.getElementById('consentCheck').checked){document.getElementById('consentModal').style.display='none'; localStorage.setItem('dpdp','yes')}else{alert('Pehle tick karo')}" class="w-full mt-3 bg-white text-black rounded-xl p-3 text-sm font-bold">I Agree & Continue</button>
</div></div>

<div class="max-w-[480px] mx-auto p-4">
<div class="flex justify-between items-center mb-5">
<div class="flex items-center gap-2"><div class="w-9 h-9 rounded-xl bg-gradient-to-br from-violet-500 to-blue-600 flex items-center justify-center font-black">C</div><div><h1 class="font-extrabold leading-none">CyberCafe Agent</h1><p class="text-[10px] text-zinc-500">Phase 4C • Fast + OCR + Consent</p></div></div>
<div class="flex items-center gap-2 text-[10px]"><span class="w-2 h-2 bg-green-500 rounded-full animate-pulse"></span><span class="bg-zinc-900 border border-zinc-800 px-2 py-1 rounded-full">LIVE</span></div>
</div>

<div class="bg-[#121214] border border-zinc-800/80 rounded-[20px] p-4">
<div class="flex justify-between items-center mb-3"><p class="text-xs font-semibold text-zinc-400">👤 Operator ID</p><span class="text-[10px] bg-green-500/10 text-green-400 border border-green-500/20 px-2 py-0.5 rounded-full">Auto Vault ON</span></div>
<input id="user_id" value="yuvraj_test" class="w-full bg-black border border-zinc-800 rounded-xl p-3 text-sm">
</div>

<div class="mt-4 bg-[#121214] border border-zinc-800/80 rounded-[20px] p-4">
<h2 class="font-bold text-[13px]">🎯 INTENT SELECTOR</h2>
<div class="flex gap-2 mt-3 overflow-x-auto pb-2">
<button onclick="filterCat('all')" data-cat="all" class="cat-btn whitespace-nowrap bg-white text-black px-4 py-2 rounded-full text-xs font-bold">All Forms</button>
<button onclick="filterCat('exam')" data-cat="exam" class="cat-btn whitespace-nowrap bg-[#1E1E20] border border-zinc-800 px-4 py-2 rounded-full text-xs">📚 Exam</button>
<button onclick="filterCat('certificate')" data-cat="certificate" class="cat-btn whitespace-nowrap bg-[#1E1E20] border border-zinc-800 px-4 py-2 rounded-full text-xs">📜 Certificate</button>
<button onclick="filterCat('new')" data-cat="new" class="cat-btn whitespace-nowrap bg-[#1E1E20] border border-zinc-800 px-4 py-2 rounded-full text-xs">🆕 New ID</button>
<button onclick="filterCat('correction')" data-cat="correction" class="cat-btn whitespace-nowrap bg-[#1E1E20] border border-zinc-800 px-4 py-2 rounded-full text-xs">✏️ Correction</button>
<button onclick="filterCat('scholarship')" data-cat="scholarship" class="cat-btn whitespace-nowrap bg-[#1E1E20] border border-zinc-800 px-4 py-2 rounded-full text-xs">🎓 Scholarship</button>
</div>
<select id="template" class="w-full mt-2 bg-black border border-zinc-800 rounded-xl p-3 text-sm"></select>
<button onclick="checkFill()" class="w-full mt-3 bg-gradient-to-r from-violet-600 to-blue-600 rounded-xl p-3 text-sm font-bold">Check Docs & Preview →</button>
<div id="preview" class="mt-3 bg-[#0A0A0B] border border-dashed border-zinc-800 rounded-xl p-3 min-h-[70px] text-xs text-zinc-500">Select a form to see required docs</div>
</div>

<div class="mt-4 bg-[#121214] border border-zinc-800/80 rounded-[20px] p-4">
<div class="flex justify-between items-center"><h2 class="font-bold text-[13px]">⚡ FAST UPLOAD</h2><span class="text-[10px] bg-violet-500/10 text-violet-300 border border-violet-500/20 px-2 py-0.5 rounded-full">BG OCR ON</span></div>
<select id="doc_type" class="w-full mt-3 bg-black border border-zinc-800 rounded-xl p-3 text-sm">
<option>aadhaar_front</option><option>aadhaar_back</option><option>pan_card</option><option>photo</option><option>signature</option><option>10th_marksheet</option><option>10th_certificate</option><option>12th_marksheet</option><option>graduation_marksheet</option><option>graduation_degree</option><option>income_certificate</option><option>domicile_certificate</option><option>caste_certificate</option><option>bank_passbook</option><option>ration_card</option>
</select>
<label class="mt-3 flex flex-col items-center justify-center w-full border-2 border-dashed border-zinc-800 rounded-xl p-4 bg-black/50">
<span class="text-xs text-zinc-400">📁 Tap to choose file</span><span id="fname" class="text-[11px] text-zinc-500 mt-1">No file chosen</span>
<input id="file" type="file" class="hidden" onchange="document.getElementById('fname').innerText=this.files[0]?.name||'No file chosen'">
</label>
<button onclick="upload()" class="w-full mt-3 bg-white text-black rounded-xl p-3 text-sm font-extrabold">Upload Fast</button>
<p id="status" class="text-[11px] mt-2 text-zinc-400"></p>
</div>

<div class="mt-4 bg-[#121214] border border-zinc-800/80 rounded-[20px] p-4">
<div class="flex justify-between items-center"><h2 class="font-bold text-[13px]">🗄️ MERA VAULT</h2><button onclick="loadVault()" class="text-[11px] bg-zinc-800 border border-zinc-700 px-3 py-1 rounded-full">Refresh ↻</button></div>
<div id="vault" class="mt-3 space-y-2"></div>
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
const OFFICIAL_MAP = {
 "aadhaar_correction":"https://myaadhaar.uidai.gov.in/","pan_new":"https://www.tin-nsdl.com/services/pan/","pan_correction":"https://www.tin-nsdl.com/services/pan/","income_certificate":"https://edistrict.up.gov.in/","domicile_certificate":"https://edistrict.up.gov.in/","caste_certificate":"https://edistrict.up.gov.in/","ews_new":"https://edistrict.up.gov.in/","voter_new":"https://voters.eci.gov.in/","passport_new":"https://portal2.passportindia.gov.in/","ayushman_new":"https://beneficiary.nha.gov.in/","ration_new":"https://fcs.up.gov.in/","ssc_gd":"https://ssc.nic.in/","ssc_cgl":"https://ssc.nic.in/","up_police_constable":"https://uppbpb.gov.in/","up_police_si":"https://uppbpb.gov.in/","railway_group_d":"https://www.rrbcdg.gov.in/","cuet_ug":"https://cuet.samarth.ac.in/","nda":"https://www.upsc.gov.in/","ibps_po":"https://www.ibps.in/","up_scholarship":"https://scholarship.up.gov.in/"
};
function filterCat(cat){
  document.querySelectorAll('.cat-btn').forEach(b=>{b.className='cat-btn whitespace-nowrap bg-[#1E1E20] border border-zinc-800 px-4 py-2 rounded-full text-xs';});
  const active=document.querySelector(`[data-cat="${cat}"]`); if(active) active.className='cat-btn whitespace-nowrap bg-white text-black px-4 py-2 rounded-full text-xs font-bold';
  const sel=document.getElementById('template'); sel.innerHTML='';
  Object.entries(TEMPLATES).forEach(([k,v])=>{ if(cat==='all'||v.category===cat){ const o=document.createElement('option'); o.value=k; o.textContent=v.name; sel.appendChild(o); } });
}
async function upload(){
  const uid=document.getElementById('user_id').value; const dtype=document.getElementById('doc_type').value; const f=document.getElementById('file').files[0];
  if(!f){alert('File choose kar');return;}
  const fd=new FormData(); fd.append('user_id',uid); fd.append('doc_type',dtype); fd.append('file',f);
  document.getElementById('status').innerText='⏳ Uploading...';
  try{
    const r=await fetch('/upload-document',{method:'POST',body:fd}); const j=await r.json();
    if(j.success){ document.getElementById('status').innerHTML='✅ Uploaded! 30 sec me Refresh'; loadVault(); setTimeout(loadVault,30000); }
    else document.getElementById('status').innerText='Fail';
  }catch(e){ document.getElementById('status').innerText='Error: '+e; }
}
async function loadVault(){
  const uid=document.getElementById('user_id').value; const v=document.getElementById('vault'); v.innerHTML='<p class="text-xs text-zinc-500">Loading...</p>';
  try{
    const r=await fetch('/vault/'+uid); const j=await r.json(); v.innerHTML='';
    (j.docs||[]).forEach(d=>{
      let badge=''; let border='border-zinc-800';
      if(d.ocr_data?.aadhaar_no){badge=`<span class="bg-green-500/10 text-green-400 border border-green-500/20 px-2 py-0.5 rounded-full text-[10px]">Aadhaar:${d.ocr_data.aadhaar_no}</span>`; border='border-green-500/20';}
      else if(d.ocr_data?.pan_no){badge=`<span class="bg-green-500/10 text-green-400 border border-green-500/20 px-2 py-0.5 rounded-full text-[10px]">PAN:${d.ocr_data.pan_no}</span>`; border='border-green-500/20';}
      else if(d.ocr_data?.status==='processing'){badge=`<span class="bg-yellow-500/10 text-yellow-400 border border-yellow-500/20 px-2 py-0.5 rounded-full text-[10px]">Processing...</span>`;}
      v.innerHTML+=`<div class="bg-black border ${border} rounded-xl p-3 flex justify-between items-center"><div><p class="text-xs font-bold">${d.doc_type}</p><p class="text-[10px] text-zinc-500 truncate w-[150px]">${d.file_name||''}</p><div class="mt-1">${badge}</div></div><div class="flex gap-2"><button onclick="deleteDoc('${d.id}')" class="text-[10px] text-red-400 border border-red-500/20 bg-red-500/10 px-2 py-1 rounded-full">Del</button><a href="${d.file_url}" target="_blank" class="text-[11px] bg-zinc-900 border border-zinc-800 px-3 py-1.5 rounded-full">View</a></div></div>`;
    });
  }catch(e){ v.innerHTML='<p class="text-red-400 text-xs">Vault load fail</p>'; }
}
async function deleteDoc(id){ if(!confirm('Delete?')) return; await fetch('/vault/'+id,{method:'DELETE'}); loadVault(); }
async function checkFill(){
  const uid=document.getElementById('user_id').value; const tid=document.getElementById('template').value; const preview=document.getElementById('preview');
  if(!tid){ preview.innerHTML='Form select karo'; return; }
  preview.innerHTML='Checking...';
  try{
    const r=await fetch(`/api/fill-preview/${tid}/${uid}`);
    if(!r.ok){ preview.innerHTML=`<span class="text-red-400">API Error ${r.status}</span>`; return; }
    const j=await r.json();
    let h=`<p class="font-bold text-white">${j.template_name}</p><p class="text-[11px] text-zinc-500 mt-1">Need: ${j.required_docs.join(', ')}</p>`;
    if(j.missing.length>0) h+=`<div class="mt-2 bg-red-500/10 border border-red-500/20 rounded-lg p-2 text-red-300 text-[11px]">❌ Missing: ${j.missing.join(', ')}</div>`;
    else h+=`<div class="mt-2 bg-green-500/10 border border-green-500/20 rounded-lg p-2 text-green-300 font-bold text-[11px]">✅ Ready to Apply</div>`;
    h+=`<p class="text-[10px] text-zinc-500 mt-2">You have: ${j.you_have.join(', ')||'none'}</p>`;
    const official=OFFICIAL_MAP[tid];
    if(official && j.missing.length==0){ h+=`<a href="${official}" target="_blank" class="mt-3 block text-center bg-white text-black rounded-xl p-3 font-bold text-sm">Go to Official Portal →</a>`; }
    preview.innerHTML=h;
  }catch(e){ preview.innerHTML=`<span class="text-red-400 text-[11px]">Fail: ${e}</span>`; }
}
window.addEventListener('load', ()=>{
  const m=document.getElementById('consentModal');
  if(localStorage.getItem('dpdp')==='yes' && m) m.style.display='none';
  filterCat('all'); setTimeout(loadVault,800);
});
</script></body></html>
"""

@app.get("/", response_class=HTMLResponse)
def home(): return HTML_PAGE

@app.get("/api/status")
def status(): return {"templates": len(TEMPLATES), "ocr": OCR_AVAILABLE}

@app.post("/upload-document")
async def upload_doc(background_tasks: BackgroundTasks, user_id: str = Form(...), doc_type: str = Form(...), file: UploadFile = File(...)):
    sb = get_sb()
    if not sb: raise HTTPException(500, "DB not configured")
    data = await file.read()
    path = f"{user_id}/{doc_type}/{uuid.uuid4().hex}_{file.filename}"
    sb.storage.from_(BUCKET).upload(path, data, {"content-type": file.content_type, "upsert":"true"})
    url = sb.storage.from_(BUCKET).get_public_url(path)
    ins = sb.table("user_vault").insert({"user_id": user_id,"doc_type": doc_type,"file_name": file.filename,"storage_path": path,"file_url": url,"file_size": len(data),"ocr_data": {"status":"processing"}}).execute()
    rec_id = ins.data[0]["id"] if ins.data else None
    if rec_id: background_tasks.add_task(do_ocr_background, rec_id, data, doc_type)
    return {"success": True, "file_url": url}

@app.get("/vault/{user_id}")
def vault(user_id: str):
    sb = get_sb()
    res = sb.table("user_vault").select("*").eq("user_id", user_id).order("created_at", desc=True).execute()
    return {"docs": res.data}

@app.delete("/vault/{record_id}")
def delete_doc(record_id: str):
    sb = get_sb()
    sb.table("user_vault").delete().eq("id", record_id).execute()
    return {"deleted": True}

@app.get("/api/fill-preview/{template_id}/{user_id}")
def fill_preview(template_id: str, user_id: str):
    if template_id not in TEMPLATES: raise HTTPException(404, "Template not found")
    tpl = TEMPLATES[template_id]
    sb = get_sb()
    res = sb.table("user_vault").select("doc_type").eq("user_id", user_id).execute()
    you_have = list(set([r["doc_type"] for r in res.data]))
    missing = [d for d in tpl["required_docs"] if d not in you_have]
    return {"template_name": tpl["name"], "required_docs": tpl["required_docs"], "you_have": you_have, "missing": missing}
