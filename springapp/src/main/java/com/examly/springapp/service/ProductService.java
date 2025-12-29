package com.examly.springapp.service;

import java.util.List;
import com.examly.springapp.model.Product;

public interface ProductService {

    // Day 10
    Product addProduct(Product product);

    List<Product> getAllProducts();

    Product getProductById(Long id);

    Product updateProduct(Long id, Product product);

    // Day 12
    List<Product> getProductsByCategoryName(String categoryName);

    Product getProductByName(String name);
}
