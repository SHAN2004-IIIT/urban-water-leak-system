package com.waterleak.scheduling;

import java.time.LocalDate;
import java.time.LocalDateTime;
import java.time.LocalTime;
import java.util.List;
import java.util.Map;
import org.springframework.http.HttpStatus;
import org.springframework.security.access.prepost.PreAuthorize;
import org.springframework.security.core.Authentication;
import org.springframework.web.bind.annotation.*;

@RestController
@RequestMapping("/api/scheduling")
public class SchedulingController {
 private final SchedulingService service;
 public SchedulingController(SchedulingService service){this.service=service;}

 public record AvailabilityRequest(String crewId, LocalDate date, LocalTime shiftStart,
      LocalTime shiftEnd, String status, String notes) {}
 public record AssignmentRequest(String crewId, LocalDateTime scheduledStart,
      LocalDateTime scheduledEnd, String reason) {}
 public record StatusRequest(String status, String reason) {}
 public record AccessRequest(String accessStatus, String reason) {}

 @GetMapping("/calendar") @PreAuthorize("hasAnyRole('ADMIN','SUPERVISOR')")
 public Map<String,Object> calendar(@RequestParam LocalDate from,@RequestParam LocalDate to){return service.calendar(from,to);}

 @PostMapping("/availability") @PreAuthorize("hasAnyRole('ADMIN','SUPERVISOR')")
 public Map<String,Object> availability(@RequestBody AvailabilityRequest request,Authentication auth){return service.setAvailability(request,auth.getName());}

 @PostMapping("/work-orders/{id}/assign") @PreAuthorize("hasAnyRole('ADMIN','SUPERVISOR')")
 public Map<String,Object> assign(@PathVariable long id,@RequestBody AssignmentRequest request,Authentication auth){return service.assign(id,request,auth.getName(),false);}

 @PostMapping("/work-orders/{id}/reassign") @PreAuthorize("hasAnyRole('ADMIN','SUPERVISOR')")
 public Map<String,Object> reassign(@PathVariable long id,@RequestBody AssignmentRequest request,Authentication auth){return service.assign(id,request,auth.getName(),true);}

 @PostMapping("/work-orders/{id}/status") @PreAuthorize("hasAnyRole('ADMIN','SUPERVISOR','CREW')")
 public Map<String,Object> status(@PathVariable long id,@RequestBody StatusRequest request,Authentication auth){return service.changeStatus(id,request,auth);}

 @PostMapping("/leak-cases/{id}/access") @PreAuthorize("hasAnyRole('ADMIN','SUPERVISOR')")
 public Map<String,Object> access(@PathVariable long id,@RequestBody AccessRequest request,Authentication auth){return service.setAccess(id,request,auth.getName());}

 @GetMapping("/work-orders/{id}/history") @PreAuthorize("hasAnyRole('ADMIN','SUPERVISOR','CREW')")
 public List<Map<String,Object>> history(@PathVariable long id, Authentication auth){return service.history(id,auth);}
}
