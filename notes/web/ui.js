'use strict';
const el=id=>document.getElementById(id);
let controller=null,rows=[],source='',complete=false,origin='',summaryComplete=false;
const time=s=>String(Math.floor(s/60)).padStart(2,'0')+':'+String(Math.floor(s%60)).padStart(2,'0');
function buttons(){
  const busy=!!controller;
  el('stop').disabled=!busy;el('run').disabled=busy;el('link').disabled=busy;
  el('summarize').disabled=busy||!complete;el('save').disabled=busy||!rows.length;
}
async function stream(path,body,consume){
  controller=new AbortController();buttons();
  try{
    const r=await fetch('/notes/'+path,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify(body),signal:controller.signal});
    if(!r.ok)throw Error('服务返回 '+r.status+'，请检查输入后重试。');
    const reader=r.body.pipeThrough(new TextDecoderStream()).getReader();
    let buffer='',finished=false;
    while(true){
      const {done,value}=await reader.read();if(done)break;
      buffer+=value;
      let boundary;
      while((boundary=/\r?\n\r?\n/.exec(buffer))){
        const frame=buffer.slice(0,boundary.index);buffer=buffer.slice(boundary.index+boundary[0].length);
        const lines=frame.split(/\r?\n/),type=lines.find(x=>x.startsWith('event:'))?.slice(6).trim();
        const data=lines.filter(x=>x.startsWith('data:')).map(x=>x.slice(5).trimStart()).join('\n');
        if(!data)continue;
        const v=JSON.parse(data);
        if(type==='failure')throw Error(v);
        consume(type,v);
        if(type==='done')finished=true;
      }
    }
    if(!finished)throw Error('连接中断，结果未完成。');
  }catch(e){el('state').textContent=e.name==='AbortError'?'已停止；已收到的文字可以导出。':e.message;}
  finally{controller?.abort();controller=null;buttons();}
}
el('form').onsubmit=async e=>{
  e.preventDefault();rows=[];complete=false;summaryComplete=false;source='';origin=el('link').value.trim();
  el('text').textContent=el('summary').textContent='';el('state').textContent='正在连接…';
  await stream('transcript',{text:origin},(kind,v)=>{
    if(kind==='segment'){rows.push(v);el('text').append(document.createTextNode('['+time(v.start)+'] '+v.text+'\n'));}
    if(kind==='status')el('state').textContent=v;
    if(kind==='source'){source=v;el('state').textContent='文字来源：'+v;}
    if(kind==='done'){complete=!!rows.length;el('state').textContent='逐字稿已完成 · '+source;}
  });
};
el('summarize').onclick=async()=>{
  el('summary').textContent='';summaryComplete=false;el('state').textContent='正在生成章节摘要…';
  await stream('summary',{rows:rows.map(({start,text})=>({start,text}))},(kind,v)=>{
    if(kind==='delta')el('summary').append(document.createTextNode(v));
    if(kind==='done'){summaryComplete=true;el('state').textContent='摘要已完成，可以导出笔记。';}
  });
};
el('stop').onclick=()=>controller?.abort();
el('save').onclick=()=>{
  const note='# 视频手记\n\n来源：'+origin+'\n\n文字来源：'+source+'\n\n'+(el('summary').textContent?'# 章节摘要'+(summaryComplete?'':'（未完成）')+'\n'+el('summary').textContent:'')+'\n\n# 逐字稿'+(complete?'':'（未完成）')+'\n\n'+el('text').textContent;
  const a=document.createElement('a');a.href=URL.createObjectURL(new Blob([note],{type:'text/markdown;charset=utf-8'}));a.download='视频手记.md';a.click();setTimeout(()=>URL.revokeObjectURL(a.href),1000);
};
