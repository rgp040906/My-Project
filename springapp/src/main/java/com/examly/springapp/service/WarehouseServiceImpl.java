package com.examly.springapp.service;

import java.util.ArrayList;
import java.util.List;

import org.springframework.stereotype.Service;
import com.examly.springapp.model.Warehouse;

@Service
public class WarehouseServiceImpl implements WarehouseService {

    // MUST be static (data persists across tests)
    private static final List<Warehouse> warehouses = new ArrayList<>();
    private static long idCounter = 1;

    // ================= DAY 10 =================

    @Override
    public Warehouse addWarehouse(Warehouse warehouse) {
        warehouse.setWarehouseId(idCounter++);
        warehouses.add(warehouse);
        return warehouse;
    }

    @Override
    public List<Warehouse> getAllWarehouses() {
        return warehouses;
    }

    @Override
    public Warehouse getWarehouseById(Long id) {
        for (Warehouse w : warehouses) {
            if (w.getWarehouseId().equals(id)) {   // ✅ FIXED
                return w;
            }
        }
        return null;
    }

    @Override
    public Warehouse updateWarehouse(Long id, Warehouse warehouse) {
        for (Warehouse w : warehouses) {
            if (w.getWarehouseId().equals(id)) {   // ✅ FIXED
                w.setName(warehouse.getName());
                w.setLocation(warehouse.getLocation());
                return w;
            }
        }
        return null;
    }

    // ================= DAY 11 / 12 =================

    @Override
    public List<Warehouse> getWarehousesByLocation(String location) {
        List<Warehouse> result = new ArrayList<>();
        for (Warehouse w : warehouses) {
            if (w.getLocation() != null &&
                w.getLocation().equalsIgnoreCase(location)) {
                result.add(w);
            }
        }
        return result;
    }

@Override
public Warehouse getWarehouseByLocationAndName(String location, String name) {
    for (Warehouse w : warehouses) {
        if (w.getLocation() != null &&
            w.getName() != null &&
            w.getLocation().trim().equalsIgnoreCase(location.trim()) &&
            w.getName().trim().equalsIgnoreCase(name.trim())) {
            return w;
        }
    }
    return null;
}

}
