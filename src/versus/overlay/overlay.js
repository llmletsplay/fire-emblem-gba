const el=id=>document.getElementById(id);
async function refresh(){try{let response=await fetch('/state',{cache:'no-store'});if(!response.ok)throw Error();let s=await response.json(),g=s.match,o=s.observation;
 el('status').textContent=`${s.status.toUpperCase()} · ${s.completed}/${s.total} games`;
 if(g){el('blue').textContent=`BLUE · ${g.entrants[0]} · ${g.parties[0]}`;el('red').textContent=`RED · ${g.entrants[1]} · ${g.parties[1]}`;el('match').textContent=`Game ${g.id+1} · ${g.map} · ${g.objective} · ${g.opener?'Red':'Blue'} opens`;}
 el('phase').textContent=o?`Round ${o.round} · Action ${o.sequence} · ${o.active_seat?'Red':'Blue'} ${s.status==='thinking'?'thinking':'phase'}`:'';
 el('decision').textContent=s.decision?`${s.decision.seat?'Red':'Blue'}: ${s.decision.rationale}`:'—';el('error').textContent=s.error||'';
 el('result').textContent=s.last_result?`Last result: ${s.last_result.outcome===3?'Draw':s.last_result.entrants[s.last_result.outcome-1]+' wins'} · ${s.last_result.victory_reason}`:'';
 el('standings').replaceChildren(...s.standings.map(r=>{let tr=document.createElement('tr');for(let v of [r.id,r.wins,r.draws,r.losses,r.points]){let td=document.createElement('td');td.textContent=v;tr.append(td);}return tr;}));
 }catch{el('status').textContent='Stream disconnected · reconnecting';}finally{setTimeout(refresh,750);}}
refresh();

let loading=false;
function video(){if(loading)return;loading=true;const image=new Image();image.onload=()=>{el('video').src=image.src;el('video-status').textContent='';loading=false;};image.onerror=()=>{el('video-status').textContent='Waiting for native emulator video';loading=false;};image.src='/video/0.png?t='+Date.now();}
setInterval(video,100);video();

function resize(){el('broadcast').style.transform=`scale(${Math.min(innerWidth/1920,innerHeight/1080)})`;}addEventListener('resize',resize);resize();
