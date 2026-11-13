package com.waterleak.scheduling;

import java.time.*;
import java.util.*;

import org.springframework.dao.DataIntegrityViolationException;
import org.springframework.http.HttpStatus;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.security.core.Authentication;
import org.springframework.stereotype.Service;
import org.springframework.transaction.annotation.Transactional;
import org.springframework.web.server.ResponseStatusException;

@Service
public class SchedulingService {
 private final JdbcTemplate db;
 public SchedulingService(JdbcTemplate db){this.db=db;}
 private ResponseStatusException err(HttpStatus code,String text){return new ResponseStatusException(code,text);}
 private void require(boolean cond,String why){if(!cond)throw err(HttpStatus.BAD_REQUEST,why);}
 private void log(long id,String event,String before,String after,String actor,String reason){
  db.update("INSERT INTO work_order_events(work_order_id,event_type,from_status,to_status,actor,reason) VALUES (?,?,?,?,?,?)",
   id,event,before,after,actor,reason);
 }
 private void lock(long id){db.query("SELECT pg_advisory_xact_lock(?)", rs -> {}, id);}
 private long crewLock(String crew){return 500000000L+Integer.toUnsignedLong(crew.hashCode());}
 private long orderLock(long order){return 9000000000L+order;}
 private void authorizedCrew(long id,Authentication auth){
  if(auth.getAuthorities().stream().noneMatch(a->a.getAuthority().equals("ROLE_CREW")))return;
  Integer count=db.queryForObject("""
   SELECT count(*) FROM crew_assignments ca JOIN app_users u ON u.crew_id=ca.crew_id
   WHERE ca.work_order_id=? AND ca.assignment_status='ACTIVE' AND u.username=?
  """,Integer.class,id,auth.getName());
  if(count==null||count==0)throw err(HttpStatus.FORBIDDEN,"Work order not assigned to your crew");
 }
 @Transactional(readOnly=true)
 public Map<String,Object> calendar(LocalDate from,LocalDate to){
  require(from!=null&&to!=null&&!to.isBefore(from)&&!to.isAfter(from.plusDays(31)),"Date range must be 0–31 days");
  var shifts=db.queryForList("""
   SELECT c.crew_id,c.crew_name,c.availability_status AS roster_status,c.availability_date AS base_available_date,c.shift_start AS default_start,
     c.shift_end AS default_end,c.max_jobs_per_day,d.available_date,d.shift_start,d.shift_end,
     d.availability_status AS day_status,d.notes
   FROM crews c LEFT JOIN crew_availability d ON d.crew_id=c.crew_id
     AND d.available_date BETWEEN ? AND ? ORDER BY c.crew_id,d.available_date
  """,from,to);
  var bookings=db.queryForList("""
   SELECT a.assignment_id,a.work_order_id,a.crew_id,a.scheduled_start,a.scheduled_end,
    w.status,l.zone_id,l.location_id,l.case_id
   FROM crew_assignments a JOIN work_orders w ON w.work_order_id=a.work_order_id
    JOIN leak_cases l ON l.case_id=w.case_id
   WHERE a.assignment_status='ACTIVE' AND a.scheduled_start<? AND a.scheduled_end>?
   ORDER BY a.scheduled_start
  """,to.plusDays(1).atStartOfDay(),from.atStartOfDay());
  return Map.of("from",from,"to",to,"shifts",shifts,"bookings",bookings);
 }
 @Transactional
 public Map<String,Object> setAvailability(SchedulingController.AvailabilityRequest r,String actor){
  require(r!=null&&r.crewId()!=null&&r.date()!=null&&r.shiftStart()!=null&&r.shiftEnd()!=null&&r.shiftEnd().isAfter(r.shiftStart()),"Crew, date and valid shift times are required");
  require(Set.of("AVAILABLE","LEAVE","UNAVAILABLE").contains(r.status()),"Invalid availability status");
  lock(crewLock(r.crewId()));
  if(db.queryForList("SELECT 1 FROM crews WHERE crew_id=?",r.crewId()).isEmpty())throw err(HttpStatus.NOT_FOUND,"Crew not found");
  if(!"AVAILABLE".equals(r.status())){
   Integer existing=db.queryForObject("""
    SELECT count(*) FROM crew_assignments WHERE crew_id=? AND assignment_status='ACTIVE'
    AND scheduled_start::date=?
   """,Integer.class,r.crewId(),r.date());
   if(existing!=null&&existing>0)throw err(HttpStatus.CONFLICT,"Reassign active bookings before marking leave");
  }
  db.update("""
   INSERT INTO crew_availability(crew_id,available_date,shift_start,shift_end,availability_status,notes)
   VALUES(?,?,?,?,?,?) ON CONFLICT(crew_id,available_date) DO UPDATE SET
    shift_start=EXCLUDED.shift_start,shift_end=EXCLUDED.shift_end,
    availability_status=EXCLUDED.availability_status,notes=EXCLUDED.notes,updated_at=now()
  """,r.crewId(),r.date(),r.shiftStart(),r.shiftEnd(),r.status(),r.notes());
  return Map.of("crew_id",r.crewId(),"date",r.date(),"status",r.status());
 }
 @Transactional
 public Map<String,Object> assign(long id,SchedulingController.AssignmentRequest r,String actor,boolean replace){
  require(r!=null&&r.crewId()!=null&&!r.crewId().isBlank()&&r.scheduledStart()!=null&&r.scheduledEnd()!=null&&r.scheduledEnd().isAfter(r.scheduledStart()),"Valid crew and time window required");
  require(r.reason()!=null&&!r.reason().isBlank(),"Scheduling reason required");
  require(r.scheduledStart().toLocalDate().equals(r.scheduledEnd().toLocalDate()),"Use a single-day booking");
  // Fixed lock order (work order, then crew) prevents conflicting concurrent assignments.
  lock(orderLock(id));
  var orders=db.queryForList("""
   SELECT w.status,w.case_id,l.access_status FROM work_orders w
   JOIN leak_cases l ON l.case_id=w.case_id WHERE w.work_order_id=? FOR UPDATE OF w,l
  """,id);
  if(orders.isEmpty())throw err(HttpStatus.NOT_FOUND,"Work order not found");
  var order=orders.get(0);String prior=String.valueOf(order.get("status"));
  if(!Set.of("CREATED","ASSIGNED","DEFERRED").contains(prior))throw err(HttpStatus.CONFLICT,"Work order status not schedulable");
  if(!"OPEN".equals(order.get("access_status")))throw err(HttpStatus.CONFLICT,"Case access must be OPEN");
  var active=db.queryForList("SELECT assignment_id,crew_id FROM crew_assignments WHERE work_order_id=? AND assignment_status='ACTIVE'",id);
  if(replace&&active.isEmpty())throw err(HttpStatus.CONFLICT,"No assignment to replace");
  if(!replace&&!active.isEmpty())throw err(HttpStatus.CONFLICT,"Already assigned; use reassign");
  String oldCrew=active.isEmpty()?null:String.valueOf(active.get(0).get("crew_id"));
  // Lock involved crews in sorted order, regardless of source/destination.
  TreeSet<String> locked=new TreeSet<>();locked.add(r.crewId());if(oldCrew!=null)locked.add(oldCrew);
  for(String c:locked)lock(crewLock(c));
  var crews=db.queryForList("SELECT * FROM crews WHERE crew_id=? FOR UPDATE",r.crewId());
  if(crews.isEmpty())throw err(HttpStatus.NOT_FOUND,"Crew not found");
  var crew=crews.get(0);
  var overrides=db.queryForList("SELECT * FROM crew_availability WHERE crew_id=? AND available_date=?",
   r.crewId(),r.scheduledStart().toLocalDate());
  Map<String,Object> shift=overrides.isEmpty()?crew:overrides.get(0);
  // The original crews.csv availability flag belongs to one snapshot date, not every future day.
  // Treat historical 'Assigned' as a snapshot label; actual occupancy comes from crew_assignments.
  String availability;
  if(!overrides.isEmpty()) availability=String.valueOf(shift.get("availability_status"));
  else {
   String seedStatus=String.valueOf(crew.get("availability_status")).toUpperCase(Locale.ROOT).replace(" ","");
   boolean onSeedDate=r.scheduledStart().toLocalDate().equals(crew.get("availability_date"));
   availability=onSeedDate && Set.of("OFFDUTY","UNAVAILABLE","LEAVE").contains(seedStatus)
      ? "UNAVAILABLE" : "AVAILABLE";
  }
  if(!"AVAILABLE".equalsIgnoreCase(availability))throw err(HttpStatus.CONFLICT,"Crew unavailable for selected date; change dated availability first");
  LocalTime start=time(shift.get("shift_start")); LocalTime end=time(shift.get("shift_end"));
  if(r.scheduledStart().toLocalTime().isBefore(start)||r.scheduledEnd().toLocalTime().isAfter(end))
   throw err(HttpStatus.CONFLICT,"Outside crew shift");
  // Cross-check bookings; the SQL exclusion constraint also rejects races.
  Integer overlap=db.queryForObject("""
   SELECT count(*) FROM crew_assignments WHERE crew_id=? AND assignment_status='ACTIVE'
    AND scheduled_start<? AND scheduled_end>? AND work_order_id<>?
  """,Integer.class,r.crewId(),r.scheduledEnd(),r.scheduledStart(),id);
  if(overlap!=null&&overlap>0)throw err(HttpStatus.CONFLICT,"Crew already booked");
  Integer dayCount=db.queryForObject("""
   SELECT count(*) FROM crew_assignments WHERE crew_id=? AND assignment_status='ACTIVE'
     AND scheduled_start::date=? AND work_order_id<>?
  """,Integer.class,r.crewId(),r.scheduledStart().toLocalDate(),id);
  if(dayCount!=null&&dayCount>=((Number)crew.get("max_jobs_per_day")).intValue())
   throw err(HttpStatus.CONFLICT,"Crew daily capacity exceeded");
  if(replace)db.update("UPDATE crew_assignments SET assignment_status='REASSIGNED' WHERE work_order_id=? AND assignment_status='ACTIVE'",id);
  long assignment;
  try{
   assignment=db.queryForObject("""
    INSERT INTO crew_assignments(work_order_id,crew_id,scheduled_start,scheduled_end,reason)
    VALUES(?,?,?,?,?) RETURNING assignment_id
   """,Long.class,id,r.crewId(),r.scheduledStart(),r.scheduledEnd(),r.reason());
  }catch(DataIntegrityViolationException ex){throw err(HttpStatus.CONFLICT,"Booking conflict detected by database");}
  db.update("UPDATE work_orders SET status='ASSIGNED',updated_at=now(),scheduling_reason=? WHERE work_order_id=?",r.reason(),id);
  log(id,replace?"REASSIGNED":"ASSIGNED",prior,"ASSIGNED",actor,r.reason());
  Map<String,Object> output=new LinkedHashMap<>();output.put("work_order_id",id);output.put("assignment_id",assignment);
  output.put("crew_id",r.crewId());output.put("previous_crew_id",oldCrew);output.put("status","ASSIGNED");return output;
 }
 private LocalTime time(Object value){
  if(value instanceof java.sql.Time t)return t.toLocalTime();
  if(value instanceof LocalTime t)return t;
  return LocalTime.parse(value.toString());
 }
 @Transactional
 public Map<String,Object> changeStatus(long id,SchedulingController.StatusRequest r,Authentication auth){
  require(r!=null&&r.status()!=null&&r.reason()!=null&&!r.reason().isBlank(),"Status and reason required");
  lock(orderLock(id));
  var rows=db.queryForList("SELECT status FROM work_orders WHERE work_order_id=? FOR UPDATE",id);
  if(rows.isEmpty())throw err(HttpStatus.NOT_FOUND,"Work order not found");
  String before=String.valueOf(rows.get(0).get("status")),after=r.status();
  boolean isCrew=auth.getAuthorities().stream().anyMatch(a->a.getAuthority().equals("ROLE_CREW"));
  if(isCrew){authorizedCrew(id,auth);if(!("ASSIGNED".equals(before)&&"IN_PROGRESS".equals(after)))
   throw err(HttpStatus.FORBIDDEN,"Crew may only begin their assigned job; use outcome endpoint to finish");}
  Map<String,Set<String>> allowed=Map.of(
   "CREATED",Set.of("DEFERRED"),"DEFERRED",Set.of("CREATED"),
   "ASSIGNED",Set.of("IN_PROGRESS","DEFERRED"),
   "IN_PROGRESS",Set.of("DEFERRED"),"COMPLETED",Set.of("CLOSED"));
  if(!allowed.getOrDefault(before,Set.of()).contains(after))throw err(HttpStatus.CONFLICT,"Invalid transition "+before+" -> "+after);
  if("DEFERRED".equals(after))db.update("UPDATE crew_assignments SET assignment_status='CANCELLED' WHERE work_order_id=? AND assignment_status='ACTIVE'",id);
  db.update("UPDATE work_orders SET status=?,updated_at=now() WHERE work_order_id=?",after,id);
  log(id,"STATUS_CHANGED",before,after,auth.getName(),r.reason());
  return Map.of("work_order_id",id,"status",after);
 }
 @Transactional
 public Map<String,Object> setAccess(long caseId,SchedulingController.AccessRequest r,String actor){
  require(r!=null&&Set.of("OPEN","BLOCKED","UNKNOWN").contains(r.accessStatus())&&r.reason()!=null&&!r.reason().isBlank(),"Access status and reason required");
  var cases=db.queryForList("SELECT case_id FROM leak_cases WHERE case_id=? FOR UPDATE",caseId);
  if(cases.isEmpty())throw err(HttpStatus.NOT_FOUND,"Case not found");
  db.update("UPDATE leak_cases SET access_status=?,access_reason=?,updated_at=now() WHERE case_id=?",r.accessStatus(),r.reason(),caseId);
  if(!"OPEN".equals(r.accessStatus())){
   db.update("INSERT INTO access_restrictions(case_id,details,reported_by) VALUES(?,?,?)",caseId,r.reason(),actor);
 
List<Map<String, Object>> orders = db.queryForList(
    """
    SELECT work_order_id, status
    FROM work_orders
    WHERE case_id = ?
      AND status IN ('ASSIGNED', 'IN_PROGRESS')
    FOR UPDATE
    """,
    caseId
);

for (Map<String, Object> order : orders) {
    long id = ((Number) order.get("work_order_id")).longValue();
    String before = String.valueOf(order.get("status"));

    db.update(
        """
        UPDATE crew_assignments
        SET assignment_status = 'CANCELLED'
        WHERE work_order_id = ?
          AND assignment_status = 'ACTIVE'
        """,
        id
    );

    db.update(
        """
        UPDATE work_orders
        SET status = 'DEFERRED',
            updated_at = now(),
            scheduling_reason = ?
        WHERE work_order_id = ?
        """,
        r.reason(),
        id
    );

    log(
        id,
        "ACCESS_BLOCKED",
        before,
        "DEFERRED",
        actor,
        r.reason()
    );
}

  } else db.update("UPDATE access_restrictions SET active=false,resolved_at=now() WHERE case_id=? AND active=true",caseId);
  return Map.of("case_id",caseId,"access_status",r.accessStatus());
 }
 @Transactional(readOnly=true)
 public List<Map<String,Object>> history(long id,Authentication auth){
  authorizedCrew(id,auth);
  return db.queryForList("SELECT event_id,event_type,from_status,to_status,actor,reason,recorded_at FROM work_order_events WHERE work_order_id=? ORDER BY event_id",id);
 }
}
