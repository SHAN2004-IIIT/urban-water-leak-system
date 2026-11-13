package com.waterleak;

import org.springframework.boot.ApplicationRunner;
import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.jdbc.core.JdbcTemplate;
import org.springframework.security.crypto.password.PasswordEncoder;

@Configuration
public class BootstrapUsers {
 private void add(JdbcTemplate db,PasswordEncoder encoder,String username,String env,String role,String crewId){
  String password=System.getenv(env);
  if(password==null||password.isBlank())return;
  if(password.length()<12)throw new IllegalArgumentException(env+" needs at least 12 characters");
  db.update("INSERT INTO app_users(username,password_hash,role,crew_id) VALUES (?,?,?,?) ON CONFLICT (username) DO NOTHING",
     username,encoder.encode(password),role,crewId);
 }
 @Bean ApplicationRunner bootstrap(JdbcTemplate db, PasswordEncoder encoder){
  return args -> {
   add(db,encoder,"admin","BOOTSTRAP_ADMIN_PASSWORD","ADMIN",null);
   add(db,encoder,"supervisor","BOOTSTRAP_SUPERVISOR_PASSWORD","SUPERVISOR",null);
   String crewId=System.getenv("BOOTSTRAP_CREW_ID");
   if(crewId!=null&&!crewId.isBlank())add(db,encoder,"fieldcrew","BOOTSTRAP_CREW_PASSWORD","CREW",crewId);
    add(db, encoder, "crew02",
        "BOOTSTRAP_CREW02_PASSWORD", "CREW", "CR002");

    add(db, encoder, "crew03",
        "BOOTSTRAP_CREW03_PASSWORD", "CREW", "CR003");

    add(db, encoder, "crew04",
        "BOOTSTRAP_CREW04_PASSWORD", "CREW", "CR004");

    add(db, encoder, "crew05",
        "BOOTSTRAP_CREW05_PASSWORD", "CREW", "CR005");

    add(db, encoder, "crew06",
        "BOOTSTRAP_CREW06_PASSWORD", "CREW", "CR006");

    Integer count = db.queryForObject(
            "SELECT COUNT(*) FROM app_users",
            Integer.class
        );

        System.out.println(
            "BOOTSTRAP: Total users = " + count);
  };
 }
}
