let watchId=null,current=null,timer=null,authModeName="login";
const $=id=>document.getElementById(id);
function toast(x){$("toast").textContent=x;$("toast").classList.add("show");setTimeout(()=>$("toast").classList.remove("show"),2800)}
function go(p){document.querySelectorAll(".page").forEach(x=>x.classList.remove("active"));document.querySelectorAll("nav button").forEach(x=>x.classList.remove("active"));$(""+p).classList.add("active");document.querySelector(`nav button[data-page="${p}"]`)?.classList.add("active");$("pageTitle").textContent=p==="dashboard"?"Dashboard":p.replace("-"," ").replace(/\b\w/g,m=>m.toUpperCase());window.scrollTo(0,0)}
document.querySelectorAll("nav button[data-page]").forEach(b=>b.onclick=()=>go(b.dataset.page));
function toggleSide(){document.querySelector(".sidebar").classList.toggle("show")}
function openAuth(){ $("authModal").classList.add("open"); }
function closeModal(id){$(id).classList.remove("open")}
function authMode(m){authModeName=m;$("authName").style.display=m==="register"?"block":"none";$("authTitle").textContent=m==="register"?"Create your account":"Welcome back";$("authSub").textContent=m==="register"?"Set up your personal safety dashboard.":"Sign in to access your safety dashboard.";$("loginTab").classList.toggle("selected",m==="login");$("regTab").classList.toggle("selected",m==="register");$("authMsg").textContent=""}
$("authForm").onsubmit=async e=>{e.preventDefault();let d={email:$("authEmail").value,password:$("authPass").value};if(authModeName==="register")d.name=$("authName").value;let r=await fetch("/api/"+authModeName,{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify(d)});let x=await r.json();if(!x.ok){$("authMsg").textContent=x.message;return}closeModal("authModal");toast("Welcome, "+x.name);loadUser()}
async function loadUser(){let d=await (await fetch("/api/me")).json();if(d.user){$("sideName").textContent=d.user.name;$("sideStatus").textContent="Account active";$("topName").textContent=d.user.name;if(d.user.role==="admin")toast("Admin account detected — /admin available")}loadContacts();loadReports()}
function startLive(){
  if(!("geolocation" in navigator)) return toast("GPS is not supported by this browser.");
  if(watchId!==null) return toast("Live tracking is already running.");
  navigator.geolocation.getCurrentPosition(
    p=>{
      updatePosition(p);
      watchId=navigator.geolocation.watchPosition(
        updatePosition,
        err=>{
          console.warn("GPS watch error:",err);
          toast(err.code===1?"Location permission was denied.":"Unable to update GPS location.");
        },
        {enableHighAccuracy:true,maximumAge:5000,timeout:15000}
      );
      $("liveBadge").textContent="● LIVE";
      $("liveBadge").className="badge live";
      toast("Live location started");
    },
    err=>{
      if(err.code===1) toast("Please allow location permission in your browser.");
      else if(err.code===2) toast("Your location could not be determined.");
      else toast("GPS timed out. Try again outdoors or near a window.");
    },
    {enableHighAccuracy:true,maximumAge:0,timeout:15000}
  );
}

function stopLive(){
  if(watchId!==null){
    navigator.geolocation.clearWatch(watchId);
    watchId=null;
  }
  $("liveBadge").textContent="● OFFLINE";
  $("liveBadge").className="badge off";
  $("statusText").textContent="Location sharing stopped";
  toast("Live location stopped");
}

async function updatePosition(p){
  current={
    lat:p.coords.latitude,
    lng:p.coords.longitude,
    accuracy:Number.isFinite(p.coords.accuracy)?p.coords.accuracy:null
  };
  $("lat").textContent=current.lat.toFixed(6);
  $("lng").textContent=current.lng.toFixed(6);
  $("acc").textContent=current.accuracy!==null?Math.round(current.accuracy)+" m":"—";
  $("updated").textContent=new Date().toLocaleTimeString();
  $("dashLocation").textContent="Live GPS";
  $("dashCoords").textContent=current.lat.toFixed(5)+", "+current.lng.toFixed(5);
  $("statusText").textContent="Location sharing active";
  const left=Math.max(5,Math.min(95,50+((current.lng%1)*12)));
  const top=Math.max(5,Math.min(95,50-((current.lat%1)*12)));
  $("livePin").style.left=left+"%";
  $("livePin").style.top=top+"%";

  try{
    const r=await fetch("/api/location",{
      method:"POST",
      headers:{"Content-Type":"application/json"},
      body:JSON.stringify(current)
    });
    if(!r.ok) console.warn("Location was not stored on server.");
  }catch(e){
    console.warn("Location storage unavailable:",e);
  }
}

function locationUrl(){
  return current ? `https://www.google.com/maps/search/?api=1&query=${current.lat},${current.lng}` : "";
}

async function shareLocation(){
  if(!current){
    if(!("geolocation" in navigator)) return toast("GPS is not supported by this browser.");
    toast("Getting your current location…");
    navigator.geolocation.getCurrentPosition(
      p=>{ updatePosition(p); setTimeout(()=>shareLocation(),150); },
      err=>toast(err.code===1?"Please allow location permission first.":"Unable to get your location."),
      {enableHighAccuracy:true,maximumAge:0,timeout:15000}
    );
    return;
  }

  const url=locationUrl();
  const text=`My current SafeHer location is: ${url}`;

  // Native share works on supported phones/browsers.
  if(navigator.share){
    try{
      await navigator.share({title:"My SafeHer location",text,url});
      toast("Location shared");
      return;
    }catch(e){
      if(e.name==="AbortError") return;
    }
  }

  // Clipboard fallback, then open Maps so the link is still usable.
  try{
    await navigator.clipboard.writeText(text);
    toast("Location link copied — opening Google Maps");
  }catch(e){
    const ta=document.createElement("textarea");
    ta.value=text;
    ta.style.position="fixed";
    ta.style.opacity="0";
    document.body.appendChild(ta);
    ta.select();
    try{document.execCommand("copy");}catch(_){}
    ta.remove();
    toast("Opening your live location");
  }
  window.open(url,"_blank","noopener,noreferrer");
}

function getOnce(){
  if(!("geolocation" in navigator)) return toast("GPS is not supported by this browser.");
  navigator.geolocation.getCurrentPosition(
    p=>updatePosition(p),
    err=>toast(err.code===1?"Please allow location permission in your browser.":"Unable to get your location."),
    {enableHighAccuracy:true,maximumAge:0,timeout:15000}
  );
}

function activateSOS(){
  // Always show the emergency UI immediately.
  $("sosModal").classList.add("open");
  $("statusText").textContent="SOS active";
  $("statusText").parentElement.parentElement.classList.add("danger-status");
  toast("SOS activated");

  // Use the latest GPS position, or request one if needed.
  if(current){
    sendSOS(current);
    return;
  }
  if("geolocation" in navigator){
    toast("SOS active — getting your location…");
    navigator.geolocation.getCurrentPosition(
      p=>{updatePosition(p);sendSOS(current);},
      ()=>sendSOS({}),
      {enableHighAccuracy:true,maximumAge:0,timeout:10000}
    );
  }else{
    sendSOS({});
  }
}

async function sendSOS(coords){
  try{
    const r=await fetch("/api/sos",{
      method:"POST",
      headers:{"Content-Type":"application/json"},
      body:JSON.stringify(coords||{})
    });
    const d=await r.json().catch(()=>({}));
    if(!r.ok || d.ok===false) throw new Error(d.message||"SOS could not be stored");
    toast("SOS alert recorded successfully");
  }catch(e){
    // The emergency interface still works even if the local server/database is unavailable.
    console.warn("SOS storage error:",e);
    toast("SOS is active. Call 112 if you need immediate help.");
  }
}

function callNumber(n){
  toast("Opening emergency call "+n);
  window.location.href="tel:"+n;
}

let fakeCallTimer=null;
function startFakeCall(){
  $("fakeCall").classList.add("active");
  const answer=$("fakeCallAnswer");
  const title=$("fakeCallTitle");
  if(answer) answer.textContent="✓";
  if(title) title.textContent="Mom";
  clearTimeout(fakeCallTimer);
}

function answerFakeCall(){
  const title=$("fakeCallTitle");
  const sub=$("fakeCallSub");
  const answer=$("fakeCallAnswer");
  if(title) title.textContent="Connected";
  if(sub) sub.textContent="00:00 • Fake Call";
  if(answer) answer.style.display="none";
  toast("Fake call connected");
  let seconds=0;
  clearInterval(fakeCallTimer);
  fakeCallTimer=setInterval(()=>{
    seconds++;
    if(sub){
      const m=String(Math.floor(seconds/60)).padStart(2,"0");
      const s=String(seconds%60).padStart(2,"0");
      sub.textContent=`${m}:${s} • Fake Call`;
    }
  },1000);
}

function endFakeCall(){
  clearInterval(fakeCallTimer);
  fakeCallTimer=null;
  $("fakeCall").classList.remove("active");
  const answer=$("fakeCallAnswer");
  if(answer) answer.style.display="";
}

function addContact(){let name=prompt("Contact name");if(!name)return;let phone=prompt("Phone number");if(!phone)return;let relation=prompt("Relation")||"Trusted contact";fetch("/api/contacts",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({name,phone,relation})}).then(r=>r.json()).then(d=>{if(d.ok){toast("Contact added");loadContacts()}else toast(d.message||"Login required")})}
async function loadContacts(){let d=await (await fetch("/api/contacts")).json();if(!d.ok){$("contactsGrid").innerHTML='<div class="empty card">Sign in to add trusted contacts.</div>';return}$("contactCount").textContent=d.contacts.length+" contact"+(d.contacts.length===1?"":"s");$("contactsGrid").innerHTML=d.contacts.map(c=>`<div class="contact-card"><div class="contact-avatar">👤</div><div class="contact-info"><b>${esc(c.name)}</b><small>${esc(c.relation||"Trusted contact")}</small><strong>${esc(c.phone)}</strong></div><a href="tel:${esc(c.phone)}" class="call-circle">📞</a></div>`).join("")||'<div class="empty card">No trusted contacts yet. Add someone you trust.</div>'}
$("reportForm").onsubmit=async e=>{e.preventDefault();let f=new FormData(e.target);if(current){f.append("lat",current.lat);f.append("lng",current.lng)}let d=await (await fetch("/api/incidents",{method:"POST",body:f})).json();if(d.ok){toast("Report submitted");e.target.reset();loadReports()}else toast(d.message||"Login required")}
async function loadReports(){let d=await (await fetch("/api/incidents")).json();if(!d.ok){$("reportsList").innerHTML="<p>Sign in to view your reports.</p>";return}$("reportsList").innerHTML=d.incidents.map(x=>`<div class="report-item"><div class="report-icon">🚨</div><div><b>${esc(x.type)}</b><small>${esc(x.date)} · ${esc(x.severity)}</small><p>${esc(x.details)}</p></div></div>`).join("")||"<p>No reports submitted.</p>"}
function openCheckin(){go("checkin")}
async function startCheckin(min){let d=await (await fetch("/api/checkin",{method:"POST",headers:{"Content-Type":"application/json"},body:JSON.stringify({minutes:min})})).json();if(!d.ok)return toast("Sign in to start a check-in");let end=new Date(d.expires);clearInterval(timer);$("checkTitle").textContent="Check-in active";$("timerMessage").textContent="Confirm you're safe when you arrive.";timer=setInterval(()=>{let s=Math.max(0,Math.floor((end-new Date())/1000)),m=Math.floor(s/60),sec=s%60;$("timerDisplay").textContent=String(m).padStart(2,"0")+":"+String(sec).padStart(2,"0");$("dashTimer").textContent=m+" min remaining";if(!s){clearInterval(timer);$("checkTitle").textContent="Check-in expired";$("timerMessage").textContent="Please confirm your safety.";activateSOS()}},500);toast("Safety timer started")}
function safeNow(){clearInterval(timer);$("timerDisplay").textContent="✓";$("checkTitle").textContent="You're safe";$("timerMessage").textContent="Check-in completed successfully.";toast("Glad you're safe")}
function nearby(q){window.open("https://www.google.com/maps/search/"+encodeURIComponent(q)," _blank")}
function esc(s){return String(s??"").replace(/[&<>"']/g,m=>({"&":"&amp;","<":"&lt;",">":"&gt;",'"':"&quot;","'":"&#039;"}[m]))}
$("themeBtn").onclick=()=>{document.body.classList.toggle("dark");localStorage.theme=document.body.classList.contains("dark")?"dark":"light"};if(localStorage.theme==="dark")document.body.classList.add("dark");
document.querySelectorAll(".modal").forEach(m=>m.addEventListener("click",e=>{if(e.target===m)m.classList.remove("open")}));
loadUser();

