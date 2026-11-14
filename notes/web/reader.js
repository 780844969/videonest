// Deliberately narrow Markdown dialect. Model output is always text, never HTML.
export function renderNotes(root, markdown) {
  const doc=document.createDocumentFragment();
  const node=(tag,parent,text='')=>{const n=document.createElement(tag); parent.append(n);
    for(const part of text.split(/(\*\*[^*]+\*\*)/)){if(part.startsWith('**')&&part.endsWith('**')&&part.length>4){
      const b=document.createElement('strong');b.textContent=part.slice(2,-2);n.append(b);
    }else n.append(document.createTextNode(part));}return n;};
  const cells=s=>s.trim().replace(/^\||\|$/g,'').split('|').map(x=>x.trim());
  const lines=markdown.split('\n');
  let list=null;
  for(let i=0;i<lines.length;i++){
    const s=lines[i].trim();if(!s){list=null;continue;}
    const head=s.match(/^(#{1,4})\s+(.+)/);
    if(head){list=null;node(head[1].length===1?'h3':'h4',doc,head[2]);continue;}
    if(s.includes('|')&&lines[i+1]?.includes('|')&&cells(lines[i+1]).every(x=>/^:?-{2,}:?$/.test(x))){
      list=null;const wrap=node('div',doc);wrap.className='notes-table';const table=node('table',wrap);
      const tr=node('tr',node('thead',table));cells(s).forEach(c=>node('th',tr,c));
      const body=node('tbody',table);i++;
      while(i+1<lines.length&&lines[i+1].includes('|')){const row=node('tr',body);cells(lines[++i]).forEach(c=>node('td',row,c));}
      continue;
    }
    const bullet=s.match(/^([-*]|\d+[.)])\s+(.+)/);
    if(bullet){const tag=/^\d/.test(bullet[1])?'OL':'UL';if(list?.tagName!==tag)list=node(tag.toLowerCase(),doc);node('li',list,bullet[2]);continue;}
    list=null;node('p',doc,s);
  }
  root.replaceChildren(doc);
}
