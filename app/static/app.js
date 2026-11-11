'use strict';
const $ = id => document.getElementById(id);
const names={bilibili:'哔哩哔哩',douyin:'抖音',kuaishou:'快手'};
const terminal=new Set(['ready','completed','failed','cancelled']);
let jobId=null,timer=null,preferredKind='video',currentMetadata=null,busy=false;
const states={queued:'任务已加入队列，正在等待处理…',analyzing:'正在读取作品信息，请稍候…',ready:'解析完成，选择你想保存的格式。',downloading:'正在下载，请保持页面打开。',processing:'下载完成，正在处理音视频…',completed:'文件已准备好，现在可以保存到设备。',failed:'处理失败',cancelled:'任务已取消。'};
function toast(message){$('toast').textContent=message;$('toast').hidden=false;clearTimeout(toast.timer);toast.timer=setTimeout(()=>$('toast').hidden=true,3500);}
function setBusy(value){busy=value;$('analyze-button').disabled=value;$('analyze-button').querySelector('span').textContent=value?'处理中…':'解析视频';}
function bytes(value){if(!Number.isFinite(value)||value<=0)return '';const units=['B','KB','MB','GB'];let n=0;while(value>=1024&&n<3){value/=1024;n++;}return value.toFixed(n>1?1:0)+' '+units[n];}
function duration(value){if(!Number.isFinite(value))return '';const seconds=Math.floor(value);return Math.floor(seconds/60)+':'+String(seconds%60).padStart(2,'0');}
async function api(url,body){const response=await fetch(url,{method:body?'POST':'GET',headers:body?{'Content-Type':'application/json'}:{},body:body?JSON.stringify(body):undefined});let data;try{data=await response.json();}catch{throw new Error('服务响应异常，请稍后重试。');}if(!response.ok)throw new Error(typeof data.detail==='string'?data.detail:'请求未成功，请检查输入后重试。');return data;}
function showInputError(message){$('input-error').textContent=message;$('input-error').hidden=false;$('video-url').setAttribute('aria-invalid','true');}
function resetErrors(){$('input-error').hidden=true;$('video-url').removeAttribute('aria-invalid');}
function closeMenu(){$('mega-menu').hidden=true;$('more-toggle').setAttribute('aria-expanded','false');}
function platformSelect(key,scroll=true){
  document.querySelectorAll('.platform-tabs button').forEach(b=>b.setAttribute('aria-pressed',String(b.dataset.platform===key)));
  $('video-url').placeholder=key==='all'?'粘贴视频链接，也可以直接粘贴分享文案':'粘贴'+names[key]+'作品链接或分享文案';
  $('platform-hint').textContent=key==='all'?'接入 B站、抖音、快手 · 实际可用性取决于作品权限与平台响应':names[key]+' · 支持单个公开视频，部分作品可能受登录或平台访问限制';
  closeMenu();if(scroll){$('download-tool').scrollIntoView({behavior:'smooth',block:'start'});$('video-url').focus({preventScroll:true});}
}
document.querySelectorAll('[data-platform]').forEach(b=>b.addEventListener('click',()=>platformSelect(b.dataset.platform,!b.closest('.platform-tabs'))));
document.querySelectorAll('[data-tool]').forEach(b=>b.addEventListener('click',()=>{preferredKind=b.dataset.tool;platformSelect('all');toast(preferredKind==='audio'?'解析后将优先选择 MP3 音频':'解析后选择需要的视频画质');}));
$('more-toggle').addEventListener('click',()=>{const open=$('mega-menu').hidden;$('mega-menu').hidden=!open;$('more-toggle').setAttribute('aria-expanded',String(open));});
document.addEventListener('click',e=>{if(!e.target.closest('.more-wrap'))closeMenu();});
document.addEventListener('keydown',e=>{if(e.key==='Escape'&&!$('mega-menu').hidden){closeMenu();$('more-toggle').focus();}});
document.querySelectorAll('.mega-menu a').forEach(a=>a.addEventListener('click',closeMenu));
$('paste-button').addEventListener('click',async()=>{try{$('video-url').value=await navigator.clipboard.readText();resetErrors();$('video-url').focus();}catch{toast('无法读取剪贴板，请在输入框中手动粘贴。');$('video-url').focus();}});
$('clear-button').addEventListener('click',()=>{$('video-url').value='';resetErrors();$('video-url').focus();});
$('video-url').addEventListener('input',resetErrors);
function renderChoices(metadata){
  currentMetadata=metadata;$('media-details').hidden=false;
  $('media-title').textContent=metadata.title;$('media-platform').textContent=names[metadata.platform]||'视频';
  $('media-meta').textContent=[metadata.uploader,duration(metadata.duration)].filter(Boolean).join(' · ');
  const thumb=$('thumbnail');thumb.hidden=true;$('thumbnail-fallback').hidden=false;
  thumb.onload=()=>{thumb.hidden=false;$('thumbnail-fallback').hidden=true;};thumb.onerror=()=>{thumb.hidden=true;$('thumbnail-fallback').hidden=false;};
  if(metadata.thumbnail&&/^https:\/\//.test(metadata.thumbnail))thumb.src=metadata.thumbnail;else thumb.removeAttribute('src');
  $('choice-list').replaceChildren();
  const initial=metadata.choices.find(c=>c.kind===preferredKind)||metadata.choices[0];
  for(const choice of metadata.choices){
    const label=document.createElement('label');label.className='choice';
    const input=document.createElement('input');input.type='radio';input.name='format';input.value=choice.id;input.checked=choice.id===initial.id;
    const text=document.createElement('span'),strong=document.createElement('strong'),small=document.createElement('small');
    strong.textContent=choice.label;small.textContent=choice.ext.toUpperCase()+(choice.size?' · 约 '+bytes(choice.size):' · 大小待下载确认');
    text.append(strong,small);label.append(input,text);$('choice-list').append(label);
  }
}
function render(data){
  $('result').hidden=false;$('task-status').textContent=data.message||states[data.state]||'正在处理';$('task-status').classList.toggle('failed',data.state==='failed');
  const active=!terminal.has(data.state);setBusy(active);$('cancel-button').hidden=!active;$('download-button').hidden=data.state!=='ready';$('download-button').disabled=false;
  $('save-button').hidden=data.state!=='completed';$('retry-button').hidden=!['failed','cancelled'].includes(data.state);$('expiry-note').hidden=data.state!=='completed';
  $('progress-section').hidden=!['downloading','processing','completed'].includes(data.state);
  if(data.metadata&&data.state==='ready')renderChoices(data.metadata);$('choices').disabled=data.state!=='ready';
  if(data.state==='completed'){$('save-button').href='/api/tasks/'+data.id+'/file';$('save-button').download=data.file.download_name||'video';}
  if(data.progress==null){$('progress').removeAttribute('value');$('progress-number').textContent='';}else{$('progress').value=data.progress;$('progress-number').textContent=Math.round(data.progress)+'%';}
  $('progress-label').textContent=data.state==='processing'?'正在合并或转换':data.state==='completed'?'处理完成':'正在下载当前音视频流';
  const stats=data.stats||{};$('progress-detail').textContent=[bytes(stats.downloaded),stats.speed?bytes(stats.speed)+'/s':'',Number.isFinite(stats.eta)?'预计剩余 '+Math.ceil(stats.eta)+' 秒':''].filter(Boolean).join(' · ');
  if(active)sessionStorage.setItem('vn_active',data.id);else sessionStorage.removeItem('vn_active');
}
function poll(id){
  clearTimeout(timer);timer=setTimeout(async()=>{
    if(jobId!==id)return;
    try{const data=await api('/api/tasks/'+id);if(jobId!==id)return;render(data);if(!terminal.has(data.state))poll(id);}
    catch(error){if(jobId!==id)return;setBusy(false);$('task-status').textContent='暂时无法获取任务状态：'+error.message;$('retry-button').hidden=false;$('cancel-button').hidden=false;}
  },900);
}
async function analyze(){
  if(busy)return;const text=$('video-url').value.trim();resetErrors();
  if(!text){showInputError('请先粘贴视频链接或分享文案。');$('video-url').focus();return;}
  clearTimeout(timer);currentMetadata=null;$('media-details').hidden=true;$('result').hidden=true;setBusy(true);
  try{const data=await api('/api/analyze',{text});jobId=data.id;render(data);poll(jobId);}catch(error){setBusy(false);showInputError(error.message);}
}
$('link-form').addEventListener('submit',e=>{e.preventDefault();analyze();});
$('retry-button').addEventListener('click',async()=>{
  if(jobId){try{const data=await api('/api/tasks/'+jobId);if(!terminal.has(data.state)){render(data);poll(jobId);return;}}catch{}}
  analyze();
});
$('download-button').addEventListener('click',async()=>{
  const choice=document.querySelector('input[name="format"]:checked');if(!choice||!jobId)return;
  $('download-button').disabled=true;resetErrors();
  try{const data=await api('/api/tasks/'+jobId+'/download',{choice:choice.value});render(data);poll(jobId);}catch(error){$('download-button').disabled=false;showInputError(error.message);}
});
$('cancel-button').addEventListener('click',async()=>{
  if(!jobId)return;$('cancel-button').disabled=true;
  try{const data=await api('/api/tasks/'+jobId+'/cancel',{});clearTimeout(timer);render(data);}catch(error){toast(error.message);}finally{$('cancel-button').disabled=false;}
});
$('save-button').addEventListener('click',async e=>{
  e.preventDefault();
  try{const data=await api('/api/tasks/'+jobId);if(data.state!=='completed')throw new Error('文件尚未完成。');window.location.assign('/api/tasks/'+jobId+'/file');}
  catch(error){showInputError(error.message);$('save-button').hidden=true;$('retry-button').hidden=false;}
});
(async()=>{
  const saved=sessionStorage.getItem('vn_active');
  if(saved){try{const data=await api('/api/tasks/'+saved);jobId=saved;render(data);if(data.metadata)renderChoices(data.metadata);$('choices').disabled=data.state!=='ready';if(!terminal.has(data.state))poll(saved);}catch{sessionStorage.removeItem('vn_active');}}
})();
