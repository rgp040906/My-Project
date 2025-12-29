
package com.examly.springapp.service;

import java.util.List;

import org.springframework.data.domain.Page;
import com.examly.springapp.model.Category;

public interface CategoryService {

    // CRUD methods
    Category addCategory(Category category);

    List<Category> getAllCategories();

    Category getCategoryById(Integer id);

    Category updateCategory(Integer id, Category category);

    // Pagination
    Page<Category> getPaginatedCategories(int page, int size);
}
