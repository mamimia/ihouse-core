---
description: Deploy frontend to Vercel staging when a frontend batch is ready for review
---

# Vercel Staging Deploy

## Context
- The `domaniqo-staging` Vercel project is **CLI-only** (no GitHub integration).
- `git push` does **NOT** update `domaniqo-staging.vercel.app`.
- Development happens on `checkpoint/supabase-single-write-20260305-1747`.
- Railway backend auto-deploys from pushes to the checkpoint branch.
- Vercel frontend requires explicit CLI deployment.

## When to Deploy
- When a **frontend batch** (UI, routing, middleware, i18n, public pages) is coherent and ready for human staging review.
- Do **NOT** deploy on every tiny push.
- Do **NOT** deploy if the batch is backend-only.

## Steps

1. Commit and push to the checkpoint branch as normal.

2. Verify the build passes:
```
cd "/Users/clawadmin/Antigravity Proj/ihouse-core/ihouse-ui" && npx next build
```

// turbo
3. Deploy to Vercel production alias:
```
cd "/Users/clawadmin/Antigravity Proj/ihouse-core/ihouse-ui" && npx vercel --prod --yes
```

4. Report back with:
   - Commit deployed (from `git log -1 --oneline`)
   - Deployment success (exit code 0)
   - Confirmation that `domaniqo-staging.vercel.app` reflects the new code

## Verification
After deploy, confirm the key changed routes/pages return expected HTTP status:
```
curl -sI "https://domaniqo-staging.vercel.app/<changed-route>" | grep "HTTP"
```

## Live URLs
- **Frontend staging:** https://domaniqo-staging.vercel.app
- **Backend staging:** https://ihouse-core-production.up.railway.app
