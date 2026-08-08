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

app = FastAPI(title="Cyber Cafe Agent - Phase 5.2 Robust Card Aadhaar")
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
 "aadhaar_correction":"https://myaadhaar.uidai.gov.in/","pan_new":"https://www.tin-nsdl.com/services/pan/","pan_correction":"https://www.tin-nsdl.com/services/pan/","income_certificate":"https://edistrict.up.gov.in/","domicile_certificate":"https://edistrict.up.gov.in/","caste_certificate":"https://edistrict.up.gov.in/","ews_new":"https://edistrict.up.gov.in/","voter_new":"https://voters.eci.gov.in/","passport_new":"https://portal2.passportindia.gov.in/","ayushman_new":"https://beneficiary.nha.gov.in/","ration_new":"https://fcs.up.gov.in/","ssc_gd":"https://ssc.gov.in/","ssc_cgl":"https://ssc.gov.in/","up_police_constable":"https://uppbpb.gov.in/","up_police_si":"https://uppbpb.gov.in/","railway_group_d":"https://www.rrbcdg.gov.in/","cuet_ug":"https://cuet.samarth.ac.in/","nda":"https://www.upsc.gov.in/","ibps_po":"https://www.ibps.in/","up_scholarship":"https://scholarship.up.gov.in/"
}

def get_sb():
    return create_client(SUPABASE_URL, SUPABASE_KEY) if SUPABASE_URL and SUPABASE_KEY else None

def parse_smart_ocr(text, doc_type="aadhaar_front"):
    data = {}
    if not text or len(text.strip())<3:
        return data
    lines = [l.strip() for l in text.split('\n') if l.strip()]
    full_text = "\n".join(lines)

    m = re.search(r'\b\d{4}\s\d{4}\s\d{4}\b', full_text)
    if m: data["aadhaar_no"] = m.group().strip()
    m2 = re.search(r'\b[A-Z]{5}[0-9]{4}[A-Z]\b', full_text)
    if m2: data["pan_no"] = m2.group().strip()

    dob_patterns = [
        r'DOB[^\d]{0,10}(\d{2}[/-]\d{2}[/-]\d{4})',
        r'Date of Birth[^\d]{0,10}(\d{2}[/-]\d{2}[/-]\d{4})',
        r'Birth[^\d]{0,10}(\d{2}[/-]\d{2}[/-]\d{4})',
        r'\b(\d{2}/\d{4})\b',
        r'\b(\d{2}-\d{4})\b'
    ]
    for pat in dob_patterns:
        mm = re.search(pat, full_text, re.I)
        if mm:
            val = mm.group(1)
            data["dob"] = val.replace('-','/')
            break
    if "dob" not in data:
        yob = re.search(r'(Year of Birth|YOB)[^\d]{0,5}(\d{4})', full_text, re.I)
        if yob:
            data["dob"] = yob.group(2)
            data["yob"] = yob.group(2)
    g = re.search(r'\b(MALE|FEMALE)\b', full_text, re.I)
    if g:
        gm = g.group(1).upper()
        if 'FEMALE' in gm:
            data["gender"] = "FEMALE"
        else:
            data["gender"] = "MALE"
    pins = re.findall(r'\b[1-9]\d{5}\b', full_text)
    if pins:
        seen=[]
        for p in pins:
            if p not in seen:
                seen.append(p)
        data["pincode"] = seen[-1]
        if len(seen)>1:
            data["all_pincodes"] = seen

    blacklist = ['GOVT','GOVERNMENT','INDIA','AADHAAR','UIDAI','INCOME','TAX','DEPARTMENT','MALE','FEMALE','ENROLMENT','ELECTION','PASSPORT','VID','MERA','BASE','AUTHORITY','IDENTIFICATION','ADDRESS','INDIAN']
    anchor_idx = -1
    for i,l in enumerate(lines):
        if re.search(r'\d{2}/\d{4}', l) or 'MALE' in l.upper() or 'FEMALE' in l.upper() or 'DOB' in l.upper() or re.search(r'\d{4}\s\d{4}\s\d{4}', l):
            anchor_idx = i
            break
    if anchor_idx!=-1:
        for j in range(max(0, anchor_idx-4), anchor_idx):
            cand = lines[j]
            up = cand.upper()
            if any(b in up for b in blacklist):
                continue
            if re.search(r'\d', cand):
                continue
            if len(cand)<3 or len(cand)>40:
                continue
            if re.match(r'^[A-Za-z\s\.\']{3,40}$', cand):
                words = cand.split()
                if 2 <= len(words) <= 4:
                    data["full_name"] = cand.title()
                    break
    if "full_name" not in data:
        for line in lines[:6]:
            up = line.upper()
            if any(b in up for b in blacklist):
                continue
            if re.search(r'\d', line):
                continue
            if len(line)<4 or len(line)>35:
                continue
            if re.match(r'^[A-Za-z\s\.\']{4,35}$', line):
                words=line.split()
                if 2 <= len(words) <=4:
                    data["full_name"] = line.title()
                    break

    if "pincode" in data:
        for i,l in enumerate(lines):
            if data["pincode"] in l:
                addr_lines=[]
                for k in range(max(0,i-3), i):
                    ll = lines[k]
                    if "full_name" in data and data["full_name"].lower() in ll.lower():
                        continue
                    if re.search(r'\d{4}\s\d{4}\s\d{4}', ll):
                        continue
                    if re.search(r'\d{2}/\d{2}/\d{4}', ll) and 'DOB' in ll.upper():
                        continue
                    if ll.strip().upper() in ['MALE','FEMALE']:
                        continue
                    if any(b in ll.upper() for b in ['UIDAI','GOVT','MERA AADHAAR']):
                        continue
                    addr_lines.append(ll)
                if addr_lines:
                    addr = " ".join(addr_lines)
                    addr = re.sub(r'\s+', ' ', addr).strip()
                    if len(addr)>10:
                        data["address"] = addr[:200]
                break
    if "address" not in data:
        for i,l in enumerate(lines):
            up = l.upper()
            if 'ADDRESS' in up:
                nxt = lines[i+1:min(len(lines), i+4)]
                if nxt:
                    data["address"] = " ".join(nxt)[:200]
                break
            if any(kw in up for kw in ['S/O','W/O','C/O','VILL','VILLAGE','POST','DIST','HOUSE NO','ROAD','COLONY']):
                nxt = lines[i:min(len(lines), i+3)]
                addr = " ".join(nxt)
                if len(addr)>15:
                    data["address"] = addr[:200]
                    break
    if "address" not in data and doc_type in ["aadhaar_back","aadhaar_combined"]:
        candidates=[]
        for l in lines:
            if len(l)<12:
                continue
            if re.search(r'\d{4}\s\d{4}\s\d{4}', l):
                continue
            if re.search(r'\d{2}/\d{4}', l):
                continue
            if 'MALE' in l.upper() or 'FEMALE' in l.upper():
                continue
            if any(b in l.upper() for b in ['UIDAI','VID','GOVT','MERA','BASE']):
                continue
            if re.search(r'[A-Za-z]', l):
                candidates.append(l)
        if candidates:
            candidates_sorted = sorted(candidates, key=len, reverse=True)
            data["address"] = " ".join(candidates_sorted[:2])[:200]

    return data

def extract_ocr(file_bytes, doc_type):
    if doc_type not in ["aadhaar_front","aadhaar_back","aadhaar_combined","pan_card"]:
        return {"status":"no_ocr_needed", "doc_type": doc_type}
    try:
        import pytesseract
        pytesseract.pytesseract.tesseract_cmd = "/usr/bin/tesseract"
        img = Image.open(io.BytesIO(file_bytes))
        if img.width > 1600:
            w = 1600 / float(img.width); h = int(float(img.height) * w)
            img = img.resize((1600, h))
        img = img.convert('L')
        try:
            text = pytesseract.image_to_string(img, lang='eng+hin', config='--oem 3 --psm 6')
        except:
            text = pytesseract.image_to_string(img, config='--oem 3 --psm 6')
        parsed = parse_smart_ocr(text, doc_type)
        if not parsed:
            return {"status":"ocr_done_no_data", "raw": text[:120]}
        return parsed
    except Exception as e:
        return {"status":"ocr_failed", "error": str(e)[:120]}

def do_ocr_background(record_id, file_bytes, doc_type):
    try:
        ocr = extract_ocr(file_bytes, doc_type)
        if ocr:
            sb = get_sb()
            if sb:
                sb.table("user_vault").update({"ocr_data": ocr}).eq("id", record_id).execute()
    except:
        pass

HTML_PAGE = """
<!DOCTYPE html><html><head><meta name="viewport" content="width=device-width, initial-scale=1">
<title>CyberCafe Agent - Phase 5.2</title>
<script src="https://cdn.tailwindcss.com"></script>
<link href="https://fonts.googleapis.com/css2?family=Inter:wght@400;600;700;800&display=swap" rel="stylesheet">
<style>body{font-family:'Inter',sans-serif}.scroll-hide::-webkit-scrollbar{display:none}</style>
</head>
<body class="bg-[#08080A] text-white min-h-screen">
<div id="consentModal" class="fixed inset-0 bg-black/80 backdrop-blur-sm z-[99] flex items-center justify-center p-4">
<div class="bg-[#121214] border border-zinc-700 rounded-[20px] p-5 max-w-[380px] w-full">
<h3 class="font-bold text-sm">🔒 DPDP Consent</h3>
<p class="text-[11px] text-zinc-400 mt-2">Docs vault me safe rahenge. CAPTCHA/OTP/PAYMENT aap khud karenge.</p>
<label class="flex gap-2 mt-3 text-[11px]"><input type="checkbox" id="consentCheck"> <span>Main sehmat hu</span></label>
<button onclick="if(document.getElementById('consentCheck').checked){document.getElementById('consentModal').style.display='none'; localStorage.setItem('dpdp','yes')}else{alert('Pehle tick karo')}" class="w-full mt-3 bg-white text-black rounded-xl p-3 text-sm font-bold">I Agree & Continue</button>
</div></div>
<div class="max-w-[480px] mx-auto p-4 pb-20">
<div class="flex justify-between items-center mb-5">
<div class="flex items-center gap-2"><div class="w-9 h-9 rounded-xl bg-gradient-to-br from-violet-500 to-blue-600 flex items-center justify-center font-black">C</div><div><h1 class="font-extrabold leading-none">CyberCafe Agent</h1><p class="text-[10px] text-zinc-500">Phase 5.2 • Card Aadhaar Fix</p></div></div>
<div class="flex items-center gap-2 text-[10px]"><span class="w-2 h-2 bg-green-500 rounded-full animate-pulse"></span><span class="bg-zinc-900 border border-zinc-800 px-2 py-1 rounded-full">LIVE</span></div>
</div>
<div class="bg-[#121214] border border-zinc-800/80 rounded-[20px] p-4">
<div class="flex justify-between items-center mb-3"><p class="text-xs font-semibold text-zinc-400">👤 Student ID / Mobile No.</p><span class="text-[10px] bg-green-500/10 text-green-400 border border-green-500/20 px-2 py-0.5 rounded-full">Auto Vault ON • ₹99/mo</span></div>
<input id="user_id" value="yuvraj_test" class="w-full bg-black border border-zinc-800 rounded-xl p-3 text-sm">
<p class="text-[10px] text-zinc-500 mt-2">Front me naam/DOB, Back me address/pincode - dono upload karo to full Smart Fill hoga.</p>
</div>
<div class="mt-4 bg-[#121214] border border-zinc-800/80 rounded-[20px] p-4">
<h2 class="font-bold text-[13px]">🎯 INTENT SELECTOR</h2>
<div class="flex gap-2 mt-3 overflow-x-auto pb-2 scroll-hide">
<button onclick="filterCat('all')" data-cat="all" class="cat-btn whitespace-nowrap bg-white text-black px-4 py-2 rounded-full text-xs font-bold">All Forms</button>
<button onclick="filterCat('exam')" data-cat="exam" class="cat-btn whitespace-nowrap bg-[#1E1E20] border border-zinc-800 px-4 py-2 rounded-full text-xs">📚 Exam</button>
<button onclick="filterCat('certificate')" data-cat="certificate" class="cat-btn whitespace-nowrap bg-[#1E1E20] border border-zinc-800 px-4 py-2 rounded-full text-xs">📜 Certificate</button>
<button onclick="filterCat('new')" data-cat="new" class="cat-btn whitespace-nowrap bg-[#1E1E20] border border-zinc-800 px-4 py-2 rounded-full text-xs">🆕 New ID</button>
<button onclick="filterCat('correction')" data-cat="correction" class="cat-btn whitespace-nowrap bg-[#1E1E20] border border-zinc-800 px-4 py-2 rounded-full text-xs">✏️ Correction</button>
<button onclick="filterCat('scholarship')" data-cat="scholarship" class="cat-btn whitespace-nowrap bg-[#1E1E20] border border-zinc-800 px-4 py-2 rounded-full text-xs">🎓 Scholarship</button>
</div>
<select id="template" class="w-full mt-2 bg-black border border-zinc-800 rounded-xl p-3 text-sm"></select>
<button onclick="checkFill()" class="w-full mt-3 bg-gradient-to-r from-violet-600 to-blue-600 rounded-xl p-3 text-sm font-bold">✨ Check Docs + Smart Fill →</button>
<div id="preview" class="mt-3 bg-[#0A0A0B] border border-dashed border-zinc-800 rounded-xl p-3 min-h-[70px] text-xs text-zinc-500">Form select karo</div>
<div id="smartBox" class="mt-3 hidden"></div>
</div>
<div class="mt-4 bg-[#121214] border border-zinc-800/80 rounded-[20px] p-4">
<div class="flex justify-between items-center"><h2 class="font-bold text-[13px]">⚡ FAST UPLOAD (BG OCR)</h2><span class="text-[10px] bg-violet-500/10 text-violet-300 border border-violet-500/20 px-2 py-0.5 rounded-full">Front+Back Merge</span></div>
<select id="doc_type" class="w-full mt-3 bg-black border border-zinc-800 rounded-xl p-3 text-sm">
<option value="aadhaar_front">aadhaar_front - Card Front (Name/DOB)</option>
<option value="aadhaar_back">aadhaar_back - Card Back (Address/Pin)</option>
<option value="pan_card">pan_card</option>
<option value="photo">photo</option>
<option value="signature">signature</option>
<option value="10th_marksheet">10th_marksheet</option>
<option value="10th_certificate">10th_certificate</option>
<option value="12th_marksheet">12th_marksheet</option>
<option value="graduation_marksheet">graduation_marksheet</option>
<option value="graduation_degree">graduation_degree</option>
<option value="income_certificate">income_certificate</option>
<option value="domicile_certificate">domicile_certificate</option>
<option value="caste_certificate">caste_certificate</option>
<option value="bank_passbook">bank_passbook</option>
<option value="ration_card">ration_card</option>
</select>
<label class="mt-3 flex flex-col items-center justify-center w-full border-2 border-dashed border-zinc-800 rounded-xl p-4 bg-black/50">
<span class="text-xs text-zinc-400">📁 Tap to choose file</span><span id="fname" class="text-[11px] text-zinc-500 mt-1">No file chosen</span>
<input id="file" type="file" class="hidden" onchange="document.getElementById('fname').innerText=this.files[0]?.name||'No file chosen'">
</label>
<button onclick="upload()" class="w-full mt-3 bg-white text-black rounded-xl p-3 text-sm font-extrabold">Upload Fast - 2 Sec</button>
<p id="status" class="text-[11px] mt-2 text-zinc-400"></p>
</div>
<div class="mt-4 bg-[#121214] border border-zinc-800/80 rounded-[20px] p-4">
<div class="flex justify-between items-center"><h2 class="font-bold text-[13px]">🗄️ MERA VAULT + MERGED SMART DATA</h2><button onclick="loadVault()" class="text-[11px] bg-zinc-800 border border-zinc-700 px-3 py-1 rounded-full">Refresh ↻</button></div>
<div id="vault" class="mt-3 space-y-2"></div>
<p class="text-[10px] text-zinc-600 mt-3">Tip: Card Aadhaar wale - Front + Back dono upload karo, Agent merge karke full data bana dega. CAPTCHA/OTP/PAYMENT aap khud karenge.</p>
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
 "aadhaar_correction":"https://myaadhaar.uidai.gov.in/","pan_new":"https://www.tin-nsdl.com/services/pan/","pan_correction":"https://www.tin-nsdl.com/services/pan/","income_certificate":"https://edistrict.up.gov.in/","domicile_certificate":"https://edistrict.up.gov.in/","caste_certificate":"https://edistrict.up.gov.in/","ews_new":"https://edistrict.up.gov.in/","voter_new":"https://voters.eci.gov.in/","passport_new":"https://portal2.passportindia.gov.in/","ayushman_new":"https://beneficiary.nha.gov.in/","ration_new":"https://fcs.up.gov.in/","ssc_gd":"https://ssc.gov.in/","ssc_cgl":"https://ssc.gov.in/","up_police_constable":"https://uppbpb.gov.in/","up_police_si":"https://uppbpb.gov.in/","railway_group_d":"https://www.rrbcdg.gov.in/","cuet_ug":"https://cuet.samarth.ac.in/","nda":"https://www.upsc.gov.in/","ibps_po":"https://www.ibps.in/","up_scholarship":"https://scholarship.up.gov.in/"
};
function filterCat(cat){
  document.querySelectorAll('.cat-btn').forEach(b=>{ b.className='cat-btn whitespace-nowrap bg-[#1E1E20] border border-zinc-800 px-4 py-2 rounded-full text-xs'; });
  const active=document.querySelector(`[data-cat="${cat}"]`); if(active) active.className='cat-btn whitespace-nowrap bg-white text-black px-4 py-2 rounded-full text-xs font-bold';
  const sel=document.getElementById('template'); sel.innerHTML='';
  Object.entries(TEMPLATES).forEach(([k,v])=>{ if(cat==='all'||v.category===cat){ const o=document.createElement('option'); o.value=k; o.textContent=v.name; sel.appendChild(o); } });
}
async function upload(){
  const uid=document.getElementById('user_id').value; const dtype=document.getElementById('doc_type').value; const f=document.getElementById('file').files[0];
  if(!uid){alert('Student ID dalo');return;}
  if(!f){alert('File choose kar');return;}
  const fd=new FormData(); fd.append('user_id',uid); fd.append('doc_type',dtype); fd.append('file',f);
  document.getElementById('status').innerText='⏳ Uploading...';
  try{
    const r=await fetch('/upload-document',{method:'POST',body:fd}); const j=await r.json();
    if(j.success){
      document.getElementById('status').innerHTML='✅ Uploaded! 10 sec me Smart Fill - Auto refresh ON';
      let cnt=0; const iv=setInterval(()=>{ loadVault(); cnt++; if(cnt>10) clearInterval(iv); }, 3000);
      loadVault();
    }
  }catch(e){ document.getElementById('status').innerText='Error: '+e; }
}
async function loadVault(){
  const uid=document.getElementById('user_id').value; if(!uid) return;
  const v=document.getElementById('vault');
  try{
    const r=await fetch('/vault/'+uid); const j=await r.json(); v.innerHTML='';
    if((j.docs||[]).length==0){ v.innerHTML='<p class="text-[11px] text-zinc-600">Koi doc nahi.</p>'; return; }
    (j.docs||[]).forEach(d=>{
      let badge=''; let border='border-zinc-800'; let smartInfo='';
      const oc = d.ocr_data||{};
      if(oc.full_name || oc.aadhaar_no || oc.pan_no || oc.dob || oc.pincode){
        border='border-green-500/20';
        if(oc.full_name) smartInfo+=`<span class="bg-violet-500/10 text-violet-300 border border-violet-500/20 px-2 py-0.5 rounded-full text-[10px] mr-1">👤 ${oc.full_name}</span>`;
        if(oc.aadhaar_no) badge+=`<span class="bg-green-500/10 text-green-400 border border-green-500/20 px-2 py-0.5 rounded-full text-[10px] mr-1">${oc.aadhaar_no}</span>`;
        if(oc.dob) badge+=`<span class="bg-blue-500/10 text-blue-400 border border-blue-500/20 px-2 py-0.5 rounded-full text-[10px] mr-1">DOB:${oc.dob}</span>`;
        if(oc.gender) badge+=`<span class="bg-zinc-700 text-zinc-300 px-2 py-0.5 rounded-full text-[10px] mr-1">${oc.gender}</span>`;
        if(oc.pincode) badge+=`<span class="bg-orange-500/10 text-orange-300 px-2 py-0.5 rounded-full text-[10px] mr-1">PIN:${oc.pincode}</span>`;
      } else if(oc.status==='processing'){
        badge=`<span class="bg-yellow-500/10 text-yellow-400 border border-yellow-500/20 px-2 py-0.5 rounded-full text-[10px]">⏳ Processing 5-10 sec...</span>`;
        border='border-yellow-500/20';
      } else if(oc.status==='ocr_done_no_data'){
        badge=`<span class="bg-red-500/10 text-red-400 px-2 py-0.5 rounded-full text-[10px]">Text nahi mila - saaf photo dalo</span>`;
      }
      v.innerHTML+=`<div class="bg-black border ${border} rounded-xl p-3"><div class="flex justify-between items-start"><div><p class="text-xs font-bold">${d.doc_type}</p><p class="text-[10px] text-zinc-500 truncate w-[160px]">${d.file_name||''}</p><div class="mt-1 flex flex-wrap gap-1">${smartInfo}${badge}</div>${oc.address?`<p class="text-[10px] text-zinc-400 mt-1">📍 ${oc.address}</p>`:''}</div><div class="flex gap-2"><button onclick="deleteDoc('${d.id}')" class="text-[10px] text-red-400 border border-red-500/20 bg-red-500/10 px-2 py-1 rounded-full">Del</button><a href="${d.file_url}" target="_blank" class="text-[11px] bg-zinc-900 border border-zinc-800 px-3 py-1.5 rounded-full">View</a></div></div></div>`;
    });
  }catch(e){ v.innerHTML='<p class="text-red-400 text-xs">Vault fail</p>'; }
}
async function deleteDoc(id){ if(!confirm('Delete?')) return; await fetch('/vault/'+id,{method:'DELETE'}); loadVault(); }
async function checkFill(){
  const uid=document.getElementById('user_id').value; const tid=document.getElementById('template').value;
  const preview=document.getElementById('preview'); const smartBox=document.getElementById('smartBox');
  if(!uid){ alert('Student ID dalo'); return; }
  if(!tid){ preview.innerHTML='Form select karo'; return; }
  preview.innerHTML='⏳ Smart Fill soch raha hai...';
  smartBox.classList.add('hidden');
  try{
    const r=await fetch(`/api/smart-fill/${tid}/${uid}`);
    const j=await r.json();
    let h=`<p class="font-bold text-white">${j.template_name}</p><p class="text-[11px] text-zinc-500 mt-1">Need: ${j.required_docs.join(', ')}</p>`;
    if(j.missing.length>0) h+=`<div class="mt-2 bg-red-500/10 border border-red-500/20 rounded-lg p-2 text-red-300 text-[11px]">❌ Missing: ${j.missing.join(', ')}</div>`;
    else h+=`<div class="mt-2 bg-green-500/10 border border-green-500/20 rounded-lg p-2 text-green-300 font-bold text-[11px]">✅ Docs Ready</div>`;
    h+=`<p class="text-[10px] text-zinc-500 mt-2">You have: ${j.you_have.join(', ')||'none'}</p>`;
    if(j.merged_from) h+=`<p class="text-[9px] text-violet-400 mt-1">Merged from: ${j.merged_from.join(', ')}</p>`;
    preview.innerHTML=h;
    let sh=`<div class="bg-gradient-to-br from-violet-500/10 to-blue-500/10 border border-violet-500/20 rounded-xl p-3">`;
    sh+=`<p class="font-bold text-[12px]">✨ Smart Fill - Merged Front+Back</p>`;
    const af=j.auto_filled||{};
    if(Object.keys(af).length==0){
      sh+=`<p class="text-[11px] text-zinc-500 mt-2">Kuch nahi mila. Aadhaar Front + Back dono saaf photo me upload karo.</p>`;
    } else {
      sh+=`<div class="mt-2 space-y-1">`;
      if(af.full_name) sh+=`<div class="flex justify-between text-[11px]"><span class="text-zinc-400">Name</span><span class="font-bold text-white">${af.full_name} ✅ (Front se)</span></div>`;
      if(af.dob) sh+=`<div class="flex justify-between text-[11px]"><span class="text-zinc-400">DOB</span><span class="font-bold">${af.dob} ✅ (Front se)</span></div>`;
      if(af.gender) sh+=`<div class="flex justify-between text-[11px]"><span class="text-zinc-400">Gender</span><span>${af.gender} ✅</span></div>`;
      if(af.aadhaar_no) sh+=`<div class="flex justify-between text-[11px]"><span class="text-zinc-400">Aadhaar</span><span class="font-mono text-green-300">${af.aadhaar_no} ✅</span></div>`;
      if(af.pincode) sh+=`<div class="flex justify-between text-[11px]"><span class="text-zinc-400">Pincode</span><span>${af.pincode} ✅ (${af.pincode_source||'Back se'})</span></div>`;
      if(af.address) sh+=`<div class="text-[11px] mt-1"><span class="text-zinc-400">Address:</span> <span class="text-zinc-300">${af.address} ✅ (${af.address_source||'Back se'})</span></div>`;
      sh+=`</div>`;
      let hint='';
      if(!af.address) hint+='Address ke liye Aadhaar Back upload karo. ';
      if(!af.pincode) hint+='Pincode ke liye Back side upload karo.';
      if(hint) sh+=`<div class="mt-2 bg-yellow-500/10 border border-yellow-500/20 rounded-lg p-2 text-[10px] text-yellow-300">💡 ${hint}</div>`;
    }
    const official=OFFICIAL_MAP[tid];
    if(official){
      if(j.missing.length==0) sh+=`<a href="${official}" target="_blank" class="mt-3 block text-center bg-white text-black rounded-xl p-3 font-bold text-sm">Go to Official Portal →</a>`;
      else sh+=`<a href="${official}" target="_blank" class="mt-3 block text-center bg-zinc-900 border border-zinc-800 text-zinc-400 rounded-xl p-3 text-[11px]">Official Site Dekho</a>`;
    }
    sh+=`<button onclick="copySmart()" class="mt-2 w-full bg-zinc-900 border border-zinc-800 rounded-xl p-2 text-[11px]">📋 Copy Merged Data</button>`;
    sh+=`</div>`;
    smartBox.innerHTML=sh;
    smartBox.classList.remove('hidden');
    window._lastSmart = af;
  }catch(e){ preview.innerHTML=`Fail: ${e}`; }
}
function copySmart(){
  const af=window._lastSmart||{}; navigator.clipboard.writeText(JSON.stringify(af,null,2)).then(()=>alert('Copied!'));
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
def status(): return {"templates": len(TEMPLATES), "phase": "5.2-card-aadhaar", "ocr": OCR_AVAILABLE}

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
    if not sb: return {"docs":[]}
    res = sb.table("user_vault").select("*").eq("user_id", user_id).order("created_at", desc=True).execute()
    return {"docs": res.data}

@app.delete("/vault/{record_id}")
def delete_doc(record_id: str):
    sb = get_sb()
    if sb:
        sb.table("user_vault").delete().eq("id", record_id).execute()
    return {"deleted": True}

@app.get("/api/fill-preview/{template_id}/{user_id}")
def fill_preview(template_id: str, user_id: str):
    if template_id not in TEMPLATES: raise HTTPException(404, "Template not found")
    tpl = TEMPLATES[template_id]
    sb = get_sb()
    you_have=[]
    if sb:
        res = sb.table("user_vault").select("doc_type").eq("user_id", user_id).execute()
        you_have = list(set([r["doc_type"] for r in res.data]))
    missing = [d for d in tpl["required_docs"] if d not in you_have]
    return {"template_name": tpl["name"], "required_docs": tpl["required_docs"], "you_have": you_have, "missing": missing}

@app.get("/api/smart-fill/{template_id}/{user_id}")
def smart_fill(template_id: str, user_id: str):
    if template_id not in TEMPLATES: raise HTTPException(404, "Template not found")
    tpl = TEMPLATES[template_id]
    sb = get_sb()
    you_have=[]
    merged={}
    merged_from=[]
    pincode_source=None
    address_source=None
    if sb:
        res = sb.table("user_vault").select("*").eq("user_id", user_id).execute()
        for row in res.data:
            dt = row.get("doc_type")
            if dt and dt not in you_have:
                you_have.append(dt)
            ocr = row.get("ocr_data")
            if isinstance(ocr, dict):
                for k,v in ocr.items():
                    if k in ["status","error","raw","doc_type","no_ocr_needed","ocr_done_no_data","ocr_failed","all_pincodes"]:
                        continue
                    if not v:
                        continue
                    if k not in merged:
                        merged[k]=v
                        if dt not in merged_from:
                            merged_from.append(dt)
                        if k=="pincode":
                            pincode_source = dt
                        if k=="address":
                            address_source = dt
    if pincode_source:
        merged["pincode_source"] = pincode_source
    if address_source:
        merged["address_source"] = address_source
    missing = [d for d in tpl["required_docs"] if d not in you_have]
    return {
        "template_name": tpl["name"],
        "required_docs": tpl["required_docs"],
        "you_have": you_have,
        "missing": missing,
        "auto_filled": merged,
        "merged_from": merged_from,
        "auto_filled_count": len(merged),
        "official_url": OFFICIAL_URLS.get(template_id,"")
}
