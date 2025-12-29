

package com.examly.springapp.service;

import java.util.List;
import java.util.Optional;

import org.springframework.beans.factory.annotation.Autowired;
import org.springframework.data.domain.Page;
import org.springframework.data.domain.PageRequest;
import org.springframework.data.domain.Pageable;
import org.springframework.stereotype.Service;

import com.examly.springapp.model.Category;
import com.examly.springapp.repository.CategoryRepo;

@Service
public class CategoryServiceImpl implements CategoryService {

    @Autowired
    private CategoryRepo categoryRepo;

    @Override
    public Category addCategory(Category category) {
        return categoryRepo.save(category);
    }

    @Override
    public List<Category> getAllCategories() {
        return categoryRepo.findAll();
    }

    @Override
    public Category getCategoryById(Integer id) {
        Optional<Category> category = categoryRepo.findById(id);
        return category.orElse(null);
    }

    @Override
    public Category updateCategory(Integer id, Category category) {
        Optional<Category> existing = categoryRepo.findById(id);
        if (existing.isPresent()) {
            Category c = existing.get();
            c.setName(category.getName());
            return categoryRepo.save(c);
        } else {
            return null;
        }
    }

    @Override
    public Page<Category> getPaginatedCategories(int page, int size) {
        Pageable pageable = PageRequest.of(page, size);
        return categoryRepo.findAll(pageable);
    }

   
}
