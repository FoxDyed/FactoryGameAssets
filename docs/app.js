'use strict';
const $ = id => document.getElementById(id);
let catalog, activeCollection, currentCategory='All', query='', visible=36, matching=[], viewerIndex=0, focusBeforeViewer;
const esc = value => String(value).replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const count = n => n.toLocaleString();
const quantity = (n,word) => `${count(n)} ${word}${n===1?'':'s'}`;

function route() {
  const params = new URLSearchParams(location.hash.slice(1));
  activeCollection = catalog.collections.find(c => c.id === params.get('collection'));
  currentCategory = catalog.categories.includes(params.get('type')) ? params.get('type') : 'All';
  query=''; visible=36; $('search').value='';
  $('back').hidden=!activeCollection;
  $('eyebrow').textContent=activeCollection ? `${activeCollection.category.toUpperCase()} / ${(activeCollection.reviewState||'Working study').toUpperCase()}` : 'FOXDYED / THE ART ARCHIVE';
  $('page-title').innerHTML=activeCollection ? esc(activeCollection.title) : 'Asset & art galleries<span>.</span>';
  $('description').textContent=activeCollection ? activeCollection.description : 'Concepts, creatures and the worlds they inhabit.';
  $('archive-count').innerHTML=activeCollection ? `<strong>${count(activeCollection.items.length)}</strong> previews` : `<strong>${count(catalog.collections.length)}</strong> collections<br> ${count(Object.keys(catalog.media).length)} artworks & previews`;
  $('results-title').textContent=activeCollection ? 'Inside this collection' : 'The collections';
  $('categories').hidden=!!activeCollection;
  $('search').placeholder=activeCollection ? 'Find an artwork…' : 'Find a gallery…';
  $('search').setAttribute('aria-label',activeCollection ? 'Search artworks' : 'Search galleries');
  document.title=activeCollection ? `${activeCollection.title} — Factory Game Assets` : 'Factory Game Assets — Art galleries';
  render();
}

function render() {
  for (const button of $('categories').children) button.setAttribute('aria-pressed', String(button.textContent===currentCategory));
  if (activeCollection) {
    matching=activeCollection.items.map(id => catalog.media[id]).filter(item => `${item.title} ${item.source}`.toLowerCase().includes(query));
  } else {
    matching=catalog.collections.filter(c => (currentCategory==='All'||c.category===currentCategory) && `${c.title} ${c.category} ${c.source}`.toLowerCase().includes(query));
  }
  $('results-count').textContent=quantity(matching.length,activeCollection ? 'preview' : 'collection');
  $('grid').innerHTML=matching.slice(0,visible).map((entry,index) => {
    const item=activeCollection ? entry : catalog.media[entry.cover];
    const picture=`<div class="picture"><img src="${esc(item.thumb)}" alt="${esc(activeCollection?entry.title:entry.title+' collection preview')}" loading="${index<8?'eager':'lazy'}" decoding="async" width="560" height="420">${activeCollection&&item.type!=='image'?`<span class="badge">${item.type==='video'?'▶ VIDEO':'ANIMATION'}</span>`:''}</div>`;
    const body=`${picture}<div class="card-meta"><span>${esc(activeCollection?item.type:entry.category)}</span><span>${activeCollection?'':quantity(entry.items.length,'preview')}</span></div><h3>${esc(entry.title)}</h3>`;
    return activeCollection ? `<button class="card" data-index="${index}" type="button" aria-label="View ${esc(entry.title)}">${body}</button>` : `<a class="card" href="#collection=${entry.id}">${body}</a>`;
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
$('search').addEventListener('input',event=>{query=event.target.value.toLowerCase().trim();visible=36;render();});
$('reset').addEventListener('click',()=>{query='';$('search').value='';visible=36;render();$('search').focus();});
$('load-more').addEventListener('click',()=>{const firstNew=visible;visible+=36;render();$('grid').children[firstNew]?.focus();});
window.addEventListener('hashchange',()=>{if($('viewer').open)$('viewer').close();route();window.scrollTo(0,0);});

async function init(){
  try{
    const response=await fetch('data/catalog.json');
    if(!response.ok)throw new Error('Catalog unavailable');
    catalog=await response.json();
    $('categories').innerHTML=['All',...catalog.categories].map(category=>`<button type="button" aria-pressed="false">${esc(category)}</button>`).join('');
    $('categories').addEventListener('click',event=>{const button=event.target.closest('button');if(!button)return;location.hash=button.textContent==='All'?'':`type=${encodeURIComponent(button.textContent)}`;});
    $('updated').textContent=`Updated ${new Date(catalog.updated).toLocaleDateString(undefined,{year:'numeric',month:'short',day:'numeric'})}`;
    route();
  }catch(error){$('grid').setAttribute('aria-busy','false');$('grid').innerHTML='<div class="error-panel"><h2>The archive couldn’t load.</h2><p>Please reload the page to try again.</p></div>';$('archive-count').textContent='Archive unavailable';}
}
init();
