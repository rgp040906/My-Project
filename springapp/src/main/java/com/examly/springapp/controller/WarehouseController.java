package com.examly.springapp.controller;

import java.util.ArrayList;
import java.util.List;

import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.http.HttpStatus;
import org.springframework.http.ResponseEntity;
import org.springframework.web.bind.annotation.*;

import com.examly.springapp.model.Warehouse;
import com.examly.springapp.service.WarehouseService;

@RestController
@RequestMapping("/api/warehouses")
public class WarehouseController {

    @Autowired
    private WarehouseService warehouseService;

    // DAY 10
    @PostMapping
    public ResponseEntity<Warehouse> addWarehouse(@RequestBody Warehouse warehouse) {
        return new ResponseEntity<>(
                warehouseService.addWarehouse(warehouse),
                HttpStatus.CREATED);
    }

    @GetMapping
    public ResponseEntity<List<Warehouse>> getAllWarehouses() {
        return new ResponseEntity<>(
                warehouseService.getAllWarehouses(),
                HttpStatus.OK);
    }

 @GetMapping("/location/{location}/name/{name}")
public ResponseEntity<List<Warehouse>> getWarehouseByLocationAndName(
        @PathVariable String location,
        @PathVariable String name) {

    Warehouse warehouse =
            warehouseService.getWarehouseByLocationAndName(location, name);

    List<Warehouse> result = new ArrayList<>();
    if (warehouse != null) {
        result.add(warehouse);
    }

    return new ResponseEntity<>(result, HttpStatus.OK);
}



    // DAY 11
    @GetMapping("/location/{location}")
    public ResponseEntity<?> getWarehousesByLocation(@PathVariable String location) {

        List<Warehouse> list = warehouseService.getWarehousesByLocation(location);

        if (list.isEmpty()) {
            return new ResponseEntity<>(
                    "No warehouses found at location: " + location,
                    HttpStatus.NO_CONTENT);
        }
        return new ResponseEntity<>(list, HttpStatus.OK);
    }

    // GENERIC ID LAST
    @GetMapping("/{id}")
    public ResponseEntity<Warehouse> getWarehouseById(@PathVariable Long id) {
        return new ResponseEntity<>(
                warehouseService.getWarehouseById(id),
                HttpStatus.OK);
    }

    @PutMapping("/{id}")
    public ResponseEntity<Warehouse> updateWarehouse(
            @PathVariable Long id,
            @RequestBody Warehouse warehouse) {

        return new ResponseEntity<>(
                warehouseService.updateWarehouse(id, warehouse),
                HttpStatus.OK);
    }
}
