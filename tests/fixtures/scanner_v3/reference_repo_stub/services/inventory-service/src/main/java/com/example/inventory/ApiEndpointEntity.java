package com.example.inventory;

import jakarta.persistence.Entity;
import jakarta.persistence.Id;

@Entity
public class ApiEndpointEntity {
    @Id
    private Long id;
}
