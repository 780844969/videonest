import {renderNotes} from './reader.js';
let fine=false, block=null, frame=0;
const get = id => document.getElementById(id);
const tool = get('download-tool'), form = get('link-form'), input = get('video-url');
let task = null, rows = [], origin = '', source = '', transcriptDone = false, summaryDone = false, summary = '';
const stamp = sec => [Math.floor(sec / 60), Math.floor(sec % 60)].map(n => String(n).padStart(2, '0')).join(':');
const isNotes = () => tool.dataset.mode === 'notes';

function setMode(notes, updateHash = true) {
  tool.dataset.mode = notes ? 'notes' : 'download';
  get('mode-notes').setAttribute('aria-pressed', String(notes));
  get('mode-download').setAttribute('aria-pressed', String(!notes));
  get('notes-panel').hidden = !notes;
  get('run').hidden = !notes;
  get('run').type = notes ? 'submit' : 'button';
  get('analyze-button').hidden = notes;
  get('analyze-button').type = notes ? 'button' : 'submit';
  get('input-error').hidden = true;
  input.removeAttribute('aria-invalid');
  if (updateHash) history.replaceState(null, '', notes ? '#transcript' : '#download-tool');
}

function followAnchor() {
  if (location.hash === '#transcript') {
    setMode(true, false);
    tool.scrollIntoView({behavior:'instant', block:'start'});
  } else if (location.hash === '#download-tool') setMode(false, false);
}
get('mode-notes').onclick = () => setMode(true);
get('mode-download').onclick = () => setMode(false);
document.querySelectorAll('[data-tool]').forEach(button => button.addEventListener('click', () => setMode(false)));
window.addEventListener('hashchange', followAnchor);
setMode(false, false);
followAnchor();

function controls() {
  get('run').disabled = !!task;
  get('stop').hidden = !task;
  get('fill-example').disabled = !!task;
  get('summarize').disabled = !!task || !transcriptDone;
  get('summarize').textContent = summaryDone ? '重新生成摘要' : '生成摘要';
  get('save').disabled = !!task || !rows.length;
}
function status(text, kind = 'pending') {
  get('state').textContent = text;
  get('state').dataset.kind = kind;
}
function notice(text) {
  get('source-note').hidden = !text;
  get('source-note').textContent = text;
}

async function stream(path, body, onEvent) {
  const ctrl = new AbortController();
  task = ctrl;
  controls();
  try {
    const reply = await fetch('/notes/' + path, {method:'POST', signal:ctrl.signal,
      headers:{'Content-Type':'application/json'}, body:JSON.stringify(body)});
    if (!reply.ok || !reply.headers.get('content-type')?.includes('text/event-stream'))
      throw new Error('服务未返回结果，请检查链接并重试。');
    const reader = reply.body.pipeThrough(new TextDecoderStream()).getReader();
    let buffer = '', finished = false;
    while (true) {
      const {value, done} = await reader.read();
      if (done) break;
      buffer += value;
      let sep;
      while ((sep = /\r?\n\r?\n/.exec(buffer))) {
        const lines = buffer.slice(0, sep.index).split(/\r?\n/);
        buffer = buffer.slice(sep.index + sep[0].length);
        const kind = lines.find(x => x.startsWith('event:'))?.slice(6).trim();
        const raw = lines.filter(x => x.startsWith('data:')).map(x => x.slice(5).trimStart()).join('\n');
        if (!raw) continue;
        const data = JSON.parse(raw);
        if (kind === 'failure') throw new Error(data);
        onEvent(kind, data);
        if (kind === 'done') finished = true;
      }
    }
    if (!finished) throw new Error('连接已中断；已收到的文字可以导出。');
  } catch (e) {
    status(ctrl.signal.aborted ? '已停止。' : e.message, ctrl.signal.aborted ? 'idle' : 'error');
  } finally {
    ctrl.abort();
    task = null;
    controls();
  }
}

function sourceLink(raw) {
  const m = raw.match(/https?:\/\/[^\s<>]+/i);
  try { return m ? new URL(m[0]) : null; } catch { return null; }
}
function fragmentTime(row) {
  const url = sourceLink(origin);
  // Only Bilibili publishes a seek query for these canonical video URLs.
  if (url && ['www.bilibili.com','bilibili.com'].includes(url.hostname)
      && /^\/video\/(?:BV\w+|av\d+)\/?$/i.test(url.pathname) && !url.port) {
    const target = new URL(url.pathname, 'https://www.bilibili.com');
    const p = url.searchParams.get('p');
    if (p && /^\d+$/.test(p)) target.searchParams.set('p', p);
    target.searchParams.set('t', String(Math.floor(row.start)));
    const a = document.createElement('a');
    a.href = target.href; a.target = '_blank'; a.rel = 'noopener noreferrer';
    a.setAttribute('aria-label', '打开原片 '+stamp(row.start)+'（新标签页）');
    a.textContent = stamp(row.start); return a;
  }
  const t = document.createElement('time');
  t.dateTime = 'PT'+Math.floor(row.start)+'S'; t.textContent = stamp(row.start); return t;
}
function renderSegment(row) {
  rows.push(row);
  addLine(row);
}
function addLine(row) {
  get('empty-text').hidden = true;
  if(!fine && block && row.start-block.start<25 && row.start-block.lastEnd<3 && block.span.textContent.length<165){
    block.span.append(document.createTextNode(' '+row.text));block.lastEnd=row.end;
    return;
  }
  const li = document.createElement('li'), text = document.createElement('span');
  text.textContent = row.text;
  li.append(fragmentTime(row), text);
  get('text').append(li);
  block={start:row.start,lastEnd:row.end,span:text};
  get('segment-count').textContent = get('text').childElementCount+(fine?' 句':' 段');
}
get('detail-toggle').onclick=()=>{
  fine=!fine;get('detail-toggle').textContent=fine?'按段阅读':'逐句查看';
  get('detail-toggle').setAttribute('aria-pressed',String(fine));
  block=null;get('text').replaceChildren();rows.forEach(addLine);
};
function renderDelta(part) {
  summary += part;
  if(!frame)frame=requestAnimationFrame(()=>{frame=0;renderNotes(get('summary'),summary);});
}
form.addEventListener('submit', e => {
  if (!isNotes()) return;
  e.preventDefault(); e.stopImmediatePropagation();
  if (task) return;
  const value = input.value.trim();
  if (!value) {
    get('input-error').textContent = '请先粘贴视频链接或分享文案。';
    get('input-error').hidden = false; input.setAttribute('aria-invalid', 'true'); input.focus(); return;
  }
  get('input-error').hidden = true; input.removeAttribute('aria-invalid');
  origin = value; rows = []; block=null; transcriptDone = summaryDone = false; summary = source = '';
  const url = sourceLink(origin);
  get('workspace').hidden = false;
  const name = url ? url.host.replace(/^www\./,'') + url.pathname : '视频笔记';
  get('work-title').textContent = name;
  get('text').replaceChildren(); get('summary').replaceChildren();
  get('empty-text').hidden = false; get('segment-count').textContent = '0 段';
  status('正在检查平台字幕…'); notice('');
  stream('transcript', {text:value}, (kind, data) => {
    if (kind === 'title') get('work-title').textContent=data;
    if (kind === 'notice') notice(data);
    if (kind === 'status') {
      status(data);
      if (/登录|受限/.test(data)) notice(data);
    }
    if (kind === 'source') { source = data; status('文字来源：'+data); }
    if (kind === 'segment') renderSegment(data);
    if (kind === 'done') {
      transcriptDone = !!rows.length;
      status(rows.length ? '逐字稿已完成 · '+source+' · '+rows.length+' 段' : '未收到可用字幕。', rows.length ? 'done' : 'idle');
    }
  });
}, true);
get('fill-example').onclick = () => {
  input.value = 'https://bilibili.com/video/BV1mAAmzqEfP';
  input.dispatchEvent(new Event('input')); input.focus();
};
get('summarize').onclick = () => {
  if(!transcriptDone || task) return;
  summaryDone = false; summary = ''; get('summary').replaceChildren();
  status('正在生成章节摘要…');
  stream('summary', {rows:rows.map(({start,text}) => ({start,text}))}, (kind, data) => {
    if (kind === 'delta') renderDelta(data);
    if (kind === 'done') { summaryDone = true; status('摘要已完成，可以导出笔记。', 'done'); }
  });
};
get('stop').onclick = () => task?.abort();
get('save').onclick = () => {
  const note = '# '+get('work-title').textContent+'\n\n来源：'+origin+'\n\n文字来源：'+source+
    (summary ? '\n\n# 章节摘要'+(summaryDone ? '' : '（未完成）')+'\n'+summary : '')+
    '\n\n# 逐字稿'+(transcriptDone ? '' : '（未完成）')+'\n\n'+rows.map(r=>'['+stamp(r.start)+'] '+r.text).join('\n');
  const link = document.createElement('a');
  link.href = URL.createObjectURL(new Blob([note],{type:'text/markdown;charset=utf-8'}));
  link.download = '视频手记.md'; link.click();
  setTimeout(()=>URL.revokeObjectURL(link.href),1000);
};
