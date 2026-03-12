# Domaniqo — Landing Page

**domaniqo.com**

Static landing page for Domaniqo — the deep operations platform for modern hospitality.

## Structure

```
domaniqo-site/
├── index.html              ← Main page
├── assets/
│   ├── css/
│   │   └── style.css       ← All styles
│   ├── js/
│   │   └── main.js         ← Splash animation + scroll reveal
│   └── images/
│       ├── favicon.svg      ← Browser tab icon
│       └── og-image.svg     ← Social sharing image
├── robots.txt               ← Search engine instructions
├── sitemap.xml              ← Sitemap for SEO
├── _redirects               ← Netlify routing
├── _headers                 ← Netlify security headers
├── vercel.json              ← Vercel configuration
└── README.md                ← This file
```

## Deploy

### Netlify
1. Drag the entire `domaniqo-site` folder to [app.netlify.com/drop](https://app.netlify.com/drop)
2. Or connect a Git repo and set publish directory to `/`

### Vercel
1. Run `vercel` in this directory
2. Or connect a Git repo — Vercel will auto-detect static site

### Any static host
Upload all files as-is. No build step required.

## Fonts

Loaded from Google Fonts:
- **Instrument Serif** — editorial headlines
- **Manrope** — UI and labels
- **Inter** — body text

## Contact

Early access requests go to: **info@domaniqo.com**
