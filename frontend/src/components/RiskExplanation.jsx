import React from 'react';
export default function RiskExplanation({selectedCase}){
 if(!selectedCase)return <p>Select a leak case to view its scoring evidence.</p>;
 let parts=selectedCase.score_components;
 if(typeof parts==='string'){try{parts=JSON.parse(parts)}catch{parts={raw:parts}}}
 return <div className="panel"><h3>Leak risk: {selectedCase.risk_score ?? 'Not scored'}/100</h3>
 <p>Zone {selectedCase.zone_id} · Case #{selectedCase.case_id} · Access: {selectedCase.access_status}</p>
 <h4>Evidence breakdown</h4><pre>{JSON.stringify(parts||{},null,2)}</pre>
 <small>Risk measures evidence. Access and crew capacity determine whether dispatch is possible.</small></div>;
}
