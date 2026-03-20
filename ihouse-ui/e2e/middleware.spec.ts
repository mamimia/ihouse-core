import { test, expect } from '@playwright/test';

// ---------------------------------------------------------------------------
// Helpers to forge a JWT cookie for middleware checking
// Middleware uses atob() on the payload (the middle part). It does NOT verify signature.
// ---------------------------------------------------------------------------

function makeFakeJwt(payload: Record<string, unknown>): string {
    const header = Buffer.from(JSON.stringify({ alg: 'HS256', typ: 'JWT' })).toString('base64url');
    const body = Buffer.from(JSON.stringify(payload)).toString('base64url');
    // The signature doesn't matter for `middleware.ts`
    return `${header}.${body}.fake_signature_for_testing`;
}

async function setAuthCookie(context: any, payload: Record<string, unknown>) {
    await context.addCookies([
        {
            name: 'ihouse_token',
            value: makeFakeJwt(payload),
            domain: 'localhost',
            path: '/',
            httpOnly: false, // does not matter
            secure: false,
        }
    ]);
}

test.describe('Route Guards & Middleware Role Restrictions', () => {

    test('Unauthenticated user is redirected to /login', async ({ page }) => {
        // No cookie set
        await page.goto('/dashboard');
        await expect(page).toHaveURL(/.*\/login\?from=%2Fdashboard/);
    });

    test('Deactivated user is redirected to /deactivated', async ({ page, context }) => {
        await setAuthCookie(context, { role: 'admin', is_active: false });
        await page.goto('/dashboard');
        await expect(page).toHaveURL(/\/deactivated$/);
        
        // Allowed to stay on deactivated
        await page.goto('/deactivated');
        await expect(page).toHaveURL(/\/deactivated$/);
    });

    test('Active user on /deactivated is redirected to /dashboard', async ({ page, context }) => {
        await setAuthCookie(context, { role: 'admin', is_active: true });
        await page.goto('/deactivated');
        await expect(page).toHaveURL(/\/dashboard$/);
    });

    test('Forced reset user is redirected to /update-password', async ({ page, context }) => {
        await setAuthCookie(context, { role: 'admin', is_active: true, force_reset: true });
        await page.goto('/dashboard');
        await expect(page).toHaveURL(/\/update-password$/);
        
        // Allowed to stay on update password
        await page.goto('/update-password');
        await expect(page).toHaveURL(/\/update-password$/);
    });

    test('Normal user on /update-password is redirected to /dashboard', async ({ page, context }) => {
        await setAuthCookie(context, { role: 'admin', is_active: true, force_reset: false });
        await page.goto('/update-password');
        await expect(page).toHaveURL(/\/dashboard$/);
    });

    test('Admin role has access everywhere', async ({ page, context }) => {
        await setAuthCookie(context, { role: 'admin' });
        
        // Need to capture the response because 404 means it tried to render the page, meaning middleware allowed it. 
        // If it redirects, the URL changes.
        
        await page.goto('/dashboard');
        expect(page.url()).toContain('/dashboard');
        
        await page.goto('/ops');
        expect(page.url()).toContain('/ops');
        
        await page.goto('/owner');
        expect(page.url()).toContain('/owner');
    });

    test('Owner role is restricted correctly', async ({ page, context }) => {
        await setAuthCookie(context, { role: 'owner' });
        
        // Allowed
        await page.goto('/dashboard');
        expect(page.url()).toContain('/dashboard');
        
        await page.goto('/owner');
        expect(page.url()).toContain('/owner');
        
        // Blocked - redirected to /owner
        await page.goto('/ops');
        await expect(page).toHaveURL(/\/owner$/);
    });

    test('Cleaner role is restricted correctly', async ({ page, context }) => {
        await setAuthCookie(context, { role: 'cleaner' });
        
        // Allowed
        await page.goto('/worker');
        expect(page.url()).toContain('/worker');
        
        await page.goto('/ops');
        expect(page.url()).toContain('/ops');
        
        // Blocked - redirected to /worker (the first element in cleaner's allowedPrefixes)
        await page.goto('/dashboard');
        await expect(page).toHaveURL(/\/worker$/);
    });

    test('Checkin role is restricted correctly', async ({ page, context }) => {
        await setAuthCookie(context, { role: 'checkin' });
        
        // Allowed
        await page.goto('/checkin');
        // Actually goes to /ops/checkin
        expect(page.url()).toContain('/ops/checkin');
        
        // Blocked - redirected to /checkin (which redirects to /ops/checkin)
        await page.goto('/worker');
        await expect(page).toHaveURL(/.*\/ops\/checkin/);
    });

    test('Ops role is restricted correctly', async ({ page, context }) => {
        await setAuthCookie(context, { role: 'ops' });
        
        // Allowed
        await page.goto('/ops');
        expect(page.url()).toContain('/ops');
        
        await page.goto('/dashboard');
        expect(page.url()).toContain('/dashboard');
        
        // Blocked - redirected to /ops
        await page.goto('/owner');
        await expect(page).toHaveURL(/\/ops$/);
    });

    test('Maintenance role is restricted correctly', async ({ page, context }) => {
        await setAuthCookie(context, { role: 'maintenance' });
        
        // Allowed
        await page.goto('/maintenance');
        expect(page.url()).toContain('/maintenance');
        
        await page.goto('/worker');
        expect(page.url()).toContain('/worker');
        
        // Blocked - redirected to /maintenance
        await page.goto('/ops');
        await expect(page).toHaveURL(/\/maintenance$/);
    });

});
