from __future__ import annotations

import html
import json


def render_exam_html(
    questions: list[dict], images: dict[str, dict[str, str]], duration_minutes: int, source_name: str,
) -> str:
    data = json.dumps(
        {"questions": questions, "images": images, "duration": duration_minutes * 60},
        ensure_ascii=False,
    ).replace("</", "<\\/")
    title = html.escape(source_name or "SAT Verbal Practice")
    template = r'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>__TITLE__</title><style>
*{box-sizing:border-box} body{margin:0;font-family:Arial,sans-serif;background:#f4f6f8;color:#172033} header{height:64px;background:#123c69;color:white;display:flex;align-items:center;justify-content:space-between;padding:0 24px} main{display:grid;grid-template-columns:230px 1fr;min-height:calc(100vh - 64px)} aside{padding:18px;background:white;border-right:1px solid #d8dde6} #tracker{display:flex;flex-wrap:wrap;gap:8px} #tracker button{width:38px;height:38px;border:1px solid #b9c4d1;background:white;border-radius:5px} #tracker button.done{background:#d9f1e2;border-color:#4d9a68} #tracker button.flagged{outline:3px solid #f4be45} #content{padding:28px;max-width:1100px;margin:auto;width:100%} #columns{display:grid;grid-template-columns:1fr 1fr;gap:28px} .card{background:white;padding:24px;border-radius:8px;box-shadow:0 1px 3px #ccd3dd} #passage{white-space:pre-wrap;line-height:1.65;max-height:65vh;overflow:auto} .choice{display:block;border:1px solid #cbd5e1;padding:14px;margin:10px 0;border-radius:6px;cursor:pointer} .choice.selected{border:2px solid #1664b4;background:#eef6ff} .choice.correct{border-color:#23834b;background:#dcf4e4} .choice.wrong{border-color:#be3434;background:#fde3e3} button{cursor:pointer} .actions{display:flex;gap:10px;margin-top:22px} .primary{background:#1265b0;color:white;border:0;padding:11px 16px;border-radius:5px} #results{margin-top:20px;padding:16px;background:white;border-radius:8px} .highlight-active{background:#f4be45;color:#172033} @media(max-width:780px){main,#columns{display:block}aside{border-bottom:1px solid #d8dde6}#content{padding:14px}}
</style></head><body><header><strong>Practice Test</strong><span id="timer"></span></header><main><aside><button class="primary" onclick="toggleFlag()">☆ Mark for review</button><p id="progress"></p><div id="tracker"></div><hr><button onclick="submitExam()">Submit test</button></aside><section id="content"><div id="columns"><article class="card"><h2>Passage</h2><button id="highlightToggle" onclick="toggleHighlight()">Highlight off</button><p id="highlightHelp">Turn on, then select text in the passage.</p><div id="passage" contenteditable="true"></div></article><article class="card"><p id="number"></p><h2 id="question"></h2><img id="image" style="max-width:100%;display:none;margin:14px 0"><div id="choices"></div><div class="actions"><button onclick="previous()">Previous</button><button class="primary" onclick="next()">Next</button></div></article></div><div id="results" hidden></div></section></main><script>
const exam=__EXAM_DATA__; let current=0,answers={},flags={},passageMarkup={},submitted=false,highlightMode=false; const qs=exam.questions;
function escapeHtml(value) { const element=document.createElement('div'); element.textContent=value||''; return element.innerHTML; }
function formatText(value) { return escapeHtml(value).replace(/&lt;(\/?)(u|b|i)&gt;/gi, '<$1$2>'); }
function savePassage() { passageMarkup[current]=document.querySelector('#passage').innerHTML; }
function navigate(index) { savePassage(); current=index; render(); }
function render() { const question=qs[current]; document.querySelector('#number').textContent=`Question ${current+1} of ${qs.length}`; document.querySelector('#passage').innerHTML=passageMarkup[current]||formatText(question.passage||'No passage'); document.querySelector('#question').innerHTML=formatText(question.question); const image=document.querySelector('#image'), item=exam.images[question.image_id]; if (item) { image.src='data:'+item.mime+';base64,'+item.data; image.style.display='block'; } else image.style.display='none'; document.querySelector('#choices').innerHTML=Object.entries(question.choices).map(([key,value]) => `<label class="choice ${answers[current]===key?'selected':''}" data-key="${key}"><input type="radio" name="answer" ${answers[current]===key?'checked':''} onchange="answer('${key}')"> <b>${key}.</b> ${formatText(value)}</label>`).join(''); if (submitted) markResults(); renderTracker(); document.querySelector('#progress').textContent=`Completed: ${Object.keys(answers).length} / ${qs.length}`; }
function answer(key) { if (!submitted) { answers[current]=key; render(); } }
function next() { if (current<qs.length-1) navigate(current+1); }
function previous() { if (current>0) navigate(current-1); }
function toggleFlag() { flags[current]=!flags[current]; renderTracker(); }
function renderTracker() { document.querySelector('#tracker').innerHTML=qs.map((_,index) => `<button class="${answers[index]?'done':''} ${flags[index]?'flagged':''}" onclick="navigate(${index})">${index+1}</button>`).join(''); }
function toggleHighlight() { highlightMode=!highlightMode; const button=document.querySelector('#highlightToggle'); button.textContent=highlightMode?'Highlight on':'Highlight off'; button.classList.toggle('highlight-active',highlightMode); document.querySelector('#highlightHelp').textContent=highlightMode?'Select text in the passage to highlight it.':'Turn on to select and highlight text.'; }
document.querySelector('#passage').addEventListener('mouseup', () => { const selection=window.getSelection(), passage=document.querySelector('#passage'); if (highlightMode && selection && selection.toString().trim() && passage.contains(selection.anchorNode)) { document.execCommand('hiliteColor',false,'#fff19b'); setTimeout(savePassage,0); } });
function markResults() { document.querySelectorAll('.choice').forEach((element) => { const key=element.dataset.key, question=qs[current]; element.classList.toggle('correct',question.answer===key); element.classList.toggle('wrong',answers[current]===key&&question.answer&&question.answer!==key); }); }
function submitExam() { submitted=true; const keyed=qs.filter((question) => question.answer); const correct=keyed.filter((question,index) => answers[index]===question.answer).length; const wrong=keyed.filter((question,index) => answers[index]&&answers[index]!==question.answer).map((_,index) => index+1); const result=document.querySelector('#results'); result.hidden=false; result.innerHTML=keyed.length?`<b>Score: ${correct} / ${keyed.length}</b><br>Incorrect answered questions: ${wrong.length?wrong.join(', '):'None'}`:`<b>Completed ${Object.keys(answers).length} / ${qs.length} questions.</b><br>This exam has no answer key, so it cannot be scored.`; render(); }
let remaining=exam.duration; function tick() { const minutes=Math.floor(remaining/60), seconds=remaining%60; document.querySelector('#timer').textContent=`Time: ${minutes}:${String(seconds).padStart(2,'0')}`; if (remaining>0) remaining--; else submitExam(); } tick(); setInterval(tick,1000); render();
</script></body></html>'''
    return template.replace("__TITLE__", title).replace("__EXAM_DATA__", data).replace(' contenteditable="true"', "")
