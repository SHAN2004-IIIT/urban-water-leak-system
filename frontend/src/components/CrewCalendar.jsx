import React from 'react';

const date = (value) => value ? String(value).slice(0,10) : '';
const clock = (value) => value ? String(value).replace('T',' ').slice(11,16) : '';
export default function CrewCalendar({data,from,to}) {
 const shifts=data?.shifts||[];
 const bookings=data?.bookings||[];
 const crews=[...new Map(shifts.map(x=>[x.crew_id,x])).values()];
 const days=[];
 for(let d=new Date(from+'T12:00:00'); d<=new Date(to+'T12:00:00'); d.setDate(d.getDate()+1)){
  days.push([d.getFullYear(),String(d.getMonth()+1).padStart(2,'0'),String(d.getDate()).padStart(2,'0')].join('-'));
 }
 return <div className="scroll"><table className="calendar"><thead><tr><th>Crew</th>{days.map(day=><th key={day}>{day}</th>)}</tr></thead><tbody>{crews.map(crew=><tr key={crew.crew_id}><th>{crew.crew_name}<br/><small>{crew.crew_id}</small></th>{days.map(day=>{
  const override=shifts.find(s=>s.crew_id===crew.crew_id&&date(s.available_date)===day);
  const dayBookings=bookings.filter(b=>b.crew_id===crew.crew_id&&date(b.scheduled_start)===day);
  const seedOffDay=date(crew.base_available_date)===day && ['OFFDUTY','UNAVAILABLE','LEAVE'].includes(String(crew.roster_status).toUpperCase().replaceAll(' ',''));
  const shiftStatus=override?.day_status||(seedOffDay?'UNAVAILABLE':'AVAILABLE');
  const status=shiftStatus!=='AVAILABLE'?shiftStatus:
      dayBookings.length>=Number(crew.max_jobs_per_day)?'FULL':
      dayBookings.length>0?'PARTIALLY_BOOKED':'AVAILABLE';
  return <td key={day}><div className="calendar-cell"><small>{status}</small>{dayBookings.map(b=><div key={b.assignment_id} className="calendar-job"><strong>#{b.work_order_id}</strong> · {b.zone_id}<br/>{clock(b.scheduled_start)}–{clock(b.scheduled_end)}<br/><small>{b.status}</small></div>)}</div></td>;
 })}</tr>)}</tbody></table></div>;
}
