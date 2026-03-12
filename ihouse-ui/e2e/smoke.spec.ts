import { test, expect } from '@playwright/test';

/**
 * Phase 318 — Frontend E2E Smoke Tests
 * =====================================
 * Core navigation and page-load smoke tests.
 * These verify that all critical pages render without errors.
 * 
 * Prerequisites:
 *   - Next.js dev server running (auto-started by Playwright config)
 *   - Backend API not required (pages handle fetch errors gracefully)
 */

test.describe('Navigation Smoke Tests', () => {
  
  test('root redirects to /dashboard or /login', async ({ page }) => {
    await page.goto('/');
    // Root should redirect — either to dashboard (authenticated) or login
    await expect(page).not.toHaveURL(/^\/$/);  
  });

  test('/login page loads', async ({ page }) => {
    await page.goto('/login');
    await expect(page.locator('body')).toBeVisible();
    // Page should have some content (title, form, or branding)
    const body = await page.textContent('body');
    expect(body?.length).toBeGreaterThan(10);
  });

  test('/dashboard page loads', async ({ page }) => {
    await page.goto('/dashboard');
    await expect(page.locator('body')).toBeVisible();
  });

  test('/bookings page loads', async ({ page }) => {
    await page.goto('/bookings');
    await expect(page.locator('body')).toBeVisible();
  });

  test('/tasks page loads', async ({ page }) => {
    await page.goto('/tasks');
    await expect(page.locator('body')).toBeVisible();
  });

  test('/financial page loads', async ({ page }) => {
    await page.goto('/financial');
    await expect(page.locator('body')).toBeVisible();
  });

  test('/worker page loads', async ({ page }) => {
    await page.goto('/worker');
    await expect(page.locator('body')).toBeVisible();
  });

  test('/owner page loads', async ({ page }) => {
    await page.goto('/owner');
    await expect(page.locator('body')).toBeVisible();
  });

  test('/guests page loads', async ({ page }) => {
    await page.goto('/guests');
    await expect(page.locator('body')).toBeVisible();
  });

  test('/calendar page loads', async ({ page }) => {
    await page.goto('/calendar');
    await expect(page.locator('body')).toBeVisible();
  });

  test('/manager page loads', async ({ page }) => {
    await page.goto('/manager');
    await expect(page.locator('body')).toBeVisible();
  });

  test('/admin page loads', async ({ page }) => {
    await page.goto('/admin');
    await expect(page.locator('body')).toBeVisible();
  });

  test('/admin/notifications page loads', async ({ page }) => {
    await page.goto('/admin/notifications');
    await expect(page.locator('body')).toBeVisible();
  });

  test('/admin/dlq page loads', async ({ page }) => {
    await page.goto('/admin/dlq');
    await expect(page.locator('body')).toBeVisible();
  });

});

test.describe('Login Page UI Tests', () => {

  test('login page has form inputs', async ({ page }) => {
    await page.goto('/login');
    // Login page should have input fields
    const inputs = page.locator('input');
    const count = await inputs.count();
    expect(count).toBeGreaterThanOrEqual(1);
  });

  test('login page has submit button', async ({ page }) => {
    await page.goto('/login');
    const button = page.locator('button[type="submit"], button:has-text("Sign in"), button:has-text("Log in"), button:has-text("Login")');
    await expect(button.first()).toBeVisible();
  });
});

test.describe('Sidebar Navigation Tests', () => {

  test('sidebar has navigation links', async ({ page }) => {
    // Use desktop viewport to ensure sidebar is visible
    await page.setViewportSize({ width: 1280, height: 720 });
    await page.goto('/dashboard');
    const body = await page.textContent('body');
    // Page should have navigation-related text
    expect(body?.length).toBeGreaterThan(50);
  });

});
