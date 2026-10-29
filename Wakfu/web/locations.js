'use strict';
window.Locations={
 level(place){return 'Récolte : métiers niv. '+place.level+(place.level_max!==place.level?'–'+place.level_max:'');},
 render(places,view,escape,tabLink){
  const level=p=>escape(this.level(p));
  const count=p=>p.component_count+' récolte'+(p.component_count!==1?'s':'')+' référencée'+(p.component_count!==1?'s':'');
  if(view==='table')return '<div class="table-scroll"><table class="result-table"><thead><tr><th>Zone</th><th>Niveaux de récolte</th><th>Récoltes</th></tr></thead><tbody>'+places.map(p=>'<tr><td><button class="table-name" data-open="locations" data-id="'+p.id+'"><span><strong>'+escape(p.name)+'</strong><small>'+escape(p.category)+'</small></span></button></td><td>'+level(p)+'</td><td>'+count(p)+'</td></tr>').join('')+'</tbody></table></div>';
  if(view==='list')return '<ul class="result-list">'+places.map(p=>'<li><button class="list-result" data-open="locations" data-id="'+p.id+'"><span class="art" aria-hidden="true">⌖</span><span class="list-name"><strong>'+escape(p.name)+'</strong><small>'+escape(p.category)+'</small><small>'+level(p)+'</small></span><span class="list-meta">'+count(p)+'</span><span aria-hidden="true">↗</span></button></li>').join('')+'</ul>';
  return places.map(p=>'<article class="card location-card"><button class="card-open" data-open="locations" data-id="'+p.id+'"><div class="card-top"><span class="art" aria-hidden="true">⌖</span><span class="location-count">'+count(p)+'</span></div><strong>'+escape(p.name)+'</strong><small>'+escape(p.category)+'</small><small>'+level(p)+'</small></button><div class="personal-summary">'+tabLink('locations',p.id)+'</div></article>').join('');
 },
 detail(data,{escape,link,note}){
  const groups=[['fish','Poissons'],['ores','Minerais'],['wood','Bois'],['crops','Récoltes paysannes'],['herbs','Récoltes d’herboriste']];
  document.querySelector('#detail-content').innerHTML='<span class="eyebrow">ZONES DE RÉCOLTE</span><h2>'+escape(data.name)+'</h2><div class="pills"><span class="pill">'+escape(data.category)+'</span><span class="pill">'+escape(this.level(data))+'</span></div>'+note('Zones référencées dans les données officielles d’écosystème. La présence actuelle d’une ressource dépend de l’état de la zone ; cette liste ne donne pas des positions précises.')+groups.map(([key,label])=>{
   const items=data.components.filter(item=>item.category_key===key);
   return '<section class="harvest-group"><h3>'+escape(label)+' <small>('+items.length+')</small></h3><div class="detail-list">'+(items.length?items.map(item=>link('items',item.id,item.name||'Objet #'+item.id,'Niveau de métier requis : '+item.harvest_level)).join(''):'<p class="muted">Aucune récolte de ce type référencée dans cette zone.</p>')+'</div></section>';
  }).join('');
 }
};
