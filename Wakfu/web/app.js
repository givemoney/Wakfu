const networkReadOnly=!['127.0.0.1','localhost'].includes(location.hostname);
const $=s=>document.querySelector(s), esc=s=>String(s??'').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const labels={items:'Objets',monsters:'Monstres',npcs:'PNJ',creatures:'À classer',recipes:'Recettes',dungeons:'Donjons',resources:'Ressources',locations:'Récoltes par zone'},glyphs={items:'◇',monsters:'♧',npcs:'♙',creatures:'?',recipes:'⚒',dungeons:'⌂',resources:'❧',locations:'⌖'};
const detailParams=new URLSearchParams(location.search),dedicatedDetail=detailParams.has('fiche');
const detailURL=(k,id)=>'/?fiche='+encodeURIComponent(k)+'&id='+encodeURIComponent(id);
const detailTabLink=(k,id)=>`<a class="detail-tab-link" href="${detailURL(k,id)}" target="_blank" rel="noopener">Ouvrir dans un onglet ↗</a>`;
let locationCoverage='',currentRows=[],view='cards';try{view=localStorage.getItem('wakfu-view')||'cards';}catch{}if(!['cards','list','table'].includes(view))view='cards';
let wantedDungeonItems=new Map(),wantedSequence=0,wantedTimer;
try{const saved=JSON.parse(localStorage.getItem('wakfu-dungeon-wanted')||'[]');if(Array.isArray(saved))for(const x of saved.slice(0,100)){if(Number.isSafeInteger(x.id)&&x.id>0&&x.id<=2147483647&&typeof x.name==='string')wantedDungeonItems.set(x.id,{name:x.name});}}catch{}
let excludedIngredients=new Map(),ingredientSequence=0,ingredientTimer;
let kind='items',offset=0,total=0,searchSequence=0,detailSequence=0,history=[];
async function get(path,params={}){const r=await fetch(path+'?'+new URLSearchParams(params));const data=await r.json();if(!r.ok)throw Error(data.error||'Chargement impossible');return data;}
const clean=s=>String(s??'').replace(/\{\[~1\]\?[^:}]*:\}/g,'');
const name=r=>r.name||'Nom non disponible';
const note=(text)=>`<div class="notice">${esc(text)}</div>`;
const section=(title,body)=>`<h3>${esc(title)}</h3>${body}`;
const art=(k,id,url=null,lookup=false)=>`<span class="art"><span aria-hidden="true">${glyphs[k]}</span>${url||lookup&&!['dungeons','locations'].includes(k)?`<img src="${esc(url||'/api/image?kind='+k+'&id='+id)}" alt="" loading="lazy" decoding="async" referrerpolicy="no-referrer">`:''}</span>`;
document.addEventListener('error',e=>{if(e.target.tagName==='IMG'&&e.target.closest('.art'))e.target.hidden=true;},true);
const link=(k,id,title,sub='',right='↗')=>title?`<button class="row-link" data-open="${k}" data-id="${id}">${art(k,id,null,true)}<span class="row-text">${esc(title)}${sub?`<small>${esc(sub)}</small>`:''}</span><span>${esc(right)}</span></button>`:`<div class="row-link"><span>Nom non disponible<small>${esc(sub)} · fiche non disponible</small></span></div>`;
const list=content=>`<div class="detail-list">${content}</div>`;
async function search(){const seq=++searchSequence;$('#results').innerHTML='<div class="empty">Recherche dans votre encyclopédie…</div>';try{const d=await get('/api/search',{kind,wanted_items:kind==='dungeons'?Array.from(wantedDungeonItems.keys()).join(','):'',loot_categories:kind==='dungeons'?selectedCategories().join(','):'',loot_mode:$('#dungeon-loot-mode').value,loot_rarities:kind==='dungeons'?Array.from(document.querySelectorAll('#rarity-options input:checked'),i=>i.value).join(','):'',learning:['items','recipes'].includes(kind)?$('#learning-filter').value:'',exclude:kind==='recipes'?Array.from(excludedIngredients.keys()).join(','):'',recursive:kind==='recipes'&&$('#ingredient-recursive').checked?'1':'0',q:$('#query').value,min:$('#min').value,max:$('#max').value,sort:$('#sort').value,favorites:['items','recipes'].includes(kind)&&$('#favorites-only').checked?'1':'0',jobs:kind==='recipes'?Array.from(document.querySelectorAll('#job-options input:checked'),i=>i.value).join(','):'',categories:kind==='items'?selectedCategories().join(','):'',rarities:['items','recipes'].includes(kind)?Array.from(document.querySelectorAll('#rarity-options input:checked'),i=>i.value).join(','):'',offset});if(seq!==searchSequence)return;total=d.total;$('#count').textContent=total.toLocaleString('fr-FR')+' résultats';currentRows=d.rows;locationCoverage=d.coverage_message||'';renderResults();$('#previous').disabled=offset===0;$('#next').disabled=offset+36>=total;$('#page').textContent=total?`${offset+1}–${Math.min(offset+36,total)} sur ${total.toLocaleString('fr-FR')}`:'0 résultat';}catch(e){$('#results').innerHTML=note(e.message);}}
const rarityNames={0:'Commun',1:'Inhabituel',2:'Rare',3:'Mythique',4:'Légendaire',5:'Relique',6:'Souvenir',7:'Épique'};
const rarity=r=>Number.isInteger(r.rarity)&&Object.hasOwn(rarityNames,r.rarity)?r.rarity:'none';
const rarityLabel=r=>rarity(r)==='none'?'—':rarityNames[r.rarity];
const favoriteButton=r=>`<button type="button" class="favorite-button" data-favorite="${r.item_id}" data-active="${r.favorite?'1':'0'}" aria-pressed="${!!r.favorite}" aria-label="${r.favorite?'Retirer des favoris':'Ajouter aux favoris'} : ${esc(name(r))}">${r.favorite?'★':'☆'}</button>`;
const learningCheckbox=r=>r.learnable===true&&!networkReadOnly?`<label class="learning-label" data-learning-label><input type="checkbox" data-learned="${r.item_id}" aria-label="Déjà appris : ${esc(name(r))}" ${r.learned?'checked':''}><span>${r.learned?'Déjà appris':'Non appris'}</span></label>`:'';
const personalSummary=r=>`<div class="personal-summary">${learningCheckbox(r)}${r.item_id&&!networkReadOnly?favoriteButton(r):''}${r.note&&!networkReadOnly?`<span class="note-preview" title="${esc(r.note)}">${esc(r.note)}</span>`:''}${detailTabLink(kind,r.id)}${kind==='recipes'?window.RecipeBasket.button(r.id):''}</div>`;
async function savePersonal(data){const response=await fetch('/api/preference',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(data)});const result=await response.json();if(!response.ok)throw Error(result.error||'Enregistrement impossible');return result;}
function syncPersonal(data){currentRows.forEach(r=>{if(r.item_id===data.item_id)Object.assign(r,data);});renderResults();document.querySelectorAll(`[data-learned="${data.item_id}"]`).forEach(b=>{b.checked=!!data.learned;b.parentElement.querySelector('span').textContent=data.learned?'Déjà appris':'Non appris';});document.querySelectorAll(`[data-favorite="${data.item_id}"]`).forEach(b=>{b.dataset.active=data.favorite?'1':'0';b.setAttribute('aria-pressed',String(data.favorite));b.setAttribute('aria-label',data.favorite?'Retirer des favoris':'Ajouter aux favoris');b.textContent=data.favorite?'★':'☆';});}
$('#favorites-only').addEventListener('change',()=>{offset=0;search();});
function renderResults(){
 const box=$('#results');box.className='results-'+view;
 document.querySelectorAll('[data-view]').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.view===view)));
 $('#rarity-legend').hidden=!['items','recipes','dungeons'].includes(kind);
 if(!currentRows.length&&kind==='locations'&&locationCoverage){box.innerHTML=note(locationCoverage);return;}
 if(!currentRows.length){box.innerHTML='<div class="empty">Aucun résultat. Essayez un autre nom ou élargissez les niveaux.</div>';return;}
 if(kind==='dungeons'){box.className='dungeon-tables';box.innerHTML=window.Dungeons.render(currentRows,{esc,art,rarityLabel,clean,detailTabLink,wantedItems:wantedDungeonItems});return;}
 if(kind==='locations'){box.className=view==='cards'?'grid locations-grid':'results-'+view;box.innerHTML=window.Locations.render(currentRows,view,esc,detailTabLink);return;}
 if(view==='table'){
  box.innerHTML=`<div class="table-scroll"><table class="result-table"><caption class="visually-hidden">${esc(labels[kind])} : résultats de recherche</caption><thead><tr><th scope="col">Nom</th><th scope="col">Niveau</th><th scope="col">${kind==='recipes'?'Métier':'Catégorie'}</th>${['items','recipes'].includes(kind)?'<th scope="col">Rareté</th>':''}${['items','recipes'].includes(kind)?'<th scope="col">Mes notes & favoris</th>':''}</tr></thead><tbody>${currentRows.map(r=>`<tr data-rarity="${rarity(r)}" data-open="${kind}" data-id="${r.id}"><td><button class="table-name" data-open="${kind}" data-id="${r.id}">${art(kind,r.id,r.image_url)}<strong>${esc(name(r))}</strong></button></td><td>${r.level??'—'}</td><td>${esc(clean(r.category)||labels[kind])}</td>${['items','recipes'].includes(kind)?`<td class="rarity-text">${esc(rarityLabel(r))}</td>`:''}${r.item_id?`<td class="personal-cell">${personalSummary(r)}</td>`:''}</tr>`).join('')}</tbody></table></div>`;
 }else if(view==='list'){
  box.innerHTML=`<ul class="result-list">${currentRows.map(r=>`<li><button class="list-result" data-rarity="${rarity(r)}" data-open="${kind}" data-id="${r.id}">${art(kind,r.id,r.image_url)}<span class="list-name"><strong>${esc(name(r))}</strong><small>${esc(clean(r.category)||labels[kind])}</small></span><span class="list-meta">${r.level!=null?`<span class="badge">Niv. ${r.level}</span>`:''}${rarity(r)!=='none'?`<span class="rarity-text">${esc(rarityLabel(r))}</span>`:''}</span><span aria-hidden="true">↗</span></button>${personalSummary(r)}</li>`).join('')}</ul>`;
 }else{
  box.classList.add('grid');box.innerHTML=currentRows.map(r=>`<article class="card" data-rarity="${rarity(r)}"><button class="card-open" data-open="${kind}" data-id="${r.id}"><div class="card-top">${art(kind,r.id,r.image_url)}${r.level!=null?`<span class="badge">Niv. ${r.level}</span>`:''}</div><strong>${esc(name(r))}</strong><small>${esc(clean(r.category)||labels[kind])}</small>${rarity(r)!=='none'?`<span class="rarity-text">${esc(rarityLabel(r))}</span>`:''}</button>${personalSummary(r)}</article>`).join('');
 }
}
$('#view-switch').addEventListener('click',e=>{const b=e.target.closest('[data-view]');if(!b)return;view=b.dataset.view;try{localStorage.setItem('wakfu-view',view);}catch{}renderResults();});
function showTipsPage(active){
 $('.collection').hidden=active;$('#tips-page').hidden=!active;
 if(active){kind='tips';searchSequence++;currentRows=[];$('#tips-page').innerHTML=window.Tips.render(esc);$('nav').querySelectorAll('button').forEach(b=>b.classList.toggle('active',b.dataset.kind==='tips'));}
}
function category(k){if((location.pathname==='/panier'||new URLSearchParams(location.search).has('panier')))return;showTipsPage(k==='tips');if(k==='tips')return;kind=labels[k]?k:'items';$('#dungeon-searches').hidden=kind!=='dungeons';offset=0;$('#job-filters').hidden=kind!=='recipes';$('#ingredient-filters').hidden=kind!=='recipes';$('#learning-filters').hidden=!['items','recipes'].includes(kind);$('#category-filters').hidden=!['items','dungeons'].includes(kind);$('#dungeon-loot-filter').hidden=kind!=='dungeons';$('#dungeon-wanted-filter').hidden=kind!=='dungeons';$('#dungeon-wanted-summary').hidden=kind!=='dungeons'||!wantedDungeonItems.size;$('#view-switch').parentElement.hidden=kind==='dungeons';$('#category-filters legend').textContent=kind==='dungeons'?'Types de butin':'Filtrer les objets par catégorie';$('#rarity-filters').hidden=!['items','recipes','dungeons'].includes(kind);$('#favorites-filter').hidden=networkReadOnly||!['items','recipes'].includes(kind);syncLearningQuick();$('#sort').value='level';$('#heading').textContent=labels[kind];$('#query').placeholder={items:'Rechercher un objet, une ressource…',monsters:'Rechercher un monstre…',npcs:'Rechercher un personnage non joueur…',creatures:'Rechercher une créature à classer…',recipes:'Rechercher le produit à fabriquer…',dungeons:'Rechercher un donjon…',resources:'Rechercher une ressource à récolter…',locations:'Rechercher une zone ou une récolte…'}[kind];$('nav').querySelectorAll('button').forEach(b=>b.classList.toggle('active',b.dataset.kind===kind));$('#collection-note').textContent=kind==='monsters'?'Définitions associées à un donjon ou à du butin. Les PNJ identifiés sont exclus ; ce classement reste incomplet.':kind==='npcs'?'Personnages non joueurs identifiés comme membres de clan dans les données officielles.':kind==='creatures'?'Définitions dont la catégorie reste incertaine : possibles PNJ, invocations, variantes ou autres créatures.':kind==='locations'?'Poissons, minerais, bois, récoltes paysannes et d’herboriste par zone. Tri par niveau minimum de métier requis pour les récoltes référencées. Aucun donjon ni butin de monstre.':kind==='dungeons'?'Butins des monstres référencés dans chaque donjon. Un objet apparaît une seule fois par donjon. Les récompenses et conditions non documentées ne sont pas déduites.':kind==='resources'?'Les noms de métiers non identifiés restent indiqués par leur numéro.':'';search();}
function placeDescription(p){
 if(p.relation==='family')return '<div class="plain-row"><strong>'+esc([p.region_name,p.map_name&&p.map_name!==p.region_name?p.map_name:'',p.territory_name&&p.territory_name!==p.map_name?p.territory_name:''].filter(Boolean).join(' › ')||p.world_name||'Carte sans nom')+'</strong><small>Lieu de la famille de monstres : présence de ce monstre non confirmée</small></div>';
 const coordinate=p.entrance_x!=null?'Entrée du donjon : '+(p.entrance_world_name?esc(p.entrance_world_name)+' · ':'')+'('+p.entrance_x+', '+p.entrance_y+', '+p.entrance_z+')':'Entrée du donjon : lieu non renseigné';
 return link('dungeons',p.dungeon_id,p.dungeon_name||'Donjon sans nom',[[p.region_name,p.map_name&&p.map_name!==p.region_name?p.map_name:'',p.territory_name&&p.territory_name!==p.map_name?p.territory_name:''].filter(Boolean).join(' › ')||p.associated_world_name,'Monstre référencé dans ce donjon'].filter(Boolean).join(' · '))+'<div class="plain-row">'+coordinate+'</div>';
}
function entityPlaces(k,d){
 if(!['monsters','creatures','resources','recipes'].includes(k))return '';
 const places=d.places||[];
 const missing=k==='resources'?'Les données importées ne donnent pas les emplacements de cette ressource.':k==='recipes'?'Aucun emplacement d’atelier identifié pour cette recette.':'Aucun lieu identifié pour cette créature.';
 return section(k==='recipes'?'Lieu de fabrication':'Lieux connus',places.map(placeDescription).join('')||note(missing));
}
function acquisitionSources(d){
 const creatures=(d.sources||[]).filter(s=>['monsters','creatures','npcs'].includes(s.kind));
 const others=(d.sources||[]).filter(s=>!creatures.includes(s));
 const creatureBody=creatures.map(s=>'<article class="acquisition-source">'+link(s.kind,s.id,s.name||'Créature sans nom',s.label)+'<div class="source-places">'+((s.places||[]).map(placeDescription).join('')||note('Monstre source identifié ; ses lieux ne sont pas renseignés dans la base.'))+'</div></article>').join('');
 const otherBody=others.map(s=>link(s.kind,s.id,s.name,[s.label,s.kind==='recipes'?(s.category?clean(s.category):'Métier non identifié'):null,s.level!=null?'Niveau requis '+s.level:null].filter(Boolean).join(' · '))).join('');
 return section('Monstres sources et lieux',creatureBody||note('Aucun monstre source référencé pour cet objet.'))+(otherBody?section('Autres moyens d’obtention',list(otherBody)):'')+note('Les lieux de famille sont des pistes, pas des positions confirmées. Les références de butin peuvent avoir des conditions ; les sources et lieux ne sont pas exhaustifs.');
}
async function openDetail(k,id,push=true){if(push)history.push({k,id});const seq=++detailSequence;$('#detail-content').innerHTML='<p>Chargement de la fiche…</p>';$('#open-detail-tab').href=detailURL(k,id);if(dedicatedDetail){document.body.classList.add('dedicated-detail');window.history.replaceState(null,'',detailURL(k,id));if(!$('#detail').open)$('#detail').show();}else if(!$('#detail').open)$('#detail').showModal();$('#back').disabled=history.length<2;try{const d=await get('/api/detail',{kind:k,id});if(seq!==detailSequence)return;if(k==='locations'){window.Locations.detail(d,{escape:esc,link,note,get});$('#detail-content').scrollTop=0;if(dedicatedDetail)document.title=name(d)+' · WAKFU Atlas';return;}let html=`<span class="eyebrow">${esc(labels[k])}</span><div class="detail-heading" data-rarity="${rarity(d)}">${art(k,id,d.image_url)}<h2>${esc(name(d))}</h2></div><div class="pills">${d.level!=null?`<span class="pill">Niveau ${d.level}${d.level_max!=null&&d.level_max!==d.level?'–'+d.level_max:''}</span>`:''}${d.category?`<span class="pill">${esc(clean(d.category))}</span>`:''}${d.family?`<span class="pill">${esc(d.family)}</span>`:''}</div>`;
if(rarity(d)!=='none')html+=`<p class="rarity-text" data-rarity="${rarity(d)}">${esc(rarityLabel(d))}${k==='recipes'?' · rareté du produit':''}</p>`;
html+=entityPlaces(k,d);
if(d.learnable===true)html+=section('Apprentissage du mobilier',learningCheckbox(d)||'<p>Ce produit peut être appris dans le catalogue de décorations.</p>');
if(d.item_id&&!networkReadOnly)html+=section('Mes notes & favoris',`<div class="personal-editor">${favoriteButton(d)}<label for="item-note">Note personnelle${k==='recipes'?' sur le produit fabriqué':''}</label><textarea id="item-note" rows="3" maxlength="5000" placeholder="Votre objectif, une quantité à garder, un rappel…">${esc(d.note||'')}</textarea><button type="button" id="save-note">Enregistrer la note</button><span id="note-status" role="status"></span></div>`);
if(d.description)html+=`<p>${esc(d.description)}</p>`;
if(k==='items'){
html+=acquisitionSources(d);
if(d.used_in.length)html+=section('Utilisé dans ces recettes',list(d.used_in.map(r=>link('recipes',r.recipe_id,r.name,[r.category?clean(r.category):'Métier non identifié',r.level!=null?'Niveau '+r.level:null,'Ingrédient'].filter(Boolean).join(' · '),'× '+r.quantity)).join('')));
if(d.effects.length)html+=`<details><summary>Effets : données officielles non interprétées (${d.effects.length})</summary><p>Les modèles et paramètres sont conservés. Leurs formules ne sont pas encore traduites en caractéristiques lisibles.</p>${d.effects.map(e=>`<p>${esc(e.description||'Effet sans intitulé')}</p><pre>${esc(JSON.stringify(JSON.parse(e.payload),null,2))}</pre>`).join('')}</details>`;
}else if(k==='npcs'){
html+=section('Personnage non joueur',note('Identification fondée sur le catalogue officiel des membres de clan ou sur la famille officielle Membres de clan.'));
html+=section('Repères associés',d.locations.length?d.locations.map(l=>`<div class="plain-row">${esc(l.world_name||'Lieu non identifié')} · (${l.x}, ${l.y}, ${l.z})</div>`).join('')+note('Repères issus des archives ; les conditions d’accès ne sont pas évaluées.'):note('Aucun repère associé identifié.'));
}else if(k==='monsters'||k==='creatures'){
if(k==='creatures')html+=note('Catégorie non déterminée : cette définition n’est pas présentée comme un monstre ni comme un PNJ identifié.');
html+=section('Butins référencés',d.drops.length?list(d.drops.map(r=>link('items',r.id,r.name,'Référence de butin · taux brut '+r.rate_raw)).join(''))+note('Taux bruts conservés pour traçabilité, sans conversion en pourcentage effectif. Les conditions et mécanismes de tirage ne sont pas évalués. Les objets sans nom peuvent être absents de l’export.'):note('Aucun butin référencé dans cette définition.'));
html+=section('Caractéristiques de base',`<div class="pills">${Object.entries(d.stats).map(([s,v])=>`<span class="pill">${({base_hp:'Points de vie',base_ap:'Points d’action',base_mp:'Points de mouvement',base_wp:'Points de Wakfu'})[s]} : ${v}</span>`).join('')}</div><p class="muted">Valeurs de la définition ; aucune évolution selon le niveau ou le mode de donjon n’est calculée.</p>`);
if(d.spells.length)html+=section('Sorts référencés',d.spells.map(s=>`<div class="plain-row">${esc(s.name||'Sort sans intitulé')}</div>`).join(''));
}else if(k==='recipes'){
html+=`<p>${window.RecipeBasket.button(id)}</p>`;
html+=section('Produit',list(d.products.map(r=>link('items',r.id,r.name,'Résultat','× '+r.quantity)).join('')));
html+=section('Ingrédients nécessaires',`<label class="muted">Nombre de fabrications <input id="craft-count" type="number" min="1" max="9999" value="1" style="width:80px;padding:5px;margin:0 0 12px 8px"></label>`+list(d.ingredients.map(r=>link('items',r.id,r.name,'Ingrédient',`× ${r.quantity}`)).join('')));
}else if(k==='dungeons'){
if(d.world)html+=`<p>Monde associé : ${esc(d.world)}</p>`;
html+=section('Entrée du donjon',d.entrances.length?d.entrances.map(e=>`<div class="plain-row">Lieu non identifié · (${e.x}, ${e.y}, ${e.z})</div>`).join(''):note('Coordonnées d’entrée non identifiées.'));
html+=note('Les repères d’entrée peuvent comporter des conditions d’accès qui ne sont pas évaluées.');
html+=section('Créatures associées',d.monsters.length?list(d.monsters.map(m=>link(m.kind||'monsters',m.id,m.name,'Niveau '+m.level)).join('')):note('Aucune créature associée identifiée.'));
}else{
html+=section('Récoltes disponibles',d.harvests.length?d.harvests.map(h=>`<div class="plain-row">Niveau requis ${h.skillLevelRequired} · métier non identifié</div>`+list((h.collectItemId>0?link('items',h.collectItemId,h.item_name,'Récolte directe'):'')+h.loots.map(l=>link('items',l.id,l.name,'Butin de récolte',`${l.quantityMin}–${l.quantityMax}`)).join(''))).join(''):note('Aucune action de récolte associée.'));
}
$('#detail-content').innerHTML=html;$('#detail-content').scrollTop=0;if(dedicatedDetail)document.title=name(d)+' · WAKFU Atlas';
if(d.item_id&&!networkReadOnly)$('#save-note').onclick=async()=>{const button=$('#save-note');button.disabled=true;try{const data=await savePersonal({item_id:d.item_id,note:$('#item-note').value});syncPersonal(data);$('#note-status').textContent='Note enregistrée sur votre ordinateur.';}catch(e){$('#note-status').textContent=e.message;}finally{button.disabled=false;}};
if(k==='recipes')$('#craft-count').addEventListener('input',e=>{let n=Math.min(9999,Math.max(1,Math.floor(Number(e.target.value)||1)));let buttons=$('#craft-count').parentElement.nextElementSibling.querySelectorAll('.row-link');buttons.forEach((b,i)=>b.lastElementChild.textContent='× '+d.ingredients[i].quantity*n);let products=$('#detail-content').querySelectorAll('.detail-list')[0].querySelectorAll('.row-link');products.forEach((b,i)=>b.lastElementChild.textContent='× '+d.products[i].quantity*n);});
}catch(e){if(seq===detailSequence)$('#detail-content').innerHTML=note(e.message);}}
document.addEventListener('click',async e=>{if(e.target.closest('a')||e.target.closest('[data-learning-label]'))return;const star=e.target.closest('[data-favorite]');if(star){star.disabled=true;try{const data=await savePersonal({item_id:Number(star.dataset.favorite),favorite:star.dataset.active!=='1'});syncPersonal(data);$('#personal-status').textContent=data.favorite?'Objet ajouté aux favoris.':'Objet retiré des favoris.';if($('#favorites-only').checked)search();}catch(err){$('#personal-status').textContent=err.message;}finally{star.disabled=false;}return;}const el=e.target.closest('[data-open]');if(el)openDetail(el.dataset.open,Number(el.dataset.id));});
function renderExcludedIngredients(){
 $('#ingredient-selected').innerHTML=Array.from(excludedIngredients,([id,item])=>'<button type="button" class="ingredient-chip" data-remove-ingredient="'+id+'" aria-label="Retirer '+esc(item.name)+'">'+esc(item.name)+' <span aria-hidden="true">×</span></button>').join('');
 $('#ingredient-explanation').textContent=$('#ingredient-recursive').checked?'Une recette reste affichée si une fabrication connue évite tous ces ingrédients. Les composants sans recette connue sont considérés comme des ingrédients de base ; les chaînes incomplètes ou cycliques sont écartées.':'Seuls les ingrédients directs de la recette sont vérifiés.';
}
function clearIngredientExclusions(refresh=true){excludedIngredients.clear();ingredientSequence++;clearTimeout(ingredientTimer);$('#ingredient-query').value='';$('#ingredient-suggestions').innerHTML='';renderExcludedIngredients();if(refresh){offset=0;search();}}
$('#ingredient-query').addEventListener('input',()=>{
 clearTimeout(ingredientTimer);const seq=++ingredientSequence,q=$('#ingredient-query').value.trim();
 if(!q){$('#ingredient-suggestions').innerHTML='';return;}
 ingredientTimer=setTimeout(async()=>{try{const data=await get('/api/search',{kind:'items',q,sort:'name'});if(seq!==ingredientSequence)return;
 $('#ingredient-suggestions').innerHTML=data.rows.length?data.rows.slice(0,12).map(r=>'<button type="button" class="ingredient-option" data-exclude-ingredient="'+r.id+'" data-ingredient-name="'+esc(name(r))+'">'+art('items',r.id,r.image_url)+'<span>'+esc(name(r))+'</span></button>').join(''):'<p>Aucun objet trouvé.</p>';
 }catch(e){if(seq===ingredientSequence)$('#ingredient-suggestions').textContent=e.message;}},200);
});
$('#ingredient-suggestions').addEventListener('click',event=>{const b=event.target.closest('[data-exclude-ingredient]');if(!b)return;if(excludedIngredients.size>=100){$('#ingredient-explanation').textContent='100 ingrédients maximum.';return;}excludedIngredients.set(Number(b.dataset.excludeIngredient),{name:b.dataset.ingredientName});ingredientSequence++;$('#ingredient-query').value='';$('#ingredient-suggestions').innerHTML='';renderExcludedIngredients();offset=0;search();});
$('#ingredient-selected').addEventListener('click',event=>{const b=event.target.closest('[data-remove-ingredient]');if(b){excludedIngredients.delete(Number(b.dataset.removeIngredient));renderExcludedIngredients();offset=0;search();}});
$('#ingredient-recursive').addEventListener('change',()=>{renderExcludedIngredients();offset=0;search();});
$('#ingredient-clear').addEventListener('click',()=>clearIngredientExclusions());
function syncLearningQuick(){
 const value=$('#learning-filter').value;
 $('#learnable-only').checked=['learnable','unlearned','learned'].includes(value);
 $('#unlearned-only').checked=value==='unlearned';
 $('#learnable-quick-label').hidden=kind!=='recipes';
 $('#unlearned-quick-label').hidden=networkReadOnly||kind!=='recipes';
}
$('#learning-filter').addEventListener('change',()=>{syncLearningQuick();offset=0;search();});
$('#learnable-only').addEventListener('change',()=>{$('#learning-filter').value=$('#learnable-only').checked?'learnable':'';syncLearningQuick();offset=0;search();});
$('#unlearned-only').addEventListener('change',()=>{$('#learning-filter').value=$('#unlearned-only').checked?'unlearned':($('#learnable-only').checked?'learnable':'');syncLearningQuick();offset=0;search();});
if(networkReadOnly)document.querySelectorAll('#learning-filter option[value="learned"],#learning-filter option[value="unlearned"]').forEach(o=>o.remove());
document.addEventListener('change',async event=>{const input=event.target.closest('[data-learned]');if(!input)return;const checked=input.checked;input.disabled=true;try{const data=await savePersonal({item_id:Number(input.dataset.learned),learned:checked});syncPersonal(data);$('#personal-status').textContent=data.learned?'Objet marqué déjà appris.':'Objet marqué non appris.';if(['learned','unlearned'].includes($('#learning-filter').value))search();}catch(error){input.checked=!checked;$('#personal-status').textContent=error.message;}finally{input.disabled=false;}});
$('nav').addEventListener('click',e=>{const b=e.target.closest('[data-kind]');if(b){if(dedicatedDetail||(location.pathname==='/panier'||new URLSearchParams(location.search).has('panier')))location.href='/#'+b.dataset.kind;else location.hash=b.dataset.kind;}});window.addEventListener('hashchange',()=>category(location.hash.slice(1)));
function renderWantedDungeonItems(){
 $('#dungeon-wanted-selected').innerHTML=Array.from(wantedDungeonItems,([id,item])=>`<button type="button" class="wanted-chip" data-remove-wanted="${id}" aria-label="Retirer ${esc(item.name)}">${esc(item.name)} <span aria-hidden="true">×</span></button>`).join('');
 $('#dungeon-wanted-status').textContent=wantedDungeonItems.size?`${wantedDungeonItems.size} objet(s) recherché(s). Liste enregistrée dans ce navigateur.`:'Liste vide : tous les donjons sont inclus.';
 $('#dungeon-wanted-summary').textContent=wantedDungeonItems.size?`Objets recherchés : ${Array.from(wantedDungeonItems.values(),i=>i.name).join(', ')}. Les lignes encadrées correspondent à votre liste.`:'';
 $('#dungeon-wanted-summary').hidden=kind!=='dungeons'||!wantedDungeonItems.size;
 try{localStorage.setItem('wakfu-dungeon-wanted',JSON.stringify(Array.from(wantedDungeonItems,([id,item])=>({id,name:item.name}))));}catch{}
}
function clearWantedDungeonItems(refresh=true){wantedDungeonItems.clear();wantedSequence++;clearTimeout(wantedTimer);$('#dungeon-wanted-query').value='';$('#dungeon-wanted-suggestions').innerHTML='';renderWantedDungeonItems();if(refresh){offset=0;search();}}
$('#dungeon-wanted-query').addEventListener('input',()=>{
 clearTimeout(wantedTimer);const seq=++wantedSequence,q=$('#dungeon-wanted-query').value.trim();
 if(!q){$('#dungeon-wanted-suggestions').innerHTML='';return;}
 wantedTimer=setTimeout(async()=>{try{const data=await get('/api/search',{kind:'items',q,sort:'name'});if(seq!==wantedSequence)return;
 const candidates=data.rows.filter(i=>!wantedDungeonItems.has(i.id)).slice(0,12);
 $('#dungeon-wanted-suggestions').innerHTML=candidates.length?candidates.map(i=>`<button type="button" class="ingredient-option" data-add-wanted="${i.id}" data-wanted-name="${esc(name(i))}">${art('items',i.id,null,true)}<span>${esc(name(i))} · Niv. ${i.level??'—'} · ${esc(rarityLabel(i))}</span></button>`).join(''):'<p>Aucun autre objet trouvé.</p>';
 }catch(e){if(seq===wantedSequence)$('#dungeon-wanted-suggestions').textContent=e.message;}},200);
});
$('#dungeon-wanted-suggestions').addEventListener('click',e=>{const b=e.target.closest('[data-add-wanted]');if(!b)return;if(wantedDungeonItems.size>=100){$('#dungeon-wanted-status').textContent='100 objets maximum.';return;}wantedDungeonItems.set(Number(b.dataset.addWanted),{name:b.dataset.wantedName});wantedSequence++;clearTimeout(wantedTimer);$('#dungeon-wanted-query').value='';$('#dungeon-wanted-suggestions').innerHTML='';renderWantedDungeonItems();offset=0;search();$('#dungeon-wanted-query').focus();});
$('#dungeon-wanted-selected').addEventListener('click',e=>{const b=e.target.closest('[data-remove-wanted]');if(b){wantedDungeonItems.delete(Number(b.dataset.removeWanted));renderWantedDungeonItems();offset=0;search();}});
$('#dungeon-wanted-clear').addEventListener('click',()=>clearWantedDungeonItems());
renderWantedDungeonItems();
let timer;$('#query').addEventListener('input',()=>{clearTimeout(timer);timer=setTimeout(()=>{offset=0;search();},200);});$('#filters').addEventListener('submit',e=>{e.preventDefault();offset=0;search();$('#filters-dialog').close();});['min','max','sort'].forEach(s=>$('#'+s).addEventListener('change',()=>{offset=0;search();}));$('#reset').onclick=()=>{HTMLFormElement.prototype.reset.call($('#filters'));syncLearningQuick();clearIngredientExclusions(false);clearWantedDungeonItems(false);$('#favorites-only').checked=false;document.querySelectorAll('#category-options input').forEach(i=>i.indeterminate=false);categoryStatus();offset=0;search();};$('#previous').onclick=()=>{offset=Math.max(0,offset-36);search();};$('#next').onclick=()=>{offset+=36;search();};$('#close').onclick=()=>{if(dedicatedDetail)location.href='/#'+(history.at(-1)?.k||'items');else $('#detail').close();};$('#detail').addEventListener('close',()=>{history=[];detailSequence++;});$('#back').onclick=()=>{history.pop();const r=history.at(-1);if(r)openDetail(r.k,r.id,false);};$('#about').onclick=()=>$('#info').showModal();$('.close-info').onclick=()=>$('#info').close();document.addEventListener('keydown',e=>{if(e.key==='/'&&!['INPUT','TEXTAREA','SELECT'].includes(e.target.tagName)&&!$('#detail').open&&!$('#info').open&&!$('#filters-dialog').open){e.preventDefault();$('#query').focus();}});
get('/api/stats').then(d=>{$('#version').textContent='Version '+d.version;$('#stats').innerHTML=['items','monsters','npcs','recipes','dungeons'].map(k=>`<div class="stat"><strong>${d.counts[k].toLocaleString('fr-FR')}</strong><span>${labels[k].toLowerCase()} ${k==='recipes'?'référencées':k==='npcs'?'identifiés':'référencés'}</span></div>`).join('');$('#build').textContent=`Version ${d.version} · archives ${d.build} · base ${(d.bytes/1048576).toFixed(2)} Mio`;}).catch(e=>$('#version').textContent=e.message);if(dedicatedDetail){const detailKind=detailParams.get('fiche'),detailId=Number(detailParams.get('id'));document.body.classList.add('dedicated-detail');$('#close').textContent='Retour au catalogue';$('#close').setAttribute('aria-label','Retour au catalogue');$('.brand').href='/#items';if(Object.hasOwn(labels,detailKind)&&Number.isSafeInteger(detailId)&&detailId!==0)openDetail(detailKind,detailId);else{$('#detail').show();$('#detail-content').textContent='Fiche introuvable.';}}else category(location.hash.slice(1));


$('#job-options').addEventListener('change',()=>{offset=0;search();});
get('/api/recipe-jobs').then(jobs=>{
 $('#job-options').innerHTML=jobs.map(j=>`<label class="job-option"><input type="checkbox" name="job" value="${j.id}"><span>${esc(j.name||'Métier sans intitulé')}</span><small>${j.count}</small></label>`).join('');
}).catch(e=>$('#job-error').textContent='Impossible de charger les métiers : '+e.message);

let categoryNodes=new Map();
function selectedCategories(){
 return Array.from(document.querySelectorAll('#category-options input:checked')).filter(input=>{
  let parent=categoryNodes.get(Number(input.value))?.parent_id;
  while(parent){if(document.querySelector(`#cat-${parent}`)?.checked)return false;parent=categoryNodes.get(parent)?.parent_id;}
  return true;
 }).map(input=>input.value);
}
function categoryStatus(){const n=selectedCategories().length;$('#category-status').textContent=n?`${n} branche${n>1?'s':''} sélectionnée${n>1?'s':''}`:'Tous les types';}
function categoryMarkup(node){
 categoryNodes.set(node.id,node);
 const label=clean(String(node.name||'Catégorie sans intitulé').replace(/\{\[~1\]\?([^:}]*):\}/g,'$1'));
 const row=`<label class="category-label"><input id="cat-${node.id}" type="checkbox" value="${node.id}"><span>${esc(label)}</span><small>${node.count.toLocaleString('fr-FR')}</small></label>`;
 const branchRow=`<input id="cat-${node.id}" type="checkbox" value="${node.id}" aria-label="Sélectionner ${esc(label)}"><span class="category-title">${esc(label)}</span><small>${node.count.toLocaleString('fr-FR')}</small>`;
 return node.children.length?`<details class="category-branch"><summary>${branchRow}</summary><div class="category-children">${node.children.map(categoryMarkup).join('')}</div></details>`:`<div class="category-leaf">${row}</div>`;
}
$('#category-options').addEventListener('change',event=>{
 const input=event.target;if(input.tagName!=='INPUT')return;
 const setBranch=node=>{const box=document.querySelector(`#cat-${node.id}`);if(box){box.checked=input.checked;box.indeterminate=false;}node.children.forEach(setBranch);};
 const node=categoryNodes.get(Number(input.value));node.children.forEach(setBranch);input.indeterminate=false;
 let parent=node.parent_id;
 while(parent){const ancestor=categoryNodes.get(parent),box=document.querySelector(`#cat-${parent}`);if(!ancestor||!box)break;
  const children=ancestor.children.map(child=>document.querySelector(`#cat-${child.id}`));
  box.checked=children.every(child=>child.checked);box.indeterminate=!box.checked&&children.some(child=>child.checked||child.indeterminate);parent=ancestor.parent_id;
 }
 categoryStatus();offset=0;search();
});
// Checkbox and label clicks should select a category without folding its branch.
$('#category-options').addEventListener('click',event=>{if(event.target.closest('.category-label'))event.stopPropagation();});
const categoriesReady=get('/api/item-categories').then(nodes=>{
 const mainIds=new Set([109,226,758,761,420,295,525,385]);
 const main=nodes.filter(n=>mainIds.has(n.id)),other=nodes.filter(n=>!mainIds.has(n.id));
 $('#category-options').innerHTML=main.map(categoryMarkup).join('')+(other.length?`<details class="category-branch extra-categories"><summary>Autres catégories</summary><div class="category-children">${other.map(categoryMarkup).join('')}</div></details>`:'');categoryStatus();
}).catch(error=>$('#category-status').textContent='Chargement des catégories impossible : '+error.message);

$('#show-filters').onclick=()=>{$('#filters-dialog').showModal();$('#filters').scrollTop=0;};
$('#close-filters').onclick=()=>$('#filters-dialog').close();

$('#rarity-options').innerHTML=Object.entries(rarityNames).map(([id,label])=>`<label class="rarity-option" data-rarity="${id}"><input type="checkbox" value="${id}"><span>${esc(label)}</span></label>`).join('');
$('#rarity-options').addEventListener('change',()=>{offset=0;search();});

['min','max'].forEach(id=>$('#'+id).addEventListener('input',()=>{clearTimeout(timer);timer=setTimeout(()=>{offset=0;search();},200);}));

$('#dungeon-loot-mode').addEventListener('change',()=>{offset=0;search();});

// Named searches are local to this browser and independent of current filters.
class DungeonSearchStore {
 constructor(storage){this.storage=storage;this.key='wakfu-dungeon-searches-v1';}
 read(){const data=JSON.parse(this.storage.getItem(this.key)||'[]');if(!Array.isArray(data)||data.some(r=>!r||typeof r.id!=='string'||typeof r.name!=='string'||!r.filters))throw Error('Les recherches enregistrées sont illisibles. Elles ont été conservées.');return data;}
 put(id,name,filters){name=name.trim();if(!name)throw Error('Donnez un nom à cette recherche.');const records=this.read();if(id){const i=records.findIndex(r=>r.id===id);if(i<0)throw Error('Cette sauvegarde a été supprimée dans un autre onglet.');records[i]={id,name,filters};}else{id=typeof crypto!=="undefined"&&typeof crypto.randomUUID==="function"?crypto.randomUUID():"search-"+Date.now().toString(36)+"-"+Math.random().toString(36).slice(2);records.push({id,name,filters});}this.storage.setItem(this.key,JSON.stringify(records));return id;}
 remove(id){const records=this.read();this.storage.setItem(this.key,JSON.stringify(records.filter(r=>r.id!==id)));}
}

function initDungeonSearches(){
 const select=$('#dungeon-search-select'),nameInput=$('#dungeon-search-name'),status=$('#dungeon-search-status');
 let store;try{store=new DungeonSearchStore(localStorage);}catch{status.textContent='Le navigateur ne permet pas de sauvegarder les recherches.';return;}
 const error=e=>status.textContent=e.name==='QuotaExceededError'?'Le stockage du navigateur est plein. Cette sauvegarde n’a pas été enregistrée ; les précédentes sont conservées.':e.message;
 function refresh(){try{const current=select.value,records=store.read();select.innerHTML='<option value="">Choisir une recherche ('+records.length+')</option>'+records.map(r=>'<option value="'+esc(r.id)+'">'+esc(r.name)+'</option>').join('');select.value=records.some(r=>r.id===current)?current:'';['load','update','delete'].forEach(action=>$('#dungeon-search-'+action).disabled=!select.value);}catch(e){error(e);}}
 function snapshot(){return {q:$('#query').value,min:$('#min').value,max:$('#max').value,sort:$('#sort').value,lootMode:$('#dungeon-loot-mode').value,rarities:Array.from(document.querySelectorAll('#rarity-options input:checked'),i=>i.value),categories:Array.from(document.querySelectorAll('#category-options input:checked'),i=>i.value),partialCategories:Array.from(document.querySelectorAll('#category-options input'),i=>i.indeterminate?i.value:null).filter(Boolean),wanted:Array.from(wantedDungeonItems,([id,item])=>({id,name:item.name}))};}
 async function apply(filters){
  await categoriesReady;
  if(!categoryNodes.size)throw Error('Les catégories n’ont pas pu être chargées. Réessayez après avoir rechargé la page.');
  clearTimeout(timer);clearWantedDungeonItems(false);
  $('#query').value=filters.q||'';$('#min').value=filters.min||'';$('#max').value=filters.max||'';
  $('#sort').value=['level','level_desc','name'].includes(filters.sort)?filters.sort:'level';
  $('#dungeon-loot-mode').value=filters.lootMode==='exclude'?'exclude':'include';
  const checked=new Set(filters.categories||[]),partial=new Set(filters.partialCategories||[]),rarities=new Set(filters.rarities||[]);
  document.querySelectorAll('#category-options input').forEach(i=>{i.checked=checked.has(i.value);i.indeterminate=partial.has(i.value);});
  document.querySelectorAll('#rarity-options input').forEach(i=>i.checked=rarities.has(i.value));
  for(const item of filters.wanted||[])if(Number.isSafeInteger(item.id)&&item.id>0&&typeof item.name==='string')wantedDungeonItems.set(item.id,{name:item.name});
  renderWantedDungeonItems();categoryStatus();offset=0;await search();
 }
 select.addEventListener('change',()=>{try{const record=store.read().find(r=>r.id===select.value);nameInput.value=record?.name||'';status.textContent=record?'Cliquez sur « Charger » pour retrouver cette recherche.':'';refresh();}catch(e){error(e);}});
 $('#dungeon-search-save').addEventListener('click',()=>{try{const id=store.put(null,nameInput.value,snapshot());refresh();select.value=id;refresh();status.textContent='Recherche enregistrée : '+nameInput.value.trim()+'.';}catch(e){error(e);}});
 $('#dungeon-search-load').addEventListener('click',async()=>{try{const record=store.read().find(r=>r.id===select.value);if(!record)throw Error('Choisissez une recherche enregistrée.');nameInput.value=record.name;status.textContent='Recherche chargée : '+record.name+'.';await apply(record.filters);}catch(e){error(e);}});
 $('#dungeon-search-update').addEventListener('click',()=>{try{store.put(select.value,nameInput.value,snapshot());refresh();status.textContent='Nom et filtres mis à jour : '+nameInput.value.trim()+'.';}catch(e){error(e);}});
 $('#dungeon-search-delete').addEventListener('click',()=>{try{const id=select.value;if(!id)return;store.remove(id);nameInput.value='';refresh();status.textContent='Sauvegarde supprimée. Les filtres affichés restent utilisables.';}catch(e){error(e);}});
 $('#dungeon-search-new').addEventListener('click',async()=>{try{select.value='';nameInput.value='';refresh();status.textContent='Nouvelle recherche. Vos sauvegardes sont conservées.';await apply({});}catch(e){error(e);}});
 window.addEventListener('storage',e=>{if(e.key===store.key)refresh();});
 refresh();
}
initDungeonSearches();
