package com.waterleak;

import java.time.LocalDateTime;
import java.util.Map;
import java.util.Set;
import org.springframework.http.HttpStatus;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.server.ResponseStatusException;

@Service
public class WorkOrderService {
 private final JdbcTemplate db;
 public WorkOrderService(JdbcTemplate db){this.db=db;}
 public record CreateWorkOrder(Long caseId,String workType,Integer estimatedDurationMinutes,String reason){}
 public record AssignCrew(String crewId,LocalDateTime scheduledStart,LocalDateTime scheduledEnd,String reason){}
 public record RecordOutcome(String outcomeType,String leakType,Double estimatedWaterLossLitres,String repairNotes,LocalDateTime inspectedAt){}
 public record AccessUpdate(String accessStatus,String reason){}
 private ResponseStatusException bad(String message){return new ResponseStatusException(HttpStatus.BAD_REQUEST,message);}
 private boolean exists(String sql,Object... args){return !db.queryForList(sql,args).isEmpty();}
 @Transactional
 public long create(CreateWorkOrder r){
  if(r==null||r.caseId()==null||r.estimatedDurationMinutes()==null||r.estimatedDurationMinutes()<=0)throw bad("caseId and positive estimatedDurationMinutes required");
  if(!exists("SELECT 1 FROM leak_cases WHERE case_id=?",r.caseId()))throw new ResponseStatusException(HttpStatus.NOT_FOUND,"case not found");
  if(!(r.workType()!=null&&Set.of("INSPECTION","REPAIR").contains(r.workType())))throw bad("workType must be INSPECTION or REPAIR");
  return db.queryForObject("""
    INSERT INTO work_orders(case_id,work_type,estimated_duration_minutes,scheduling_reason)
    VALUES (?,?,?,?) RETURNING work_order_id
  """,Long.class,r.caseId(),r.workType(),r.estimatedDurationMinutes(),r.reason());
 }
 @Transactional
 public Map<String,Object> updateAccess(long id,AccessUpdate r){
  if(r==null||!(r.accessStatus()!=null&&Set.of("OPEN","BLOCKED","UNKNOWN").contains(r.accessStatus())))throw bad("accessStatus must be OPEN, BLOCKED or UNKNOWN");
  int n=db.update("UPDATE leak_cases SET access_status=?,access_reason=?,updated_at=now() WHERE case_id=?",r.accessStatus(),r.reason(),id);
  if(n==0)throw new ResponseStatusException(HttpStatus.NOT_FOUND,"case not found");
  return Map.of("case_id",id,"access_status",r.accessStatus());
 }
 @Transactional
 public Map<String,Object> assign(long workOrderId, AssignCrew r){
  if(r==null||r.crewId()==null||r.scheduledStart()==null||r.scheduledEnd()==null||!r.scheduledEnd().isAfter(r.scheduledStart()))throw bad("crewId and valid scheduledStart/scheduledEnd required");
  if(r.reason()==null||r.reason().isBlank())throw bad("Assignment reason required");
  // Serialize competing crew assignments to protect the overlap check.
  if(!exists("SELECT 1 FROM crews WHERE crew_id=? FOR UPDATE",r.crewId()))throw new ResponseStatusException(HttpStatus.NOT_FOUND,"crew not found");
  var crew=db.queryForMap("SELECT availability_status,availability_date,shift_start,shift_end,max_jobs_per_day FROM crews WHERE crew_id=?",r.crewId());
  if(!"Available".equalsIgnoreCase(String.valueOf(crew.get("availability_status"))))throw new ResponseStatusException(HttpStatus.CONFLICT,"crew unavailable");
  if(!r.scheduledStart().toLocalDate().equals(r.scheduledEnd().toLocalDate()))throw bad("This starter supports one-day shifts only");
  if(!r.scheduledStart().toLocalDate().equals(crew.get("availability_date")))throw new ResponseStatusException(HttpStatus.CONFLICT,"crew availability date mismatch; update roster first");
  if(r.scheduledStart().toLocalTime().isBefore(((java.sql.Time)crew.get("shift_start")).toLocalTime())||r.scheduledEnd().toLocalTime().isAfter(((java.sql.Time)crew.get("shift_end")).toLocalTime()))throw new ResponseStatusException(HttpStatus.CONFLICT,"Outside crew shift");
  var wo=db.queryForList("""
     SELECT w.status,l.access_status FROM work_orders w JOIN leak_cases l ON l.case_id=w.case_id
     WHERE w.work_order_id=? FOR UPDATE OF w,l
  """,workOrderId);
  if(wo.isEmpty())throw new ResponseStatusException(HttpStatus.NOT_FOUND,"work order not found");
  if(!"OPEN".equals(wo.get(0).get("access_status")))throw new ResponseStatusException(HttpStatus.CONFLICT,"Verify that leak location is OPEN before dispatch");
  if(!Set.of("CREATED","ASSIGNED").contains(wo.get(0).get("status")))throw new ResponseStatusException(HttpStatus.CONFLICT,"Work order not assignable");
  if(exists("""
    SELECT 1 FROM crew_assignments WHERE crew_id=? AND assignment_status='ACTIVE'
    AND scheduled_start<? AND scheduled_end>? LIMIT 1
  """,r.crewId(),r.scheduledEnd(),r.scheduledStart()))throw new ResponseStatusException(HttpStatus.CONFLICT,"Crew already booked in this time range");
  if(exists("SELECT 1 FROM crew_assignments WHERE work_order_id=? AND assignment_status='ACTIVE'",workOrderId))throw new ResponseStatusException(HttpStatus.CONFLICT,"Work order already assigned; reassignment API comes in next increment");
  int assigned=db.queryForObject("""
    SELECT count(*) FROM crew_assignments WHERE crew_id=? AND assignment_status='ACTIVE'
    AND scheduled_start::date=?
  """,Integer.class,r.crewId(),r.scheduledStart().toLocalDate());
  if(assigned>=((Number)crew.get("max_jobs_per_day")).intValue())throw new ResponseStatusException(HttpStatus.CONFLICT,"Crew daily capacity exceeded");
  long aid=db.queryForObject("""
    INSERT INTO crew_assignments(work_order_id,crew_id,scheduled_start,scheduled_end,reason)
    VALUES (?,?,?,?,?) RETURNING assignment_id
  """,Long.class,workOrderId,r.crewId(),r.scheduledStart(),r.scheduledEnd(),r.reason());
  db.update("UPDATE work_orders SET status='ASSIGNED',updated_at=now() WHERE work_order_id=?",workOrderId);
  return Map.of("assignment_id",aid,"work_order_id",workOrderId,"crew_id",r.crewId(),"status","ASSIGNED");
 }
 @Transactional
 public Map<String,Object> reassign(long workOrderId, AssignCrew r){
  // All changes are in a single transaction. On validation failure the old booking is restored.
  var current=db.queryForList("SELECT assignment_id FROM crew_assignments WHERE work_order_id=? AND assignment_status='ACTIVE' FOR UPDATE",workOrderId);
  if(current.isEmpty())throw new ResponseStatusException(HttpStatus.CONFLICT,"No active assignment to replace");
  long previous=((Number)current.get(0).get("assignment_id")).longValue();
  db.update("UPDATE crew_assignments SET assignment_status='REASSIGNED' WHERE assignment_id=?",previous);
  Map<String,Object> result=assign(workOrderId,r);
  db.update("INSERT INTO application_events(event_type,entity_type,entity_id,details) VALUES ('CREW_REASSIGNED','WORK_ORDER',?,jsonb_build_object('prior_assignment_id',?,'reason',?))",
    workOrderId,previous,r.reason());
  return result;
 }
 @Transactional
 public Map<String,Object> recordOutcome(long workOrderId, RecordOutcome r){
  if(r==null||r.inspectedAt()==null||!(r.outcomeType()!=null&&Set.of("CONFIRMED_LEAK","NO_LEAK","INCONCLUSIVE").contains(r.outcomeType())))throw bad("outcomeType and inspectedAt required");
  var rows=db.queryForList("SELECT case_id,status FROM work_orders WHERE work_order_id=? FOR UPDATE",workOrderId);
  if(rows.isEmpty())throw new ResponseStatusException(HttpStatus.NOT_FOUND,"work order not found");
  if(Set.of("COMPLETED","CLOSED").contains(rows.get(0).get("status")))throw new ResponseStatusException(HttpStatus.CONFLICT,"Outcome already recorded");
  if(!Set.of("ASSIGNED","IN_PROGRESS").contains(rows.get(0).get("status")))throw new ResponseStatusException(HttpStatus.CONFLICT,"Work order must be assigned or in progress before recording an outcome");
  if(r.estimatedWaterLossLitres()!=null&&r.estimatedWaterLossLitres()<0)throw bad("estimatedWaterLossLitres must be nonnegative");
  db.update("""
    INSERT INTO repair_outcomes(work_order_id,outcome_type,leak_type,estimated_water_loss_litres,repair_notes,inspected_at)
    VALUES (?,?,?,?,?,?)
  """,workOrderId,r.outcomeType(),r.leakType(),r.estimatedWaterLossLitres(),r.repairNotes(),r.inspectedAt());
  db.update("UPDATE work_orders SET status='COMPLETED',updated_at=now() WHERE work_order_id=?",workOrderId);
  var auth=org.springframework.security.core.context.SecurityContextHolder.getContext().getAuthentication();
  String actor=auth==null?"SYSTEM":auth.getName();
  db.update("INSERT INTO work_order_events(work_order_id,event_type,from_status,to_status,actor,reason) VALUES (?,?,?,?,?,?)",
   workOrderId,"OUTCOME_RECORDED",rows.get(0).get("status"),"COMPLETED",actor,
   "Inspection outcome: "+r.outcomeType()+"; "+(r.repairNotes()==null?"":r.repairNotes()));
  if(!"INCONCLUSIVE".equals(r.outcomeType())) db.update("""
    UPDATE leak_cases SET case_status=?,updated_at=now() WHERE case_id=?
  """, "CONFIRMED_LEAK".equals(r.outcomeType())?"CONFIRMED":"NO_LEAK_FOUND",rows.get(0).get("case_id"));
  return Map.of("work_order_id",workOrderId,"outcome",r.outcomeType(),"status","COMPLETED");
 }
}
