'use client';

/**
 * Phase 860 — Domaniqo Terms of Use Page
 *
 * Legal page with Domaniqo branding.
 * Self-contained nav and footer (light theme).
 */

const CSS_CONTENT = `@import url('https://fonts.googleapis.com/css2?family=Instrument+Serif:ital@0;1&family=Inter:wght@300;400;500;600&family=Manrope:wght@400;500;600;700&display=swap');
:root {
  --midnight: #171A1F; --stone: #EAE5DE; --sand: #D6C8B7;
  --cloud: #F8F6F2; --copper: #B56E45; --moss: #334036;
  --olive: #6B7258; --sage: #8FA39B;
  --font-brand: 'Manrope', sans-serif;
  --font-body: 'Inter', sans-serif;
  --font-editorial: 'Instrument Serif', Georgia, serif;
  --radius: 10px;
}
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
html { -webkit-font-smoothing: antialiased; -moz-osx-font-smoothing: grayscale; }
body { font-family: var(--font-body); color: var(--midnight); background: var(--cloud); }
a { color: var(--copper); text-decoration: none; transition: opacity 0.2s; }
a:hover { opacity: 0.7; }

.nav {
  position: sticky; top: 0; z-index: 100; padding: 0 40px; height: 72px;
  display: flex; align-items: center; justify-content: space-between;
  background: rgba(248,246,242,0.9); backdrop-filter: blur(20px);
  border-bottom: 1px solid rgba(23,26,31,0.06);
}
.nav-logo { display: flex; align-items: center; gap: 12px; text-decoration: none; color: var(--midnight); }
.nav-logo svg { width: 28px; height: 28px; }
.nav-logo span { font-family: var(--font-editorial); font-size: 20px; letter-spacing: 0.5px; }
.nav-back { font-family: var(--font-brand); font-size: 13px; font-weight: 500; color: var(--midnight); opacity: 0.5; transition: opacity 0.2s; }
.nav-back:hover { opacity: 1; }

.legal-hero {
  padding: 80px 24px 48px; text-align: center;
  border-bottom: 1px solid rgba(23,26,31,0.06);
}
.legal-hero h1 { font-family: var(--font-editorial); font-size: clamp(32px, 5vw, 48px); font-weight: 400; letter-spacing: -0.5px; margin-bottom: 12px; }
.legal-hero .date { font-family: var(--font-brand); font-size: 13px; font-weight: 500; color: var(--midnight); opacity: 0.35; letter-spacing: 0.5px; }

.legal-body { max-width: 720px; margin: 0 auto; padding: 56px 24px 120px; }
.legal-intro { font-size: 16px; line-height: 1.75; font-weight: 300; opacity: 0.65; margin-bottom: 48px; padding-bottom: 40px; border-bottom: 1px solid rgba(23,26,31,0.06); }
.legal-section { margin-bottom: 40px; }
.legal-section h2 { font-family: var(--font-brand); font-size: 15px; font-weight: 600; letter-spacing: 0.3px; margin-bottom: 14px; color: var(--midnight); }
.legal-section p { font-size: 15px; line-height: 1.75; font-weight: 300; opacity: 0.6; margin-bottom: 12px; }
.legal-section ul { list-style: none; padding: 0; margin-bottom: 12px; }
.legal-section ul li { font-size: 15px; line-height: 1.75; font-weight: 300; opacity: 0.6; padding-left: 20px; position: relative; margin-bottom: 4px; }
.legal-section ul li::before { content: ''; position: absolute; left: 0; top: 11px; width: 5px; height: 5px; border-radius: 50%; background: var(--copper); opacity: 0.4; }
.legal-contact { margin-top: 56px; padding-top: 40px; border-top: 1px solid rgba(23,26,31,0.06); }
.legal-contact p { font-size: 15px; line-height: 1.75; font-weight: 300; opacity: 0.6; }

.footer { padding: 48px 24px; background: var(--midnight); color: var(--stone); text-align: center; }
.footer-inner { max-width: 720px; margin: 0 auto; display: flex; align-items: center; justify-content: space-between; flex-wrap: wrap; gap: 16px; }
.footer-copy { font-size: 12px; opacity: 0.3; font-weight: 300; }
.footer-links { display: flex; gap: 24px; }
.footer-links a { font-family: var(--font-brand); font-size: 12px; color: var(--stone); opacity: 0.35; transition: opacity 0.2s; }
.footer-links a:hover { opacity: 0.7; }
.footer-tagline { font-family: var(--font-editorial); font-style: italic; font-size: 12px; opacity: 0.2; width: 100%; margin-top: 16px; }

@media (max-width: 768px) {
  .nav { padding: 0 20px; height: 60px; }
  .footer-inner { flex-direction: column; align-items: center; }
}`;
const HTML_CONTENT = `<nav class="nav">
  <a href="/" class="nav-logo">
    <svg viewBox="0 0 64 64" fill="none">
      <path d="M16 6H28C46 6 58 18 58 32C58 46 46 58 28 58H16Z" stroke="#B56E45" stroke-width="2.2" stroke-linejoin="round" fill="none"/>
      <line x1="28" y1="6" x2="28" y2="58" stroke="#B56E45" stroke-width="1.2"/>
      <line x1="16" y1="32" x2="52" y2="32" stroke="#B56E45" stroke-width="1.2"/>
      <path d="M28 13C40 13 51 22 51 32C51 42 40 51 28 51" stroke="#B56E45" stroke-width="1.08" fill="none"/>
    </svg>
    <span>Domaniqo</span>
  </a>
  <a href="/" class="nav-back">← Back to home</a>
</nav>

<div class="legal-hero">
  <h1>Terms of Use</h1>
  <div class="date">Last updated: March 19, 2026</div>
</div>

<div class="legal-body">
  <p class="legal-intro">These Terms of Use govern access to and use of the Domaniqo website, platform, and related services. By using Domaniqo, you agree to these Terms.</p>

  <div class="legal-section">
    <h2>1. Use of the Service</h2>
    <p>Domaniqo provides software and operational tools for property and hospitality management. You agree to use the service only for lawful business purposes.</p>
  </div>

  <div class="legal-section">
    <h2>2. Accounts</h2>
    <p>You are responsible for maintaining the confidentiality of your account credentials and for all activity under your account.</p>
  </div>

  <div class="legal-section">
    <h2>3. Customer Data</h2>
    <p>You retain responsibility for the accuracy, legality, and integrity of the data you enter into the platform, including booking data, staff data, guest data, and property data.</p>
  </div>

  <div class="legal-section">
    <h2>4. Acceptable Use</h2>
    <p>You must not:</p>
    <ul>
      <li>Use the platform for unlawful, fraudulent, or abusive purposes</li>
      <li>Attempt to gain unauthorized access to accounts, systems, or data</li>
      <li>Interfere with platform operation, security, or performance</li>
      <li>Upload malicious code, harmful content, or unauthorized materials</li>
    </ul>
  </div>

  <div class="legal-section">
    <h2>5. Integrations and Third-Party Services</h2>
    <p>Some features may depend on third-party services such as messaging platforms, calendar feeds, booking channels, maps, or hosting providers. Domaniqo is not responsible for third-party outages or policy changes.</p>
  </div>

  <div class="legal-section">
    <h2>6. Availability</h2>
    <p>We aim to provide a reliable service, but we do not guarantee uninterrupted or error-free availability at all times.</p>
  </div>

  <div class="legal-section">
    <h2>7. Intellectual Property</h2>
    <p>All software, branding, design, and platform materials related to Domaniqo remain the property of Domaniqo or its licensors, unless stated otherwise.</p>
  </div>

  <div class="legal-section">
    <h2>8. Limitation of Liability</h2>
    <p>To the maximum extent permitted by law, Domaniqo is provided on an as-is and as-available basis. Domaniqo shall not be liable for indirect, incidental, special, consequential, or business-interruption damages.</p>
  </div>

  <div class="legal-section">
    <h2>9. Termination</h2>
    <p>We may suspend or terminate access if these Terms are violated, if required by law, or if necessary to protect the platform or other users.</p>
  </div>

  <div class="legal-section">
    <h2>10. Changes to the Terms</h2>
    <p>We may update these Terms from time to time. The updated version will be posted on this page with a revised date.</p>
  </div>

  <div class="legal-section">
    <h2>11. Governing Principles</h2>
    <p>These Terms are intended to be interpreted in a commercially reasonable manner consistent with applicable law and the legitimate operation of the service.</p>
  </div>

  <div class="legal-contact">
    <h2>12. Contact</h2>
    <p>For questions regarding these Terms, contact us at <a href="mailto:hello@domaniqo.com">hello@domaniqo.com</a></p>
  </div>
</div>

<footer class="footer">
  <div class="footer-inner">
    <div class="footer-copy">© 2026 Domaniqo</div>
    <div class="footer-links">
      <a href="/privacy">Privacy Policy</a>
      <a href="/terms">Terms of Use</a>
      <a href="mailto:hello@domaniqo.com">Contact</a>
    </div>
    <div class="footer-tagline">Calm command for modern hospitality.</div>
  </div>
</footer>`;

export default function TermsofUsePage() {
  return (
    <>
      <style dangerouslySetInnerHTML={{ __html: CSS_CONTENT }} />
      <div dangerouslySetInnerHTML={{ __html: HTML_CONTENT }} />
    </>
  );
}
