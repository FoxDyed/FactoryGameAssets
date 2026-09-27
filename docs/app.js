'use strict';
const $ = id => document.getElementById(id);
let catalog, activeCollection, currentCategory='All', visible=36, matching=[], viewerIndex=0, focusBeforeViewer;
let filters={query:'',from:'',to:'',demo:'',sort:'default'};
const {validDate,collectionItems,sortByDate}=GalleryFilters;
const demoLabels={'in-demo':'In current demo','not-in-demo':'Not in current demo',unknown:'Unverified'};
const esc = value => String(value).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const count = n => n.toLocaleString();
const quantity = (n,word) => `${count(n)} ${word}${n===1?'':'s'}`;
const readableDate = value => new Date(value+'T12:00:00Z').toLocaleDateString(undefined,{year:'numeric',month:'short',day:'numeric',timeZone:'UTC'});
const itemDate = item => item.createdDate ? `${readableDate(item.createdDate)}${item.createdDateBasis==='estimated'?' · est.':''}` : 'Date unknown';

function filterLink(collection=activeCollection?.id,category=currentCategory) {
  const params=new URLSearchParams();
  if(collection)params.set('collection',collection);
  if(category!=='All')params.set('type',category);
  for(const [key,value] of Object.entries({q:filters.query,from:filters.from,to:filters.to,demo:filters.demo,sort:filters.sort==='default'?'':filters.sort}))if(value)params.set(key,value);
  return '#'+params.toString();
}

function syncControls() {
  $('search').value=filters.query;
  $('date-from').value=filters.from;
  $('date-to').value=filters.to;
  $('demo-status').value=filters.demo;
  $('sort').value=filters.sort;
}

function updateFilters() {
  filters={query:$('search').value,from:$('date-from').value,to:$('date-to').value,demo:$('demo-status').value,sort:$('sort').value};
  visible=36;
  history.replaceState(null,'',filterLink());
  render();
}

function resetFilters() {
  filters={query:'',from:'',to:'',demo:'',sort:'default'};currentCategory='All';visible=36;
  syncControls();history.replaceState(null,'',filterLink());render();$('search').focus();
}

function collectionDates(items) {
  const dates=items.map(item=>item.createdDate).filter(Boolean).sort();
  if(!dates.length)return 'Dates unknown';
  const range=dates[0]===dates.at(-1)?readableDate(dates[0]):`${readableDate(dates[0])} – ${readableDate(dates.at(-1))}`;
  return range+(items.some(item=>item.createdDateBasis==='estimated')?' · incl. estimates':'')+(dates.length<items.length?' · some undated':'');
}

function route() {
  const params = new URLSearchParams(location.hash.slice(1));
  activeCollection = catalog.collections.find(c => c.id === params.get('collection'));
  currentCategory = catalog.categories.includes(params.get('type')) ? params.get('type') : 'All';
  filters={query:params.get('q')||'',from:validDate(params.get('from'))?params.get('from'):'',to:validDate(params.get('to'))?params.get('to'):'',demo:Object.hasOwn(demoLabels,params.get('demo'))?params.get('demo'):'',sort:['newest','oldest'].includes(params.get('sort'))?params.get('sort'):'default'};
  visible=36;syncControls();
  $('back').hidden=!activeCollection;
  $('eyebrow').textContent=activeCollection ? `${activeCollection.category.toUpperCase()} / ${(activeCollection.reviewState||'Working study').toUpperCase()}` : 'FOXDYED / THE ART ARCHIVE';
  $('page-title').innerHTML=activeCollection ? esc(activeCollection.title) : 'Asset & art galleries<span>.</span>';
  $('description').textContent=activeCollection ? activeCollection.description : 'Concepts, creatures and the worlds they inhabit.';
  $('archive-count').innerHTML=activeCollection ? `<strong>${count(activeCollection.items.length)}</strong> previews` : `<strong>${count(catalog.collections.length)}</strong> collections<br> ${count(Object.keys(catalog.media).length)} artworks & previews`;
  $('results-title').textContent=activeCollection ? 'Inside this collection' : 'The collections';
  $('categories').hidden=!!activeCollection;
  $('search').placeholder=activeCollection ? 'Find an artwork…' : 'Find art or a gallery…';
  $('search').setAttribute('aria-label',activeCollection ? 'Search artworks' : 'Search galleries');
  document.title=activeCollection ? `${activeCollection.title} — Factory Game Assets` : 'Factory Game Assets — Art galleries';
  render();
}

function render() {
  for (const button of $('categories').children) button.setAttribute('aria-pressed', String(button.textContent===currentCategory));
  const invalid=!!(filters.from&&filters.to&&filters.from>filters.to);
  $('filter-error').hidden=!invalid;
  $('filter-error').textContent=invalid?'The end date must be on or after the start date.':'';
  $('date-from').setAttribute('aria-invalid',String(invalid));$('date-to').setAttribute('aria-invalid',String(invalid));
  $('back').href=filterLink(null);
  if (activeCollection) {
    matching=sortByDate(collectionItems(activeCollection,catalog.media,filters),filters.sort);
  } else {
    matching=catalog.collections.filter(c=>currentCategory==='All'||c.category===currentCategory).map(c=>({...c,matchedItems:collectionItems(c,catalog.media,filters)})).filter(c=>c.matchedItems.length);
    matching=sortByDate(matching,filters.sort,c=>{
      const dates=c.matchedItems.map(item=>item.createdDate).filter(Boolean).sort();
      return filters.sort==='oldest'?dates[0]:dates.at(-1);
    });
  }
  $('results-count').textContent=quantity(matching.length,activeCollection ? 'preview' : 'collection');
  $('grid').innerHTML=matching.slice(0,visible).map((entry,index) => {
    const item=activeCollection ? entry : entry.matchedItems.find(item=>item.id===entry.cover)||entry.matchedItems[0];
    const picture=`<div class="picture"><img src="${esc(item.thumb)}" alt="${esc(activeCollection?entry.title:entry.title+' collection preview')}" loading="${index<8?'eager':'lazy'}" decoding="async" width="560" height="420">${activeCollection&&item.type!=='image'?`<span class="badge">${item.type==='video'?'▶ VIDEO':'ANIMATION'}</span>`:''}</div>`;
    const total=activeCollection?'':entry.matchedItems.length===entry.items.length?quantity(entry.items.length,'preview'):`${count(entry.matchedItems.length)} of ${count(entry.items.length)} previews`;
    const metadata=activeCollection?`<p class="card-date">${esc(itemDate(item))}</p><span class="demo-tag ${esc(item.demoStatus||'unknown')}">${esc(demoLabels[item.demoStatus]||demoLabels.unknown)}</span>`:`<p class="card-date">${esc(collectionDates(entry.matchedItems))}</p>`;
    const body=`${picture}<div class="card-meta"><span>${esc(activeCollection?item.type:entry.category)}</span><span>${total}</span></div><h3>${esc(entry.title)}</h3>${metadata}`;
    return activeCollection ? `<button class="card" data-index="${index}" type="button" aria-label="View ${esc(entry.title)}">${body}</button>` : `<a class="card" href="${esc(filterLink(entry.id))}">${body}</a>`;
  }).join('');
  $('grid').setAttribute('aria-busy','false');
  $('empty').hidden=matching.length!==0;
  $('load-more').hidden=matching.length<=visible;
  $('load-more').textContent=`Show more (${count(Math.max(0,matching.length-visible))} remaining)`;
}

function openViewer(index) {
  viewerIndex=(index+matching.length)%matching.length;
  const item=matching[viewerIndex];
  $('full-media').replaceChildren();
  const media=document.createElement(item.type==='video'?'video':'img');
  media.src=item.url;
  if(item.type==='video'){media.controls=true;media.loop=true;media.playsInline=true;media.poster=item.thumb;media.preload='metadata';}
  else {media.alt=item.title;media.decoding='async';}
  $('full-media').append(media);
  $('viewer-title').textContent=item.title;
  $('dimensions').textContent=item.type==='video'?'Video preview':`${count(item.width)} × ${count(item.height)} ${item.derivedPreview?'rendered':'original'} · ${item.type==='animation'?'animated':'image'} preview`;
  $('position').textContent=`${viewerIndex+1} / ${matching.length}`;
  $('open-media').href=item.url;
  $('source').textContent=item.source;
  $('source-hash').textContent=`Source SHA-256: ${item.sha256}${item.provenanceNote?' · '+item.provenanceNote:''}`;
  $('viewer-metadata').textContent=`Created: ${itemDate(item)} · ${demoLabels[item.demoStatus]||demoLabels.unknown}`;
  $('date-evidence').textContent=item.createdDateEvidence||'Creation date unavailable.';
  $('demo-evidence').textContent=item.demoEvidence||'Current demo membership is unverified.';
  $('previous').disabled=$('next').disabled=matching.length<2;
  if(!$('viewer').open){focusBeforeViewer=document.activeElement;$('viewer').showModal();document.body.style.overflow='hidden';$('close').focus();}
}

$('grid').addEventListener('click',event=>{const target=event.target.closest('[data-index]');if(target)openViewer(Number(target.dataset.index));});
$('close').addEventListener('click',()=>$('viewer').close());
$('viewer').addEventListener('close',()=>{$('full-media').replaceChildren();document.body.style.overflow='';if(focusBeforeViewer?.isConnected)focusBeforeViewer.focus();});
$('viewer').addEventListener('click',event=>{if(event.target===$('viewer')){const box=$('viewer').getBoundingClientRect();if(event.clientX<box.left||event.clientX>box.right||event.clientY<box.top||event.clientY>box.bottom)$('viewer').close();}});
$('previous').addEventListener('click',()=>openViewer(viewerIndex-1));
$('next').addEventListener('click',()=>openViewer(viewerIndex+1));
$('viewer').addEventListener('keydown',event=>{if(event.target.tagName==='VIDEO')return;if(event.key==='ArrowLeft'){event.preventDefault();openViewer(viewerIndex-1);}if(event.key==='ArrowRight'){event.preventDefault();openViewer(viewerIndex+1);}});
$('search').addEventListener('input',updateFilters);
for(const id of ['date-from','date-to','demo-status','sort'])$(id).addEventListener('change',updateFilters);
$('reset').addEventListener('click',resetFilters);
$('clear-filters').addEventListener('click',resetFilters);
$('load-more').addEventListener('click',()=>{const firstNew=visible;visible+=36;render();$('grid').children[firstNew]?.focus();});
window.addEventListener('hashchange',()=>{if($('viewer').open)$('viewer').close();route();window.scrollTo(0,0);});

async function init(){
  try{
    const response=await fetch('data/catalog.json');
    if(!response.ok)throw new Error('Catalog unavailable');
    catalog=await response.json();
    $('categories').innerHTML=['All',...catalog.categories].map(category=>`<button type="button" aria-pressed="false">${esc(category)}</button>`).join('');
    $('categories').addEventListener('click',event=>{const button=event.target.closest('button');if(!button)return;location.hash=filterLink(null,button.textContent);});
    $('updated').textContent=`Updated ${new Date(catalog.updated).toLocaleDateString(undefined,{year:'numeric',month:'short',day:'numeric'})}`;
    const demoDate=catalog.demo?.checkedAt?.slice(0,10);
    $('demo-note').textContent=catalog.demo?.verification==='verified'?`Demo status checked ${readableDate(demoDate)} against the current delivered demo. Unverified means the exact artwork version could not be confirmed.`:'Current demo artwork could not be verified. Statuses will update after the next verified catalog refresh.';
    route();
  }catch(error){$('grid').setAttribute('aria-busy','false');$('grid').innerHTML='<div class="error-panel"><h2>The archive couldn’t load.</h2><p>Please reload the page to try again.</p></div>';$('archive-count').textContent='Archive unavailable';}
}
init();
