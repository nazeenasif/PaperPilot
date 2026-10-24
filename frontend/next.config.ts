import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  reactStrictMode: true,
  // The browser talks to the API directly (no proxy: it can buffer event streams, research R11).
  poweredByHeader: false,
};

export default nextConfig;
