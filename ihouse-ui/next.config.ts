import type { NextConfig } from "next";
import path from "path";

const nextConfig: NextConfig = {
  output: "standalone",
  turbopack: {
    // Phase 859: Constrain file watcher to ihouse-ui only.
    // Without this, Next.js detected multiple package-lock.json files
    // and set root to /Users/clawadmin, causing constant HMR loops.
    root: path.resolve(__dirname),
  },
};

export default nextConfig;
