window.Dungeons={render(dungeons,{esc,art,rarityLabel,clean,detailTabLink,wantedItems=new Map()}){
 return dungeons.map(d=>`<section class="dungeon-loot"><header><div><h2><button class="table-name" data-open="dungeons" data-id="${d.id}">${esc(d.name||'Donjon sans nom · #'+d.id)}</button></h2><p>Niveau ${d.level??'non renseigné'} · ${d.loot.length} butin(s) affiché(s) sur ${d.loot_total} · Tri : rareté décroissante, puis taux de référence croissant</p></div>${detailTabLink('dungeons',d.id)}</header>${d.loot.length?`<div class="table-scroll"><table class="result-table"><caption class="visually-hidden">Butins de ${esc(d.name||'ce donjon')}</caption><thead><tr><th scope="col">Objet</th><th scope="col">Niveau</th><th scope="col">Type</th><th scope="col">Rareté</th><th scope="col">Monstres sources</th></tr></thead><tbody>${d.loot.map(item=>`<tr class="${wantedItems.has(item.id)?'wanted-loot':''}" data-rarity="${Number.isInteger(item.rarity)?item.rarity:'none'}"><td>${item.known?`<button class="table-name" data-open="items" data-id="${item.id}" data-item-preview="${item.id}">${art('items',item.id,null,true)}<strong>${esc(item.name||'Objet sans nom · #'+item.id)}</strong>${wantedItems.has(item.id)?'<span class="wanted-badge">Recherché</span>':''}</button>`:`<span>${esc(item.name||'Objet non renseigné · #'+item.id)}</span>`}</td><td>${item.level??'—'}</td><td>${esc(clean(item.category)||'Type non renseigné')}</td><td>${esc(rarityLabel(item))}</td><td>${item.sources.map(m=>`<button class="loot-source" data-open="monsters" data-id="${m.id}">${esc(m.name||'Monstre #'+m.id)}</button>`).join('')}</td></tr>`).join('')}</tbody></table></div>`:`<p class="notice">${d.loot_total?'Aucun butin ne correspond aux filtres choisis.':'Aucun butin de monstre référencé dans la base pour ce donjon.'}</p>`}${d.unresolved_loot?`<p class="loot-coverage">${d.unresolved_loot} référence(s) de butin sans objet dans le catalogue, non affichée(s).</p>`:''}</section>`).join('');
}};

(()=>{
 const cache=new Map();let timer=null,active=null,revision=0;
 const tip=document.createElement('div');tip.id='item-hover-preview';tip.className='item-hover-preview';tip.setAttribute('role','tooltip');tip.hidden=true;document.body.append(tip);
 const escape=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
 function hide(){clearTimeout(timer);revision++;if(active)active.removeAttribute('aria-describedby');active=null;tip.hidden=true;}
 function position(button){const b=button.getBoundingClientRect(),width=Math.min(360,innerWidth-24);tip.style.width=width+'px';tip.style.left=Math.max(12,Math.min(b.left,innerWidth-width-12))+'px';let top=b.bottom+8;if(top+tip.offsetHeight>innerHeight-12)top=Math.max(12,b.top-tip.offsetHeight-8);tip.style.top=top+'px';}
 async function show(button){hide();active=button;const current=revision;timer=setTimeout(async()=>{
  try{let data=cache.get(button.dataset.itemPreview);if(!data){const response=await fetch('/api/detail?kind=items&id='+encodeURIComponent(button.dataset.itemPreview));if(!response.ok)throw Error();data=await response.json();cache.set(button.dataset.itemPreview,data);}
   if(current!==revision||active!==button||!button.isConnected)return;
   const groups=[['equipEffects','Caractéristiques'],['useEffects','Attaque / utilisation'],['useCriticalEffects','Coup critique']];
   const effects=data.formatted_effects||[];
   const blocks=groups.map(([kind,label])=>{const lines=effects.filter(e=>e.kind===kind);return lines.length?`<h4>${label}</h4><ul>${lines.map(e=>'<li>'+escape(e.text)+'</li>').join('')}</ul>`:'';}).join('');
   tip.innerHTML=`<strong>${escape(data.name||'Objet')}</strong><p>Niveau ${data.level??'—'} · ${escape(String(data.category||'Type non renseigné').replace(/\{\[~1\]\?[^:}]*:\}/g,''))}</p>${blocks||'<p>Aucun effet renseigné.</p>'}`;
   tip.hidden=false;button.setAttribute('aria-describedby',tip.id);position(button);
  }catch{if(current===revision){tip.innerHTML='Caractéristiques indisponibles. Cliquez pour ouvrir la fiche.';tip.hidden=false;position(button);}}
 },220);}
 document.addEventListener('pointerover',e=>{const b=e.target.closest('[data-item-preview]');if(b&&active!==b)show(b);});
 document.addEventListener('pointerout',e=>{const b=e.target.closest('[data-item-preview]');if(b&&!b.contains(e.relatedTarget))hide();});
 document.addEventListener('focusin',e=>{const b=e.target.closest('[data-item-preview]');if(b)show(b);});
 document.addEventListener('focusout',e=>{if(e.target.closest('[data-item-preview]'))hide();});
 document.addEventListener('keydown',e=>{if(e.key==='Escape')hide();});document.addEventListener('click',hide);window.addEventListener('scroll',hide,true);window.addEventListener('resize',hide);
})();
