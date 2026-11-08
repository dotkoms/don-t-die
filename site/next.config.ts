import type { NextConfig } from "next";

const nextConfig: NextConfig = {
  // The site reads the pipeline's Postgres through a read-only role.
  // Connection is server-side only; never expose it to the client.
};

export default nextConfig;
