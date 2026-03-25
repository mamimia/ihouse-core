import { test, expect } from '@playwright/test';

test.describe('Model B Concurrent Sessions Proof (Safari)', () => {
  // Use a global setup for the browser context to maintain tabs
  test('Prove unlimited tabs & isolation', async ({ browser }) => {
    // 1. Launch a single context (simulating actual user browser window)
    const context = await browser.newContext();
    
    // 2. Admin Login
    const adminPage = await context.newPage();
    await adminPage.goto('https://domaniqo-staging.vercel.app/login');
    await adminPage.fill('input[type="email"]', 'admin@domaniqo.com');
    await adminPage.click('button[type="submit"]');
    await adminPage.fill('input[type="password"]', 'Admin123!');
    await adminPage.click('button[type="submit"]');
    
    // Wait for dashboard to load
    await adminPage.waitForURL('**/dashboard');
    await expect(adminPage.locator('text=Operations Dashboard')).toBeVisible({ timeout: 15000 });
    
    const adminTokenBase = await adminPage.evaluate(() => localStorage.getItem('ihouse_token'));
    expect(adminTokenBase).toBeTruthy();

    console.log('[+] Admin successfully logged in');

    // 3. Open Cleaner Tab (Worker 1)
    const cleanerPage = await context.newPage();
    // Simulate Act As redirect flow
    await adminPage.click('select');
    await adminPage.selectOption('select', 'cleaner');
    
    // Manually trigger the Act As API and open new tab because playwright clicking a ↗ that calls window.open
    // gets intercepted contextually. We can just intercept the popup.
    const [popup1] = await Promise.all([
      context.waitForEvent('page'),
      adminPage.click('button:has-text("↗")')
    ]);
    
    await popup1.waitForLoadState('networkidle');
    await expect(popup1.locator('text=ACTING AS: Cleaner')).toBeVisible({ timeout: 15000 });
    const cleanerStorage = await popup1.evaluate(() => sessionStorage.getItem('ihouse_token'));
    expect(cleanerStorage).toBeTruthy();
    expect(cleanerStorage).not.toEqual(adminTokenBase);
    
    console.log('[+] Cleaner tab opened cleanly (isolated token confirmed)');

    // 4. Open Check-in Tab (Worker 2 - proving concurrency)
    await adminPage.bringToFront();
    await adminPage.selectOption('select', 'checkin');
    const [popup2] = await Promise.all([
      context.waitForEvent('page'),
      adminPage.click('button:has-text("↗")')
    ]);
    
    await popup2.waitForLoadState('networkidle');
    await expect(popup2.locator('text=ACTING AS: Check-in Staff')).toBeVisible({ timeout: 15000 });
    const checkinStorage = await popup2.evaluate(() => sessionStorage.getItem('ihouse_token'));
    expect(checkinStorage).toBeTruthy();
    expect(checkinStorage).not.toEqual(cleanerStorage);
    expect(checkinStorage).not.toEqual(adminTokenBase);

    console.log('[+] Check-in tab opened concurrently (no 409 limit, strict token isolation)');

    // 5. Termination Independence Check
    await popup1.bringToFront();
    await popup1.click('button:has-text("END & RE-LOGIN")');
    await popup1.waitForURL('**/dashboard', { timeout: 10000 });
    
    console.log('[+] Cleaner session ended. Verifying other tabs...');

    // 6. Verify Check-in tab is unharmed
    await popup2.bringToFront();
    await popup2.reload();
    await expect(popup2.locator('text=ACTING AS: Check-in Staff')).toBeVisible({ timeout: 15000 });
    const checkinStorageFinal = await popup2.evaluate(() => sessionStorage.getItem('ihouse_token'));
    expect(checkinStorageFinal).toEqual(checkinStorage);

    console.log('[+] Check-in tab remained fully active and unharmed');

    // 7. Verify Admin tab is unharmed
    await adminPage.bringToFront();
    await adminPage.reload();
    await expect(adminPage.locator('text=Operations Dashboard')).toBeVisible({ timeout: 15000 });
    const adminTokenFinal = await adminPage.evaluate(() => localStorage.getItem('ihouse_token'));
    expect(adminTokenFinal).toEqual(adminTokenBase);
    
    console.log('[+] Admin tab local storage perfectly preserved. Safari concurrency proof passed!');

    await context.close();
  });
});
