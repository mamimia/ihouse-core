/**
 * Phase 525 — Admin Layout
 * 
 * Wraps all /admin/* pages with the AdminNav sub-navigation.
 */

import AdminNav from '../../../components/AdminNav';

export default function AdminLayout({ children }: { children: React.ReactNode }) {
    return (
        <div style={{ width: '100%' }}>
            <AdminNav />
            {children}
        </div>
    );
}
