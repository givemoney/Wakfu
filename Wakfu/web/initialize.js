'use strict';
const button=document.querySelector('#install');
const statusText=document.querySelector('#status');
let timer;
function show(data){
  document.querySelector('#version').textContent=data.version || '—';
  statusText.textContent=data.message;
  button.disabled=data.state==='running' || data.state==='ready';
  button.textContent=data.state==='error' ? 'Réessayer l’installation' : 'Initialiser la base';
  document.querySelector('#progress').hidden=data.state!=='running';
  document.querySelector('#open').hidden=data.state!=='ready';
  clearTimeout(timer);
  if(data.state==='running') timer=setTimeout(refresh,2000);
}
async function refresh(){
  try{
    const response=await fetch('/api/initialization',{cache:'no-store'});
    if(!response.ok) throw new Error('Impossible de vérifier l’installation. Ouvrez cette page depuis http://127.0.0.1 et gardez le serveur ouvert.');
    show(await response.json());
  }catch(error){statusText.textContent=error.message;button.disabled=true;timer=setTimeout(refresh,5000);}
}
button.addEventListener('click',async()=>{
  button.disabled=true;
  try{
    const response=await fetch('/api/initialize',{method:'POST',headers:{'Content-Type':'application/json'},body:'{}'});
    const data=await response.json();
    if(!response.ok) throw new Error(data.error || 'L’installation ne peut pas démarrer.');
    show(data);
  }catch(error){statusText.textContent=error.message;button.disabled=false;}
});
refresh();
