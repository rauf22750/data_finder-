(() => {
  const toast = (message) => { const el=document.querySelector('#appToast'); if(!el) return; el.querySelector('.toast-body').textContent=message; bootstrap.Toast.getOrCreateInstance(el).show(); };
  document.querySelector('.menu-button')?.addEventListener('click',()=>document.querySelector('.sidebar').classList.toggle('open'));
  const form=document.querySelector('#searchForm');
  const countrySelect=document.querySelector('#countrySelect'), provinceSelect=document.querySelector('#provinceSelect'), citySelect=document.querySelector('#citySelect'), areaSelect=document.querySelector('#areaSelect');
  const customArea=document.querySelector('#customArea');
  const provinceStatus=document.querySelector('#provinceStatus'), cityStatus=document.querySelector('#cityStatus'), areaStatus=document.querySelector('#areaStatus');
  const escapeOption=(value)=>String(value).replace(/[&<>'"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]));
  let locationController;
  const resetSelect=(element,message)=>{element.disabled=true;element.innerHTML=`<option value="">${message}</option>`;};
  async function loadProvinces(){
    resetSelect(provinceSelect,'Loading provinces…');resetSelect(citySelect,'Select a province first');resetSelect(areaSelect,'Select a city first');
    cityStatus.textContent='Cities load after province selection.';areaStatus.textContent='Areas load after city selection.';
    const selected=countrySelect.selectedOptions[0];if(!selected?.dataset.code){provinceStatus.textContent='Choose a country first.';return;}
    locationController?.abort();locationController=new AbortController();provinceStatus.textContent='Loading provinces and states…';
    try{const response=await fetch(`${form.dataset.provincesUrl}?country=${encodeURIComponent(selected.dataset.code)}`,{signal:locationController.signal});const data=await response.json();if(!response.ok||!data.success)throw new Error(data.error||'Provinces could not be loaded.');const provinces=data.provinces.length?data.provinces:[{name:'All regions',code:''}];provinceSelect.innerHTML='<option value="">Select a province / state</option>'+provinces.map(item=>`<option value="${escapeOption(item.name)}" data-code="${escapeOption(item.code)}">${escapeOption(item.name)}</option>`).join('');provinceSelect.disabled=false;provinceStatus.textContent=`${provinces.length} provinces or states available.`;}
    catch(error){if(error.name==='AbortError')return;resetSelect(provinceSelect,'Unable to load provinces');provinceStatus.textContent=error.message;toast(error.message);}
  }
  async function loadCities(){
    const country=countrySelect.selectedOptions[0],province=provinceSelect.value;resetSelect(citySelect,'Loading cities…');resetSelect(areaSelect,'Select a city first');areaStatus.textContent='Areas load after city selection.';
    if(!country?.dataset.code||!province){cityStatus.textContent='Choose a province or state first.';return;}
    locationController?.abort(); locationController=new AbortController(); cityStatus.textContent='Loading cities…';
    try{
      const response=await fetch(`${form.dataset.citiesUrl}?country=${encodeURIComponent(country.dataset.code)}&province=${encodeURIComponent(province)}`,{signal:locationController.signal});
      const data=await response.json(); if(!response.ok||!data.success)throw new Error(data.error||'Cities could not be loaded.');
      citySelect.innerHTML='<option value="">Select a city</option>'+data.cities.map(city=>`<option value="${escapeOption(city)}">${escapeOption(city)}</option>`).join('');
      citySelect.disabled=false; cityStatus.textContent=data.cities.length?`${data.cities.length} cities and towns available.`:'No mapped cities were found.';
    }catch(error){if(error.name==='AbortError')return;citySelect.innerHTML='<option value="">Unable to load cities</option>';cityStatus.textContent=error.message;toast(error.message);}
  }
  async function loadAreas(){
    resetSelect(areaSelect,'Loading areas…');if(!citySelect.value){areaStatus.textContent='Choose a city first.';return;}areaStatus.textContent='Loading areas…';
    customArea.classList.add('d-none');customArea.value='';
    try{const query=new URLSearchParams({country:countrySelect.value,province:provinceSelect.value,city:citySelect.value});const response=await fetch(`${form.dataset.areasUrl}?${query}`);const data=await response.json();if(!response.ok||!data.success)throw new Error(data.error||'Areas could not be loaded.');areaSelect.innerHTML='<option value="">Select an area</option>'+data.areas.map(area=>`<option value="${escapeOption(area)}">${escapeOption(area)}</option>`).join('')+'<option value="__custom__">Other area — type manually</option>';areaSelect.disabled=false;areaStatus.textContent=data.areas.length>1?`${data.areas.length-1} mapped areas plus manual entry available.`:'Select city-wide or type your area manually.';}
    catch(error){resetSelect(areaSelect,'Unable to load areas');areaStatus.textContent=error.message;toast(error.message);}
  }
  countrySelect?.addEventListener('change',loadProvinces);provinceSelect?.addEventListener('change',loadCities);citySelect?.addEventListener('change',loadAreas);
  areaSelect?.addEventListener('change',()=>{const custom=areaSelect.value==='__custom__';customArea.classList.toggle('d-none',!custom);customArea.required=custom;if(custom)customArea.focus();});
  if(form) form.addEventListener('submit',async(e)=>{
    e.preventDefault(); const button=form.querySelector('button[type=submit]'); const normal=button.querySelector('.button-label'); const loading=button.querySelector('.loading-label');
    button.disabled=true; normal.classList.add('d-none'); loading.classList.remove('d-none');
    const payload=Object.fromEntries(new FormData(form)); if(payload.area==='__custom__')payload.area=customArea.value.trim(); payload.limit=Number(payload.limit);
    try{const response=await fetch(form.dataset.searchUrl,{method:'POST',headers:{'Content-Type':'application/json','X-CSRFToken':payload.csrfmiddlewaretoken},body:JSON.stringify(payload)}); const data=await response.json(); if(!response.ok||!data.success) throw new Error(data.error||'Search failed.'); toast(`Found ${data.count} businesses.`); location.href=`${form.dataset.resultsUrl}?search=${data.search_id}`;}
    catch(error){toast(error.message); button.disabled=false; normal.classList.remove('d-none'); loading.classList.add('d-none');}
  });
  const dataNode=document.querySelector('#results-data'); if(!dataNode||!window.RESULTS_CONFIG)return;
  const all=JSON.parse(dataNode.textContent), body=document.querySelector('#resultsBody'), search=document.querySelector('#resultFilter'), presence=document.querySelector('#presenceFilter'), sort=document.querySelector('#resultSort'), selectAll=document.querySelector('#selectAll'); let page=1; const perPage=20;
  const valid=(v)=>v&&v!=='N/A'; const escape=(v)=>String(v??'').replace(/[&<>'"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c]));
  function filtered(){let rows=[...all],q=search.value.toLowerCase().trim(),p=presence.value;if(q)rows=rows.filter(x=>[x.name,x.phone,x.address].some(v=>String(v).toLowerCase().includes(q)));if(p)rows=rows.filter(x=>valid(x[p]));if(sort.value==='az')rows.sort((a,b)=>a.name.localeCompare(b.name));if(sort.value==='za')rows.sort((a,b)=>b.name.localeCompare(a.name));if(sort.value==='website')rows.sort((a,b)=>Number(valid(b.website))-Number(valid(a.website)));if(sort.value==='phone')rows.sort((a,b)=>Number(valid(b.phone))-Number(valid(a.phone)));return rows}
  function render(){const rows=filtered(),pages=Math.max(1,Math.ceil(rows.length/perPage));page=Math.min(page,pages);const visible=rows.slice((page-1)*perPage,page*perPage);body.innerHTML=visible.map((x,i)=>`<tr><td><input class="row-check" type="checkbox" value="${x.id}"></td><td>${(page-1)*perPage+i+1}</td><td class="business-name">${escape(x.name)}</td><td>${escape(x.phone)}</td><td>${escape(x.address)}</td><td>${valid(x.website)?`<a href="${escape(x.website)}" target="_blank" rel="noopener">Visit website ↗</a>`:'<span class="muted">N/A</span>'}</td><td>${escape(x.category)}</td><td>${valid(x.google_maps_url)?`<a href="${escape(x.google_maps_url)}" target="_blank" rel="noopener">View on Maps ↗</a>`:'<span class="muted">N/A</span>'}</td><td class="location">${x.latitude&&x.longitude?`${escape(x.latitude)}, ${escape(x.longitude)}`:'N/A'}</td></tr>`).join('');document.querySelector('#emptyResults').classList.toggle('d-none',rows.length>0);document.querySelector('#visibleCount').textContent=`Showing ${visible.length} of ${rows.length} results`;document.querySelector('#pagination').innerHTML=Array.from({length:pages},(_,i)=>`<button data-page="${i+1}" class="${page===i+1?'active':''}">${i+1}</button>`).join('');selectAll.checked=false;updateSelected();}
  function updateSelected(){document.querySelector('#selectionCount').textContent=`${document.querySelectorAll('.row-check:checked').length} selected`}
  [search,presence,sort].forEach(el=>el.addEventListener(el===search?'input':'change',()=>{page=1;render()}));document.querySelector('#pagination').addEventListener('click',e=>{if(e.target.dataset.page){page=Number(e.target.dataset.page);render()}});body.addEventListener('change',updateSelected);selectAll.addEventListener('change',()=>{document.querySelectorAll('.row-check').forEach(x=>x.checked=selectAll.checked);updateSelected()});
  document.querySelectorAll('.export-button').forEach(button=>button.addEventListener('click',()=>{const url=button.dataset.format==='csv'?RESULTS_CONFIG.csvUrl:RESULTS_CONFIG.excelUrl;let target=`${url}?search=${RESULTS_CONFIG.searchId}`;if(button.dataset.mode==='selected'){const ids=[...document.querySelectorAll('.row-check:checked')].map(x=>x.value);if(!ids.length){toast('Select at least one business to export.');return}target+=`&ids=${ids.join(',')}`}location.href=target}));render();
})();
