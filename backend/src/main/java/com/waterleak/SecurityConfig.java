
package com.waterleak;

import java.util.List;

import org.springframework.context.annotation.Bean;
import org.springframework.context.annotation.Configuration;
import org.springframework.http.HttpMethod;
import org.springframework.security.config.Customizer;
import org.springframework.security.config.annotation.method.configuration.EnableMethodSecurity;
import org.springframework.security.config.annotation.web.builders.HttpSecurity;
import org.springframework.security.config.http.SessionCreationPolicy;
import org.springframework.security.core.authority.SimpleGrantedAuthority;
import org.springframework.security.core.userdetails.User;
import org.springframework.security.core.userdetails.UserDetailsService;
import org.springframework.security.core.userdetails.UsernameNotFoundException;
import org.springframework.security.crypto.bcrypt.BCryptPasswordEncoder;
import org.springframework.security.crypto.password.PasswordEncoder;
import org.springframework.security.provisioning.JdbcUserDetailsManager;
import org.springframework.security.web.SecurityFilterChain;
import org.springframework.web.cors.CorsConfiguration;
import org.springframework.web.cors.CorsConfigurationSource;
import org.springframework.web.cors.UrlBasedCorsConfigurationSource;
import org.springframework.jdbc.core.JdbcTemplate;

@Configuration
@EnableMethodSecurity
public class SecurityConfig {

    @Bean
    PasswordEncoder passwordEncoder() {
        return new BCryptPasswordEncoder();
    }

    @Bean
    UserDetailsService users(JdbcTemplate db) {
        return username -> db.query(
            "SELECT username, password_hash, role, enabled " +
            "FROM app_users WHERE username=?",
            (rs, row) -> User.withUsername(rs.getString("username"))
                .password(rs.getString("password_hash"))
                .authorities(
                    new SimpleGrantedAuthority(
                        "ROLE_" + rs.getString("role")
                    )
                )
                .disabled(!rs.getBoolean("enabled"))
                .build(),
            username
        ).stream().findFirst()
         .orElseThrow(() ->
             new UsernameNotFoundException("Unknown user")
         );
    }

    @Bean
    CorsConfigurationSource corsConfigurationSource() {

        CorsConfiguration config = new CorsConfiguration();

        // React frontend origins
        config.setAllowedOrigins(List.of(
            "http://127.0.0.1:8088",
            "http://localhost:8088",
            "http://127.0.0.1:5173",
            "http://localhost:5173"
        ));

        // HTTP methods allowed from frontend
        config.setAllowedMethods(List.of(
            "GET",
            "POST",
            "PUT",
            "PATCH",
            "DELETE",
            "OPTIONS"
        ));

        // Request headers allowed
        config.setAllowedHeaders(List.of(
            "Authorization",
            "Content-Type",
            "Accept",
            "Origin",
            "X-Requested-With"
        ));

        // Allow browser credentials with the explicitly listed origins
        config.setAllowCredentials(true);

        // Cache preflight response for one hour
        config.setMaxAge(3600L);

        UrlBasedCorsConfigurationSource source =
            new UrlBasedCorsConfigurationSource();

        source.registerCorsConfiguration("/api/**", config);

        return source;
    }

    @Bean
    SecurityFilterChain filterChain(HttpSecurity http) throws Exception {

        return http
            .cors(Customizer.withDefaults())

            // Stateless API using HTTP Basic authentication
            .csrf(csrf -> csrf.disable())

            .sessionManagement(session ->
                session.sessionCreationPolicy(
                    SessionCreationPolicy.STATELESS
                )
            )

            .authorizeHttpRequests(auth -> auth

                .requestMatchers("/api/health").permitAll()

                // Allow browser CORS preflight requests
                .requestMatchers(HttpMethod.OPTIONS, "/**").permitAll()

                // Other endpoints require authentication
                .anyRequest().authenticated()
            )

            .httpBasic(Customizer.withDefaults())

            .build();
    }
}
