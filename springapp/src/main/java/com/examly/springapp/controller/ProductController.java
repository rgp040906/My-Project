
package com.examly.springapp.controller;

import java.util.List;

import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.http.*;
import org.springframework.web.bind.annotation.*;

import com.examly.springapp.model.Product;
import com.examly.springapp.service.ProductService;

@RestController
@RequestMapping("/api/products")
public class ProductController {

    @Autowired
    private ProductService productService;

    @PostMapping
    public ResponseEntity<Product> addProduct(@RequestBody Product product) {
        Product saved = productService.addProduct(product);
        return new ResponseEntity<>(saved, HttpStatus.CREATED);
    }

    @GetMapping
    public ResponseEntity<List<Product>> getAllProducts() {
        return new ResponseEntity<>(productService.getAllProducts(), HttpStatus.OK);
    }

    @GetMapping("/{id}")
    public ResponseEntity<Product> getProductById(@PathVariable Long id) {
        return new ResponseEntity<>(productService.getProductById(id), HttpStatus.OK);
    }

    @PutMapping("/{id}")
    public ResponseEntity<Product> updateProduct(
            @PathVariable Long id,
            @RequestBody Product product) {

        return new ResponseEntity<>(productService.updateProduct(id, product), HttpStatus.OK);
    }
    
    // Day 12 — by category
    @GetMapping("/category/{categoryName}")
    public ResponseEntity<List<Product>> getProductsByCategoryName(
            @PathVariable String categoryName) {

        List<Product> products =
                productService.getProductsByCategoryName(categoryName);

        return new ResponseEntity<>(products, HttpStatus.OK);
    }

    // Day 12 — by product name
    @GetMapping("/name/{name}")
    public ResponseEntity<?> getProductByName(@PathVariable String name) {

        Product product = productService.getProductByName(name);

        if (product == null) {
            return new ResponseEntity<>(
                "No products found with name: " + name,
                HttpStatus.NOT_FOUND
            );
        }
        return new ResponseEntity<>(product, HttpStatus.OK);
    }
    
}

