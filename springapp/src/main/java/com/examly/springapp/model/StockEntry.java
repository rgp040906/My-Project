package com.examly.springapp.model;

import jakarta.persistence.Entity;
import jakarta.persistence.Id;

@Entity
public class StockEntry {
    @Id
    private Long stockEntryId;

    private Long productId;
    private Long warehouseId;
    private Integer quantity;
    public StockEntry() {
    }
    public Long getstockEntryId() {
        return stockEntryId;
    }
    public void setStockEntryId(Long stockEntryId) {
        stockEntryId = stockEntryId;
    }
    public Long getProductId() {
        return productId;
    }
    public void setProductId(Long productId) {
        this.productId = productId;
    }
    public Long getWarehouseId() {
        return warehouseId;
    }
    public void setWarehouseId(Long warehouseId) {
        this.warehouseId = warehouseId;
    }
    public Integer getQuantity() {
        return quantity;
    }
    public void setQuantity(Integer quantity) {
        this.quantity = quantity;
    }
    
}
