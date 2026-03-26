export default function WorkerHeader({ title, subtitle }: { title: string; subtitle?: string }) {
    const today = new Date();
    const weekday = today.toLocaleDateString('en-US', { weekday: 'long' });
    const month = today.toLocaleDateString('en-US', { month: 'short' });
    const day = today.getDate();

    return (
        <div style={{ marginBottom: 'var(--space-5)' }}>
            <div style={{ 
                fontSize: 'var(--text-sm)', 
                fontWeight: 600, 
                color: 'var(--color-text-dim)', 
                textTransform: 'uppercase', 
                letterSpacing: '0.05em',
                display: 'flex',
                alignItems: 'baseline',
                gap: 6
            }}>
                <span>Today • {weekday}, {month}</span>
                <span style={{ 
                    fontSize: '1.4em', 
                    color: 'var(--color-text)', 
                    fontWeight: 800,
                    lineHeight: 1 
                }}>{day}</span>
            </div>
            <h1 style={{ 
                fontSize: '2rem', 
                fontWeight: 800, 
                color: 'var(--color-text)', 
                letterSpacing: '-0.03em', 
                marginTop: 4 
            }}>
                {title}
            </h1>
            {subtitle && (
                <p style={{ 
                    fontSize: 'var(--text-xs)', 
                    color: 'var(--color-text-dim)', 
                    marginTop: 2 
                }}>
                    {subtitle}
                </p>
            )}
        </div>
    );
}
