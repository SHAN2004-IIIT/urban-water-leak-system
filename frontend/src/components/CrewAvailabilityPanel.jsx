import React, {useState} from 'react';

export default function CrewAvailabilityPanel({crews,date,setDate,api,onSaved}) {
 const [crewId,setCrewId]=useState('');
 const [status,setStatus]=useState('AVAILABLE');
 const [start,setStart]=useState('08:00');
 const [end,setEnd]=useState('16:00');
 const [notes,setNotes]=useState('Supervisor availability update');
 const [error,setError]=useState('');
 const [success,setSuccess]=useState('');
 const selected=crews.find(c=>c.crew_id===crewId);
 function clock(s){return String(s??'').slice(0,5)}
 function pick(id){
   setCrewId(id);const crew=crews.find(c=>c.crew_id===id);
   if(crew){setStatus(crew.shift_status==='AVAILABLE'?'AVAILABLE':crew.shift_status);
     setStart(clock(crew.shift_start));setEnd(clock(crew.shift_end));}
 }
 async function save(e){
   e.preventDefault();setError('');setSuccess('');
   if(!crewId)return setError('Select a crew');
   try{
     await api('/api/scheduling/availability','POST',{
       crewId,date,shiftStart:start,shiftEnd:end,status,notes
     });
     setSuccess('Availability updated for '+crewId+' on '+date);
     await onSaved();
   }catch(e){setError(e.message)}
 }
 return <>
  <div className="panel"><h3>Availability for selected date</h3>
   <label>Date <input type="date" value={date} onChange={e=>setDate(e.target.value)}/></label>
   <div className="scroll"><table><thead><tr>
    {['Crew ID','Crew name','Status','Jobs booked','Remaining slots','Shift','Max/day'].map(v=><th key={v}>{v}</th>)}
   </tr></thead><tbody>{crews.map(c=><tr key={c.crew_id}>
    <td>{c.crew_id}</td><td>{c.crew_name}</td><td>{c.availability_status}</td>
    <td>{c.assigned_jobs}</td><td>{c.remaining_capacity}</td>
    <td>{clock(c.shift_start)}–{clock(c.shift_end)}</td><td>{c.max_jobs_per_day}</td>
   </tr>)}</tbody></table></div>
   <p className="muted">FULL = daily booking capacity reached. PARTIALLY_BOOKED = has bookings but some daily capacity remains; overlapping times are always prohibited. This is a selected-date status, not a permanent crew property.</p>
  </div>
  <form className="panel" onSubmit={save}><h3>Change dated crew availability</h3>
   {error&&<p className="alert error">{error}</p>}{success&&<p className="alert ok">{success}</p>}
   <label>Crew<select value={crewId} onChange={e=>pick(e.target.value)} required>
     <option value="">Choose crew</option>{crews.map(c=><option key={c.crew_id} value={c.crew_id}>{c.crew_id} — {c.crew_name}</option>)}
   </select></label>
   <label>Status<select value={status} onChange={e=>setStatus(e.target.value)}>
    <option value="AVAILABLE">AVAILABLE</option><option value="LEAVE">LEAVE</option>
    <option value="UNAVAILABLE">UNAVAILABLE</option>
   </select></label>
   <div className="two"><label>Shift start<input type="time" value={start} onChange={e=>setStart(e.target.value)} required/></label>
   <label>Shift end<input type="time" value={end} onChange={e=>setEnd(e.target.value)} required/></label></div>
   <label>Reason<input value={notes} onChange={e=>setNotes(e.target.value)} required/></label>
   {selected?.assigned_jobs>0&&status!=='AVAILABLE'&&<p className="muted">This crew has active assignments for this date. Reassign or defer those work orders before marking leave/unavailable.</p>}
   <button disabled={!crewId}>Save for {date}</button>
  </form>
 </>;
}
