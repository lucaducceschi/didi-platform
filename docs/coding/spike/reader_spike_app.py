# Proof of concept only, kept as a reference for the position logic. See docs/coding/PRD.md, Section 3.
import unicodedata, json
import streamlit as st

TEXTS = {
 "plain": "Plain text with target words here.\n\nSecond paragraph target too.",
 "emoji": "Emoji first 🙂🙂🙂 then TARGET-EMOJI ends the sentence.\n\nNext.",
 "nfd": unicodedata.normalize("NFD", "Gherdëina ëëë dlëijia ") + "TARGET-NFD ends.",
 "crlf": "Line one\r\nLine two\r\nTARGET-CRLF ends.",
 "markdown": "Has *stars* and _underscores_ and $math$ then TARGET-MD ends. <b>tag</b> stays.",
}
JS = """
export default function(component) {
  const { data, parentElement, setTriggerValue } = component;
  const root = parentElement.querySelector('#didi-reader');
  const text = data.text;
  // render: split into spans at highlight boundaries; positions are code points
  const cps = Array.from(text);
  const bounds = new Set([0, cps.length]);
  for (const h of data.highlights) { bounds.add(h.start); bounds.add(h.end); }
  const sorted = [...bounds].sort((a,b)=>a-b);
  root.textContent = '';
  for (let i=0;i<sorted.length-1;i++){
    const s=sorted[i], e=sorted[i+1];
    const span=document.createElement('span');
    span.dataset.start=s;
    span.textContent=cps.slice(s,e).join('');
    if (data.highlights.some(h=>h.start<=s && h.end>=e)) span.className='hl';
    root.appendChild(span);
  }
  const toCp=(node,off)=>{
    const el=node.nodeType===3?node.parentElement:node;
    const base=Number(el.dataset.start);
    const pre=(node.nodeType===3?node.data:el.textContent).slice(0,off);
    return base+Array.from(pre).length;
  };
  root.onmouseup=()=>{
    const sel=window.getSelection();
    if(!sel||sel.isCollapsed) return;
    const r=sel.getRangeAt(0);
    setTriggerValue('selection',{start:toCp(r.startContainer,r.startOffset),end:toCp(r.endContainer,r.endOffset),text:sel.toString()});
  };
}
"""
reader = st.components.v2.component(
    "didi_reader",
    html='<div id="didi-reader"></div>',
    css="#didi-reader{white-space:pre-wrap}.hl{background:#ffe08a}",
    js=JS,
    isolate_styles=False,
)
name = st.selectbox("doc", list(TEXTS))
text = TEXTS[name]
hl = st.session_state.get("hl", {}).get(name, [])
res = reader(data={"text": text, "highlights": hl}, key=f"r_{name}", on_selection_change=lambda: None)
sel = res.selection if res else None
if sel:
    py = text[sel["start"]:sel["end"]]
    st.code(json.dumps({"doc": name, "start": sel["start"], "end": sel["end"], "py": py, "browser": sel["text"]}, ensure_ascii=True), language=None)
    st.session_state.setdefault("hl", {})[name] = [{"start": sel["start"], "end": sel["end"]}]
    st.write(f"HIGHLIGHT-COUNT {len(st.session_state['hl'][name])}")
