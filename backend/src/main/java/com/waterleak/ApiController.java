package com.waterleak;

import java.util.*;
import java.time.LocalDate;
import org.springframework.http.*;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.security.core.Authentication;
import org.springframework.web.bind.annotation.*;
import org.springframework.web.server.ResponseStatusException;

@RestController
@RequestMapping("/api")
public class ApiController {
 private final JdbcTemplate db;
 private final WorkOrderService orders;
 private final com.waterleak.scheduling.SchedulingService schedule;
 public ApiController(JdbcTemplate db,WorkOrderService orders,com.waterleak.scheduling.SchedulingService schedule){this.db=db;this.orders=orders;this.schedule=schedule;}
 @GetMapping("/health") public Map<String,String> health(){return Map.of("status","ok");}
 @GetMapping("/auth/me") public Map<String,Object> me(Authentication a){
  var user=db.queryForMap("SELECT username,role,crew_id FROM app_users WHERE username=?",a.getName());
  return user;
 }
 @GetMapping("/zones") @PreAuthorize("hasAnyRole('ADMIN','SUPERVISOR')")
 public List<Map<String,Object>> zones(){return db.queryForList("SELECT zone_id,zone_name,city,zone_status FROM zones ORDER BY zone_id");}
 @GetMapping("/crews") @PreAuthorize("hasAnyRole('ADMIN','SUPERVISOR')")
 public List<Map<String,Object>> crews(@RequestParam(required=false) LocalDate date){
  LocalDate day=date==null?LocalDate.now():date;
  // Availability is DATE-SPECIFIC: a generated CSV's roster status is not a perpetual live status.
  // A historic OffDuty flag applies only on the seed date; dated overrides take precedence.
  return db.queryForList("""
   SELECT c.crew_id,c.crew_name,
     CASE
       WHEN status.effective_status <> 'AVAILABLE' THEN status.effective_status
       WHEN bookings.assigned_jobs >= c.max_jobs_per_day THEN 'FULL'
       WHEN bookings.assigned_jobs > 0 THEN 'PARTIALLY_BOOKED'
       ELSE 'AVAILABLE'
     END AS availability_status,
     ?::date AS availability_date,
     COALESCE(d.shift_start,c.shift_start) AS shift_start,
     COALESCE(d.shift_end,c.shift_end) AS shift_end,
     c.max_jobs_per_day,
     bookings.assigned_jobs,
     GREATEST(0,c.max_jobs_per_day-bookings.assigned_jobs) AS remaining_capacity,
     status.effective_status AS shift_status
   FROM crews c
   LEFT JOIN crew_availability d
     ON d.crew_id=c.crew_id AND d.available_date=?
   CROSS JOIN LATERAL (
     SELECT CASE
       WHEN d.availability_status IS NOT NULL THEN d.availability_status
       WHEN c.availability_date=?
         AND UPPER(REPLACE(c.availability_status,' ','')) IN ('OFFDUTY','UNAVAILABLE','LEAVE')
         THEN 'UNAVAILABLE'
       ELSE 'AVAILABLE'
     END AS effective_status
   ) status
   CROSS JOIN LATERAL (
     SELECT COUNT(*)::int AS assigned_jobs
     FROM crew_assignments a
     WHERE a.crew_id=c.crew_id AND a.assignment_status='ACTIVE'
       AND a.scheduled_start::date=?
   ) bookings
   ORDER BY c.crew_id
  """,day,day,day,day);
 }
 @GetMapping("/leak-cases") @PreAuthorize("hasAnyRole('ADMIN','SUPERVISOR')")
 public List<Map<String,Object>> cases(){return db.queryForList("""
  SELECT l.case_id,l.source_case_id,l.zone_id,l.location_id,l.meter_id,l.case_status,
         l.access_status,l.access_reason,l.risk_band,
         s.score AS risk_score,s.score_components::text AS score_components,s.model_version
  FROM leak_cases l LEFT JOIN LATERAL
   (SELECT score,score_components,model_version FROM risk_scores r
    WHERE r.case_id=l.case_id ORDER BY calculated_at DESC,risk_score_id DESC LIMIT 1) s ON TRUE
  ORDER BY s.score DESC NULLS LAST,l.case_id
 """);}
 @GetMapping("/leak-cases/{id}/score") @PreAuthorize("hasAnyRole('ADMIN','SUPERVISOR')")
 public Map<String,Object> score(@PathVariable long id){
  var rows=db.queryForList("""
   SELECT risk_score_id,case_id,score,score_components::text AS score_components,model_name,model_version,
          data_quality_notes,calculated_at FROM risk_scores
   WHERE case_id=? ORDER BY calculated_at DESC,risk_score_id DESC LIMIT 1
  """,id);
  if(rows.isEmpty())throw new ResponseStatusException(HttpStatus.NOT_FOUND,"No score for case");
  return rows.get(0);
 }
 @GetMapping("/work-orders") @PreAuthorize("hasAnyRole('ADMIN','SUPERVISOR')")
 public List<Map<String,Object>> workOrders(){return db.queryForList("""
   SELECT w.work_order_id,w.case_id,w.work_type,w.status,w.scheduling_reason,w.created_at,
    a.crew_id,a.scheduled_start,a.scheduled_end
   FROM work_orders w LEFT JOIN LATERAL
    (SELECT crew_id,scheduled_start,scheduled_end FROM crew_assignments
      WHERE work_order_id=w.work_order_id AND assignment_status='ACTIVE'
      ORDER BY assignment_id DESC LIMIT 1) a ON TRUE
   ORDER BY w.work_order_id DESC
 """);}
 @GetMapping("/my/work-orders") @PreAuthorize("hasRole('CREW')")
 public List<Map<String,Object>> myOrders(Authentication auth){return db.queryForList("""
  SELECT w.work_order_id,w.case_id,w.work_type,w.status,a.scheduled_start,a.scheduled_end,
      l.zone_id,l.location_id,l.access_status
  FROM work_orders w JOIN crew_assignments a ON a.work_order_id=w.work_order_id
  JOIN leak_cases l ON l.case_id=w.case_id
  JOIN app_users u ON u.crew_id=a.crew_id
  WHERE u.username=? AND a.assignment_status='ACTIVE'
  ORDER BY a.scheduled_start DESC
 """,auth.getName());}
 @PostMapping("/work-orders") @PreAuthorize("hasAnyRole('ADMIN','SUPERVISOR')")
 public ResponseEntity<Map<String,Object>> create(@RequestBody WorkOrderService.CreateWorkOrder req){
  long id=orders.create(req);
  return ResponseEntity.status(HttpStatus.CREATED).body(Map.of("work_order_id",id,"status","CREATED"));
 }
 @PostMapping("/work-orders/{id}/assign") @PreAuthorize("hasAnyRole('ADMIN','SUPERVISOR')")
 public Map<String,Object> assign(@PathVariable long id,@RequestBody WorkOrderService.AssignCrew req,Authentication auth){return schedule.assign(id,new com.waterleak.scheduling.SchedulingController.AssignmentRequest(req.crewId(),req.scheduledStart(),req.scheduledEnd(),req.reason()),auth.getName(),false);}
 @PostMapping("/work-orders/{id}/reassign") @PreAuthorize("hasAnyRole('ADMIN','SUPERVISOR')")
 public Map<String,Object> reassign(@PathVariable long id,@RequestBody WorkOrderService.AssignCrew req,Authentication auth){return schedule.assign(id,new com.waterleak.scheduling.SchedulingController.AssignmentRequest(req.crewId(),req.scheduledStart(),req.scheduledEnd(),req.reason()),auth.getName(),true);}
 @PostMapping("/work-orders/{id}/outcome") @PreAuthorize("hasAnyRole('ADMIN','SUPERVISOR','CREW')")
 public Map<String,Object> outcome(@PathVariable long id,@RequestBody WorkOrderService.RecordOutcome req,Authentication auth){
  if(auth.getAuthorities().stream().anyMatch(x->x.getAuthority().equals("ROLE_CREW"))){
   Integer count=db.queryForObject("""
    SELECT COUNT(*) FROM crew_assignments a JOIN app_users u ON u.crew_id=a.crew_id
    WHERE a.work_order_id=? AND a.assignment_status='ACTIVE' AND u.username=?
   """,Integer.class,id,auth.getName());
   if(count==null||count==0)throw new ResponseStatusException(HttpStatus.FORBIDDEN,"Not assigned to your crew");
  }
  return orders.recordOutcome(id,req);
 }
 @PatchMapping("/leak-cases/{id}/access") @PreAuthorize("hasAnyRole('ADMIN','SUPERVISOR')")
 public Map<String,Object> access(@PathVariable long id,@RequestBody WorkOrderService.AccessUpdate req,Authentication auth){return schedule.setAccess(id,new com.waterleak.scheduling.SchedulingController.AccessRequest(req.accessStatus(),req.reason()),auth.getName());}
}
