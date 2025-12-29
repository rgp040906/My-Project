
package com.examly.springapp.service;

import java.util.List;
import com.examly.springapp.model.Warehouse;

public interface WarehouseService {
    Warehouse addWarehouse(Warehouse warehouse);
    


    List<Warehouse> getAllWarehouses();
    Warehouse getWarehouseById(Long id);
    Warehouse updateWarehouse(Long id, Warehouse warehouse);
      List<Warehouse> getWarehousesByLocation(String location);

    Warehouse getWarehouseByLocationAndName(String location, String name);
}

