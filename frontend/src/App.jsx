import SchedulingPage from './pages/SchedulingPage.jsx';
import React,{useEffect,useState} from 'react';
const BASE=import.meta.env.VITE_API_BASE||'';
function useApi(auth){
 return async (path,method='GET',body)=>{
  const response=await fetch(BASE+path,{
   method,headers:{Authorization:'Basic '+auth,'Content-Type':'application/json'},
   ...(body!==undefined?{body:JSON.stringify(body)}:{})
  });
  const raw=await response.text();let data;
  try{data=raw?JSON.parse(raw):null}catch{data=raw}
  if(!response.ok)throw Error((typeof data==='object'&&(data?.detail||data?.message))||`Request failed (${response.status})`);
  return data;
 };
}
function Login({onLogin}){
 const [username,setUsername]=useState('');const [password,setPassword]=useState('');const [error,setError]=useState('');const [busy,setBusy]=useState(false);
 async function submit(e){e.preventDefault();setBusy(true);setError('');try{
  const token=btoa(String.fromCharCode(...new TextEncoder().encode(`${username}:${password}`)));
  const res=await fetch(BASE+'/api/auth/me',{headers:{Authorization:'Basic '+token}});
  if(!res.ok)throw Error('Invalid credentials or backend unavailable');
  onLogin(token,await res.json());
 }catch(e){setError(e.message)}finally{setBusy(false)}}
 return <div className="login"><form onSubmit={submit} className="panel"><h1>Water Leak Operations</h1><p>Local development sign-in</p><label>Username<input value={username} onChange={e=>setUsername(e.target.value)} required autoComplete="username"/></label><label>Password<input value={password} type="password" onChange={e=>setPassword(e.target.value)} required autoComplete="current-password"/></label><button disabled={busy}>Sign in</button>{error&&<p className="error">{error}</p>}</form></div>
}
const badge=(s)=><span className="pill">{String(s??'—')}</span>;
function Table({rows,cols}){return <div className="scroll"><table><thead><tr>{cols.map(c=><th key={c}>{c.replaceAll('_',' ')}</th>)}</tr></thead><tbody>{rows.map((r,i)=><tr key={i}>{cols.map(c=><td key={c}>{typeof r[c]==='object'?JSON.stringify(r[c]):String(r[c]??'—')}</td>)}</tr>)}</tbody></table>{rows.length===0&&<p>No records yet.</p>}</div>}
function App(){
 const [token,setToken]=useState('');const [user,setUser]=useState(null);const api=useApi(token);const [tab,setTab]=useState('Dashboard');const [cases,setCases]=useState([]);const [zones,setZones]=useState([]);const [crews,setCrews]=useState([]);const [orders,setOrders]=useState([]);const [mine,setMine]=useState([]);const [selected,setSelected]=useState(null);const [error,setError]=useState('');const [success,setSuccess]=useState('');const [loading,setLoading]=useState(false);
 const manager=user&&user.role!=='CREW';
 async function refresh(){if(!user)return;setLoading(true);setError('');try{
  if(manager){const [c,z,cr,o]=await Promise.all([api('/api/leak-cases'),api('/api/zones'),api('/api/crews'),api('/api/work-orders')]);setCases(c);setZones(z);setCrews(cr);setOrders(o)}
  else setMine(await api('/api/my/work-orders'));
 }catch(e){setError(e.message)}finally{setLoading(false)}}
 useEffect(()=>{if(user)refresh()},[user]);
 async function act(path,method,body){setError('');setSuccess('');try{const res=await api(path,method,body);setSuccess('Saved successfully');await refresh();return res}catch(e){setError(e.message);return null}}
 const tabs=manager?['Dashboard','Leak Cases','Crews','Work Orders','Scheduling']:['My Work Orders'];
 return !user?<Login onLogin={(t,u)=>{setToken(t);setUser(u);setTab(u.role==='CREW'?'My Work Orders':'Dashboard')}}/>:<div className="app">
 <aside><h2>Water Leak</h2><div className="muted">Operations Console</div><nav>{tabs.map(t=><button className={tab===t?'active':''} key={t} onClick={()=>{setTab(t);setSelected(null)}}>{t}</button>)}</nav></aside>
 <main><header><div><h1>{tab}</h1><span className="muted">{user.username} · {user.role}{user.crew_id?` · ${user.crew_id}`:''}</span></div><div><button className="secondary" onClick={refresh}>{loading?'Loading…':'Refresh'}</button><button className="secondary" onClick={()=>{setToken('');setUser(null)}}>Sign out</button></div></header>
 {error&&<div className="alert error">{error}</div>}{success&&<div className="alert ok">{success}</div>}
 {tab==='Dashboard'&&<><section className="metrics"><div className="panel"><small>Suspected cases</small><strong>{cases.length}</strong></div><div className="panel"><small>High risk</small><strong>{cases.filter(c=>Number(c.risk_score)>=75).length}</strong></div><div className="panel"><small>Crews</small><strong>{crews.length}</strong></div><div className="panel"><small>Open work orders</small><strong>{orders.filter(o=>o.status!=='COMPLETED').length}</strong></div></section><div className="panel"><h3>Priority cases</h3><Table rows={cases.slice(0,10)} cols={['case_id','zone_id','risk_score','risk_band','access_status','case_status']}/></div></>}
 {tab==='Leak Cases'&&<><div className="panel"><h3>Cases ranked by risk</h3><Table rows={cases} cols={['case_id','source_case_id','zone_id','location_id','risk_score','risk_band','access_status','case_status']}/></div><CaseActions api={api} act={act} cases={cases} selected={selected} setSelected={setSelected}/></>}
 {tab==='Crews'&&<div className="panel"><h3>Crew roster</h3><Table rows={crews} cols={['crew_id','crew_name','availability_status','availability_date','shift_start','shift_end','max_jobs_per_day']}/></div>}
 {tab==='Work Orders'&&<><div className="panel"><h3>All work orders</h3><Table rows={orders} cols={['work_order_id','case_id','status','crew_id','scheduled_start','scheduled_end']}/></div><WorkOrderActions act={act} cases={cases} crews={crews} orders={orders}/></>}
 {tab==='Scheduling'&&manager&&<SchedulingPage api={api} cases={cases} crews={crews} orders={orders} onRefresh={refresh}/>}
 {tab==='My Work Orders'&&<><div className="panel"><h3>Assigned to your crew</h3><Table rows={mine} cols={['work_order_id','case_id','zone_id','location_id','status','scheduled_start','scheduled_end']}/></div><OutcomeForm orders={mine} act={act}/></>}
 </main></div>;
}
function CaseActions({api,act,cases,selected,setSelected}){const [status,setStatus]=useState('OPEN');const [reason,setReason]=useState('Access verified by supervisor');
 async function details(id){if(!id)return;try{setSelected(await api(`/api/leak-cases/${id}/score`))}catch(e){setSelected({error:e.message})}}
 return <div className="panel"><h3>Case details & access</h3><label>Select case<select onChange={e=>details(e.target.value)}><option value="">Choose case</option>{cases.map(c=><option key={c.case_id} value={c.case_id}>{c.case_id} — {c.zone_id} ({c.risk_score})</option>)}</select></label>{selected&&<pre>{JSON.stringify(selected,null,2)}</pre>}<label>Access status<select value={status} onChange={e=>setStatus(e.target.value)}><option>OPEN</option><option>BLOCKED</option><option>UNKNOWN</option></select></label><label>Reason<input value={reason} onChange={e=>setReason(e.target.value)}/></label><button disabled={!selected?.case_id} onClick={()=>act(`/api/leak-cases/${selected.case_id}/access`,'PATCH',{accessStatus:status,reason})}>Update access</button></div>}
function WorkOrderActions({act,cases,crews,orders}){
 const [caseId,setCaseId]=useState('');const [type,setType]=useState('INSPECTION');const [duration,setDuration]=useState(120);const [orderId,setOrderId]=useState('');const [crewId,setCrewId]=useState('');const [start,setStart]=useState('');const [end,setEnd]=useState('');const [reason,setReason]=useState('Scheduled after access verification');
 const request={crewId,scheduledStart:start?start+':00':null,scheduledEnd:end?end+':00':null,reason};
 return <div className="two"><div className="panel"><h3>Create work order</h3><label>Case<select value={caseId} onChange={e=>setCaseId(e.target.value)}><option value="">Choose</option>{cases.map(c=><option key={c.case_id} value={c.case_id}>{c.case_id} — {c.zone_id}</option>)}</select></label><label>Type<select value={type} onChange={e=>setType(e.target.value)}><option>INSPECTION</option><option>REPAIR</option></select></label><label>Duration in minutes<input type="number" min="1" value={duration} onChange={e=>setDuration(+e.target.value)}/></label><button disabled={!caseId} onClick={()=>act('/api/work-orders','POST',{caseId:+caseId,workType:type,estimatedDurationMinutes:duration,reason:'Supervisor created investigation'})}>Create</button></div>
 <div className="panel"><h3>Assign / reassign crew</h3><label>Work order<select value={orderId} onChange={e=>setOrderId(e.target.value)}><option value="">Choose</option>{orders.map(o=><option key={o.work_order_id} value={o.work_order_id}>{o.work_order_id} — {o.status}</option>)}</select></label><label>Crew<select value={crewId} onChange={e=>setCrewId(e.target.value)}><option value="">Choose</option>{crews.map(c=><option key={c.crew_id} value={c.crew_id}>{c.crew_id} — {c.crew_name}</option>)}</select></label><label>Start<input type="datetime-local" value={start} onChange={e=>setStart(e.target.value)}/></label><label>End<input type="datetime-local" value={end} onChange={e=>setEnd(e.target.value)}/></label><label>Reason<input value={reason} onChange={e=>setReason(e.target.value)}/></label><div className="actions"><button disabled={!orderId||!crewId||!start||!end} onClick={()=>act(`/api/work-orders/${orderId}/assign`,'POST',request)}>Assign</button><button className="secondary" disabled={!orderId||!crewId||!start||!end} onClick={()=>act(`/api/work-orders/${orderId}/reassign`,'POST',request)}>Reassign</button></div></div></div>
}
function localDateTime(){const d=new Date();const z=n=>String(n).padStart(2,'0');return `${d.getFullYear()}-${z(d.getMonth()+1)}-${z(d.getDate())}T${z(d.getHours())}:${z(d.getMinutes())}:${z(d.getSeconds())}`}
function OutcomeForm({orders,act}){const [id,setId]=useState('');const [outcome,setOutcome]=useState('CONFIRMED_LEAK');const [notes,setNotes]=useState('');const [loss,setLoss]=useState('');return <div className="panel"><h3>Record field inspection</h3><label>Assigned work order<select value={id} onChange={e=>setId(e.target.value)}><option value="">Choose</option>{orders.filter(o=>o.status==='ASSIGNED').map(o=><option key={o.work_order_id} value={o.work_order_id}>{o.work_order_id}</option>)}</select></label><label>Outcome<select value={outcome} onChange={e=>setOutcome(e.target.value)}><option>CONFIRMED_LEAK</option><option>NO_LEAK</option><option>INCONCLUSIVE</option></select></label><label>Estimated loss (litres, optional)<input type="number" min="0" value={loss} onChange={e=>setLoss(e.target.value)}/></label><label>Inspection notes<textarea rows="3" value={notes} onChange={e=>setNotes(e.target.value)}/></label><button disabled={!id} onClick={()=>act(`/api/work-orders/${id}/outcome`,'POST',{outcomeType:outcome,leakType:null,estimatedWaterLossLitres:loss===''?null:+loss,repairNotes:notes,inspectedAt:localDateTime()})}>Save outcome</button></div>}
export default App;
