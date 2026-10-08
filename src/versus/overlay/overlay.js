const el=id=>document.getElementById(id);
function render(s){const g=s.match,o=s.observation;
 el('broadcast').dataset.status=s.status;
 el('status').textContent=`${s.status.toUpperCase()} · ${s.completed}/${s.total} games`;
 for(let seat=0;seat<2;seat++)el(seat?'red':'blue').dataset.active=String(o?.active_seat===seat);
 if(g){el('blue').textContent=`BLUE · ${g.entrants[0]} · ${g.parties[0]}`;el('red').textContent=`RED · ${g.entrants[1]} · ${g.parties[1]}`;el('blue').title=el('blue').textContent;el('red').title=el('red').textContent;el('objective').textContent={elimination:'ELIMINATE THE ENEMY ARMY',seizure:'SEIZE THE ENEMY CASTLE',either:'ELIMINATION OR CASTLE SEIZURE'}[g.objective]||g.objective;el('match').textContent=`Game ${g.id+1} · ${g.map} · ${g.objective} · ${g.opener?'Red':'Blue'} opens`;}
 el('phase').textContent=o?`Round ${o.round} · Action ${o.sequence} · ${o.active_seat?'Red':'Blue'} ${s.status==='human-turn'?'human turn':s.status==='thinking'?'thinking':'phase'}`:'';
 for(let seat=0;seat<2;seat++){const name=seat?'red':'blue',d=s.decisions?.[seat];el(name+'-decision').title=d?.rationale||'';el(name+'-decision').textContent=d?.rationale||`Waiting for ${seat?'Red':'Blue'}`;el(name+'-action').textContent=d?`ROUND ${d.round} · ACTION ${d.sequence+1}`:'';el(name+'-thinking').textContent=s.status==='thinking'&&s.thinking_seat===seat?'THINKING':s.status==='human-turn'&&s.thinking_seat===seat?'YOUR TURN':'';}el('error').textContent=s.error||'';
 el('result').textContent=s.last_result?`Last result: ${s.last_result.outcome===3?'Draw':s.last_result.entrants[s.last_result.outcome-1]+' wins'} · ${s.last_result.victory_reason}`:'';
 const rows=s.standings||[],page=Math.floor(Date.now()/10000)%Math.max(1,Math.ceil(rows.length/4));
 el('standings').replaceChildren(...rows.slice(page*4,page*4+4).map(r=>{let tr=document.createElement('tr');for(let v of [r.id,r.wins,r.draws,r.losses,r.points]){let td=document.createElement('td');td.textContent=v;tr.append(td);}return tr;}));
}
async function refresh(){try{let response=await fetch('/state',{cache:'no-store'});if(!response.ok)throw Error();render(await response.json());}catch{el('broadcast').dataset.status='disconnected';el('status').textContent='Stream disconnected · reconnecting';}finally{setTimeout(refresh,750);}}
const overlayOnly=new URLSearchParams(location.search).has('overlay');
el('broadcast').dataset.overlay=String(overlayOnly);
refresh();

let loading=false;
function video(){if(loading)return;loading=true;const image=new Image();image.onload=()=>{el('video').src=image.src;el('video-status').textContent='';loading=false;};image.onerror=()=>{el('video-status').textContent='Waiting for native emulator video';loading=false;};image.src='/video/0.png?t='+Date.now();}
if(!overlayOnly){setInterval(video,100);video();}

function resize(){const scale=Math.min(innerWidth/1920,innerHeight/1080);el('broadcast').style.transform=`translate(${(innerWidth-1920*scale)/2}px,${(innerHeight-1080*scale)/2}px) scale(${scale})`;}addEventListener('resize',resize);resize();
