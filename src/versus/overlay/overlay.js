const el=id=>document.getElementById(id), canvas=el('map'), ctx=canvas.getContext('2d');
const roles={sword:'S',axe:'A',bow:'B',mage:'M',healer:'H'};
function draw(o){ctx.clearRect(0,0,720,720);if(!o)return;
 for(let y=0;y<15;y++)for(let x=0;x<15;x++){let t=o.terrain[y][x];ctx.fillStyle=({12:'#36563e',10:'#9c8452',11:'#666685'})[t]||'#58685a';ctx.fillRect(x*48,y*48,48,48);ctx.strokeStyle='#26342f';ctx.strokeRect(x*48,y*48,48,48);if(t===11){ctx.fillStyle='#f0e3c4';ctx.font='32px serif';ctx.fillText('♜',x*48+9,y*48+34);}}
 for(const u of o.units){if(u.dead)continue;ctx.globalAlpha=u.spent?0.55:1;ctx.fillStyle=u.seat===0?'#337bea':'#de465b';ctx.beginPath();ctx.arc(u.x*48+24,u.y*48+23,17,0,Math.PI*2);ctx.fill();ctx.fillStyle='white';ctx.font='bold 18px system-ui';ctx.textAlign='center';ctx.fillText(roles[u.role]||'?',u.x*48+24,u.y*48+29);ctx.fillStyle='#161b20';ctx.fillRect(u.x*48+5,u.y*48+41,38,5);ctx.fillStyle='#75df9d';ctx.fillRect(u.x*48+5,u.y*48+41,38*u.hp/u.max_hp,5);ctx.globalAlpha=1;ctx.textAlign='left';}}
async function refresh(){try{let response=await fetch('/state',{cache:'no-store'});if(!response.ok)throw Error();let s=await response.json(),g=s.match,o=s.observation;
 el('status').textContent=`${s.status.toUpperCase()} · ${s.completed}/${s.total} games`;
 if(g){el('blue').textContent=`BLUE · ${g.entrants[0]} · ${g.parties[0]}`;el('red').textContent=`RED · ${g.entrants[1]} · ${g.parties[1]}`;el('match').textContent=`Game ${g.id+1} · ${g.map} · ${g.objective} · ${g.opener?'Red':'Blue'} opens`;}
 el('phase').textContent=o?`Round ${o.round} · Action ${o.sequence} · ${o.active_seat?'Red':'Blue'} ${s.status==='thinking'?'thinking':'phase'}`:'';
 draw(o);el('decision').textContent=s.decision?`${s.decision.seat?'Red':'Blue'}: ${s.decision.rationale}`:'—';el('error').textContent=s.error||'';
 el('result').textContent=s.last_result?`Last result: ${s.last_result.outcome===3?'Draw':s.last_result.entrants[s.last_result.outcome-1]+' wins'} · ${s.last_result.victory_reason}`:'';
 el('standings').replaceChildren(...s.standings.map(r=>{let tr=document.createElement('tr');for(let v of [r.id,r.wins,r.draws,r.losses,r.points]){let td=document.createElement('td');td.textContent=v;tr.append(td);}return tr;}));
 }catch{el('status').textContent='Stream disconnected · reconnecting';}finally{setTimeout(refresh,750);}}
refresh();
