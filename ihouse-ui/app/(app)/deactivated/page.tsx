import ForceLight from '../../../components/ForceLight';

export default function DeactivatedPage() {
  return (
    <div style={{ height: '100vh', display: 'flex', flexDirection: 'column', alignItems: 'center', justifyContent: 'center', textAlign: 'center', padding: 24, background: 'var(--color-surface, #fff)', color: 'var(--color-text, #171A1F)' }}>
      <ForceLight />
      <div style={{ marginBottom: 32 }}>
        <img src="/logo_domaniqo_dark.png" alt="Domaniqo" style={{ height: 48, filter: 'invert(1)' }} />
      </div>
      <div style={{ padding: 'var(--space-6)', background: 'rgba(248,81,73,0.05)', border: '1px solid rgba(248,81,73,0.2)', borderRadius: 'var(--radius-md)', maxWidth: 400, width: '100%' }}>
        <h1 style={{ fontSize: 'var(--text-lg)', fontWeight: 700, margin: '0 0 var(--space-4) 0', color: '#f85149' }}>Account Deactivated</h1>
        <p style={{ margin: 0, fontSize: 'var(--text-md)', lineHeight: 1.5, color: 'var(--color-text-dim)' }}>
          Domaniqo - You are deactivated.
          <br /><br />
          Talk with your admin or email <a href="mailto:info@domaniqo.com" style={{ color: 'var(--color-primary)' }}>info@domaniqo.com</a>
        </p>
      </div>
    </div>
  );
}
