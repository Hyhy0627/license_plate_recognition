import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  distDir: process.env.NEXT_DIST_DIR || ".next",
  typescript: { tsconfigPath: process.env.NEXT_DIST_DIR ? "tsconfig.benchmark.json" : "tsconfig.json" },
  cacheComponents: true,
  devIndicators: false,
  partialPrefetching: true,
};

export default nextConfig;
