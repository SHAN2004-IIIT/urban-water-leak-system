import React,{useEffect,useState} from 'react';
import CrewCalendar from '../components/CrewCalendar.jsx';
import AssignmentModal from '../components/AssignmentModal.jsx';
import RiskExplanation from '../components/RiskExplanation.jsx';
const day=()=>{const d=new Date();return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}-${String(d.getDate()).padStart(2,'0')}`};
export default function SchedulingPage({api,cases,crews,orders,onRefresh}){
 const [from,setFrom]=useState(day());const [to,setTo]=useState(day());const [calendar,setCalendar]=useState(null);
 const [caseId,setCaseId]=useState('');const [access,setAccess]=useState('BLOCKED');const [reason,setReason]=useState('Road access restricted');
 const [crewId,setCrewId]=useState('');const [availabilityDate,setDate]=useState(day());const [availability,setAvailability]=useState('LEAVE');
 const [start,setStart]=useState('09:00');const [end,setEnd]=useState('17:00');
 const [orderId,setOrderId]=useState('');const [status,setStatus]=useState('DEFERRED');const [statusReason,setStatusReason]=useState('Awaiting access clearance');
 const [history,setHistory]=useState([]);const [error,setError]=useState('');const [message,setMessage]=useState('');
 async function refresh(){try{setError('');setCalendar(await api(`/api/scheduling/calendar?from=${from}&to=${to}`));await onRefresh?.()}catch(e){setError(e.message)}}
 useEffect(()=>{refresh()},[from,to]);
 async function submit(path,payload){try{setError('');setMessage('');await api(path,'POST',payload);setMessage('Updated successfully');await refresh()}catch(e){setError(e.message)}}
 const selected=cases.find(x=>String(x.case_id)===caseId);
 return <>
 {error&&<div className="alert error">{error}</div>}{message&&<div className="alert ok">{message}</div>}
 <div className="panel"><h3>Crew capacity calendar</h3><div className="two"><label>From<input type="date" value={from} onChange={e=>setFrom(e.target.value)}/></label><label>To<input type="date" value={to} onChange={e=>setTo(e.target.value)}/></label></div>
 {calendar&&<CrewCalendar data={calendar} from={from} to={to}/>}</div>
 <div className="two"><div className="panel"><h3>Availability override</h3><label>Crew<select value={crewId} onChange={e=>setCrewId(e.target.value)}><option value="">Select</option>{crews.map(x=><option value={x.crew_id} key={x.crew_id}>{x.crew_name}</option>)}</select></label><label>Date<input type="date" value={availabilityDate} onChange={e=>setDate(e.target.value)}/></label><label>Status<select value={availability} onChange={e=>setAvailability(e.target.value)}>{['AVAILABLE','LEAVE','UNAVAILABLE'].map(x=><option key={x}>{x}</option>)}</select></label><div className="two"><label>Start<input type="time" value={start} onChange={e=>setStart(e.target.value)}/></label><label>End<input type="time" value={end} onChange={e=>setEnd(e.target.value)}/></label></div><button disabled={!crewId} onClick={()=>submit('/api/scheduling/availability',{crewId,date:availabilityDate,shiftStart:start,shiftEnd:end,status:availability,notes:'Supervisor calendar update'})}>Save availability</button></div>
 <div className="panel"><h3>Access restriction</h3><label>Leak case<select value={caseId} onChange={e=>setCaseId(e.target.value)}><option value="">Select</option>{cases.map(x=><option key={x.case_id} value={x.case_id}>#{x.case_id} · {x.zone_id} · risk {x.risk_score}</option>)}</select></label><label>Access<select value={access} onChange={e=>setAccess(e.target.value)}>{['BLOCKED','OPEN','UNKNOWN'].map(x=><option key={x}>{x}</option>)}</select></label><label>Reason<input value={reason} onChange={e=>setReason(e.target.value)}/></label><button disabled={!caseId||!reason.trim()} onClick={()=>submit(`/api/scheduling/leak-cases/${caseId}/access`,{accessStatus:access,reason})}>Save access decision</button></div></div>
 {selected&&<RiskExplanation selectedCase={selected}/>}
 <AssignmentModal orders={orders} crews={crews} api={api} onSaved={refresh}/>
 <div className="two"><div className="panel"><h3>Work-order lifecycle</h3><label>Work order<select value={orderId} onChange={e=>{setOrderId(e.target.value);setHistory([])}}><option value="">Select</option>{orders.map(o=><option key={o.work_order_id} value={o.work_order_id}>#{o.work_order_id} · {o.status}</option>)}</select></label><label>Change status<select value={status} onChange={e=>setStatus(e.target.value)}>{['IN_PROGRESS','DEFERRED','CREATED','CLOSED'].map(x=><option key={x}>{x}</option>)}</select></label><label>Reason<input value={statusReason} onChange={e=>setStatusReason(e.target.value)}/></label><button disabled={!orderId||!statusReason.trim()} onClick={()=>submit(`/api/scheduling/work-orders/${orderId}/status`,{status,reason:statusReason})}>Update status</button></div>
 <div className="panel"><h3>Decision history</h3><button className="secondary" disabled={!orderId} onClick={async()=>{try{setHistory(await api(`/api/scheduling/work-orders/${orderId}/history`))}catch(e){setError(e.message)}}}>Load history</button><div className="scroll"><table><thead><tr><th>Event</th><th>Previous</th><th>New</th><th>Actor</th><th>Reason</th></tr></thead><tbody>{history.map(h=><tr key={h.event_id}><td>{h.event_type}</td><td>{h.from_status}</td><td>{h.to_status}</td><td>{h.actor}</td><td>{h.reason}</td></tr>)}</tbody></table></div></div></div>
 </>;
}
