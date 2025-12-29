package com.examly.springapp.model;

import jakarta.persistence.Entity;
import jakarta.persistence.Id;

@Entity
public class StockMovement {
    @Id
    private Long movementId;
    private Long productId;
    private long warehouseId;
    private Integer quantity;
    public StockMovement() {
    }
    public Long getMovementId() {
        return movementId;
    }
    public void setMovementId(Long movementId) {
        this.movementId = movementId;
    }
    public Long getProductId() {
        return productId;
    }
    public void setProductId(Long productId) {
        this.productId = productId;
    }
    public long getWarehouseId() {
        return warehouseId;
    }
    public void setWarehouseId(long warehouseId) {
        this.warehouseId = warehouseId;
    }
    public Integer getQuantity() {
        return quantity;
    }
    public void setQuantity(Integer quantity) {
        this.quantity = quantity;
    }
    
    
}
