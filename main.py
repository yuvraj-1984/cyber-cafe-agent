import os
from fastapi import FastAPI, UploadFile, File, Form
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import HTMLResponse

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

FRONTEND_HTML = """
<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8"><meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Cyber Cafe Agent</title>
<script src="https://cdn.tailwindcss.com"></script>
</head>
<body class="bg-[#0a0a0a] text-white min-h-screen">
<div class="max-w-md mx-auto p-4">
  <div class="text-center py-6">
    <h1 class="text-3xl font-black text-orange-500">CYBER CAFE AGENT</h1>
    <p class="text-zinc-400 text-sm mt-1">Vault Permanent - Auto Form Fill</p>
    <div class="mt-2 text-xs bg-green-900/30 text-green-400 px-3 py-1 rounded-full inline-block">● LIVE + Supabase Connected</div>
  </div>

  <div class="bg-zinc-900 border border-zinc-800 rounded-2xl p-4 mb-4">
    <h2 class="font-bold mb-3">1. User ID</h2>
    <input id="userId" value="test_user_01" class="w-full bg-black border border-zinc-700 rounded-xl px-4 py-3 text-white" placeholder="Aadhaar last 4 digit">
  </div>

  <div class="bg-zinc-900 border border-zinc-800 rounded-2xl p-4 mb-4">
    <h2 class="font-bold mb-3">2. Document Upload (Permanent)</h2>
    <select id="docType" class="w-full bg-black border border-zinc-700 rounded-xl px-4 py-3 mb-3">
      <option value="aadhaar">Aadhaar Card</option>
      <option value="photo">Photo</option>
      <option value="10th_marksheet">10th Marksheet</option>
      <option value="12th_marksheet">12th Marksheet</option>
      <option value="domicile">Domicile</option>
    </select>
    <input id="fileInput" type="file" class="w-full text-sm text-zinc-400 mb-3">
    <button onclick="uploadDoc()" id="uploadBtn" class="w-full bg-orange-500 text-black font-bold py-3 rounded-xl">UPLOAD TO VAULT</button>
    <pre id="uploadResult" class="mt-3 text-xs bg-black p-3 rounded-xl overflow-auto hidden"></pre>
  </div>

  <div class="bg-zinc-900 border border-zinc-800 rounded-2xl p-4 mb-4">
    <h2 class="font-bold mb-3">3. Mera Vault Dekho</h2>
    <div class="flex gap-2">
      <input id="vaultUserId" value="test_user_01" class="flex-1 bg-black border border-zinc-700 rounded-xl px-4 py-3">
      <button onclick="loadVault()" class="bg-white text-black font-bold px-6 rounded-xl">VIEW</button>
    </div>
    <div id="vaultResult" class="mt-3 space-y-2"></div>
  </div>

  <div class="bg-zinc-900 border border-zinc-800 rounded-2xl p-4">
    <h2 class="font-bold mb-3">4. Army Agniveer Auto-Fill</h2>
    <button onclick="loadTemplate()" class="w-full border border-orange-500 text-orange-500 font-bold py-3 rounded-xl">GET FORM TEMPLATE</button>
    <div id="templateResult" class="mt-3 text-xs"></div>
    <a href="https://joinindianarmy.nic.in" target="_blank" class="mt-3 block text-center bg-zinc-800 py-3 rounded-xl text-sm">Official Army Site Open ↗</a>
  </div>
  <p class="text-center text-zinc-600 text-[10px] mt-6">API: /docs - Backend: Render + Supabase Mumbai</p>
</div>
<script>
async function uploadDoc(){
  const btn=document.getElementById('uploadBtn'); const resBox=document.getElementById('uploadResult');
  const userId=document.getElementById('userId').value; const docType=document.getElementById('docType').value; const file=document.getElementById('fileInput').files[0];
  if(!file){alert('File select kar bhai'); return;}
  btn.innerText='Uploading...'; btn.disabled=true;
  const fd=new FormData(); fd.append('user_id',userId); fd.append('doc_type',docType); fd.append('file',file);
  try{
    const r=await fetch('/upload-document',{method:'POST',body:fd}); const d=await r.json();
    resBox.classList.remove('hidden'); resBox.innerText=JSON.stringify(d,null,2);
    btn.innerText='✓ SAVED PERMANENT'; setTimeout(()=>{btn.innerText='UPLOAD TO VAULT'; btn.disabled=false;},2000);
  }catch(e){ resBox.classList.remove('hidden'); resBox.innerText='Error: '+e; btn.disabled=false; btn.innerText='UPLOAD TO VAULT';}
}
async function loadVault(){
  const userId=document.getElementById('vaultUserId').value; const box=document.getElementById('vaultResult');
  box.innerHTML='Loading...';
  const r=await fetch('/vault/'+userId); const d=await r.json();
  if(!d.docs || d.docs.length==0){ box.innerHTML='<p class=text-zinc-500>No docs found</p>'; return;}
  box.innerHTML=d.docs.map(x=>`<div class="bg-black border border-zinc-800 p-3 rounded-xl flex justify-between"><span>${x.doc_type}</span><span class="text-zinc-500 text-xs">${x.file_name}</span></div>`).join('');
}
async function loadTemplate(){
  const box=document.getElementById('templateResult');
  const r=await fetch('/form-template/army-agniveer'); const d=await r.json();
  box.innerHTML='<pre class="bg-black p-3 rounded-xl overflow-auto">'+JSON.stringify(d,null,2)+'</pre>';
}
</script>
</body>
</html>
"""

@app.get("/", response_class=HTMLResponse)
def home():
    return FRONTEND_HTML

@app.get("/app", response_class=HTMLResponse)
def app_page():
    return FRONTEND_HTML

@app.get("/api/status")
def api_status():
    return {"status": "Running", "vault_ready": True, "db": "connected" if supabase else "not configured"}

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
    return {"form_name": "ARMY Agniveer", "official_url": "https://joinindianarmy.nic.in", "fields": [{"id": "candidate_name", "from_vault": "aadhaar_name"}, {"id": "father_name", "from_vault": "father_name"}, {"id": "dob", "from_vault": "dob"}]}
