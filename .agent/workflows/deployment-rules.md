---
description: Canonical Deployment Rules & Topology for iHouse Core
---

# 🚀 Deployment Rules & Truth

To avoid endless confusion about what code is running where, we follow these three strict rules for deployment across GitHub, Railway (Backend), and Vercel (Frontend).

## 1. 🐙 GitHub (Source of Truth)
**All code goes here first.**
- **Action:** `git push origin HEAD:checkpoint/supabase-single-write-20260305-1747`
- **Result:** Saves code to the remote repository. This is mandatory for version control.

## 2. 🚆 Railway (Backend)
**Auto-deploys via GitHub Push.**
- **Action:** None required beyond `git push` to the correct branch!
- **Result:** Railway listens to the `checkpoint/supabase-single-write-20260305-1747` branch on GitHub. The moment you push to GitHub, Railway automatically starts building the FastAPI backend.
- **Link:** `https://ihouse-core-production.up.railway.app`

## 3. 🔺 Vercel (Frontend UI)
**Manual CLI deploy ONLY (Does NOT auto-sync with GitHub).**
- **Action:** A `git push` does nothing for the UI! You must explicitly deploy via CLI.
- **Command:** 
  ```bash
  cd "/Users/clawadmin/Antigravity Proj/ihouse-core/ihouse-ui" && npx vercel --prod --yes
  ```
- **Result:** Pushes the local `ihouse-ui` code directly to `domaniqo-staging.vercel.app`.
- **Link:** `https://domaniqo-staging.vercel.app`

---

### 📝 Summary Cheat Sheet
- **Want to push a Python / Backend fix?**  
  → `git commit && git push` (Railway pulls it automatically).
- **Want to push a React / Frontend fix?**  
  → `git commit && git push` AND THEN run `npx vercel --prod --yes` inside `ihouse-ui`.
