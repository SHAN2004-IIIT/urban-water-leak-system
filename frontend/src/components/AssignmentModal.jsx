import React,{useState} from 'react';
export default function AssignmentModal({orders,crews,api,onSaved}) {
 const [id,setId]=useState('');const [crewId,setCrew]=useState('');
 const [start,setStart]=useState('');const [end,setEnd]=useState('');
 const [reason,setReason]=useState('Access checked; crew available');const [mode,setMode]=useState('assign');
 const [error,setError]=useState('');
 async function save(e){e.preventDefault();setError('');try{
  await api(`/api/scheduling/work-orders/${id}/${mode}`,'POST',{
   crewId,scheduledStart:start+':00',scheduledEnd:end+':00',reason
  });onSaved?.();
 }catch(err){setError(err.message)}}
 return <form className="panel" onSubmit={save}><h3>Assign or reassign crew</h3><div className="two">
 <label>Work order<select required value={id} onChange={e=>setId(e.target.value)}><option value="">Choose</option>{orders.filter(o=>['CREATED','DEFERRED','ASSIGNED'].includes(o.status)).map(o=><option key={o.work_order_id} value={o.work_order_id}>#{o.work_order_id} · {o.status}</option>)}</select></label>
 <label>Crew<select required value={crewId} onChange={e=>setCrew(e.target.value)}><option value="">Choose</option>{crews.map(c=><option key={c.crew_id} value={c.crew_id}>{c.crew_id} · {c.crew_name}</option>)}</select></label>
 <label>Start<input required type="datetime-local" value={start} onChange={e=>setStart(e.target.value)}/></label>
 <label>End<input required type="datetime-local" value={end} onChange={e=>setEnd(e.target.value)}/></label>
 <label>Action<select value={mode} onChange={e=>setMode(e.target.value)}><option value="assign">Assign</option><option value="reassign">Reassign</option></select></label>
 <label>Reason<input required value={reason} onChange={e=>setReason(e.target.value)}/></label>
 </div><button>Save assignment</button>{error&&<p className="error">{error}</p>}</form>;
}
