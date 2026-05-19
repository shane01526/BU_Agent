/** @type {import('next').NextConfig} */
const nextConfig = {
  reactStrictMode: true,
  output: 'standalone',
  // 在 Docker on Windows 下 inotify 看不到 host 檔案改動 → 走 polling
  webpack: (config, { dev }) => {
    if (dev) {
      config.watchOptions = {
        poll: 800,
        aggregateTimeout: 200,
        ignored: ['**/node_modules', '**/.next'],
      };
    }
    return config;
  },
  async rewrites() {
    // Server-side proxy target：docker-compose 會注入 BACKEND_INTERNAL_URL=http://backend:8000；
    // host 開發（pnpm dev）則 fallback 到 localhost:8000
    const target = process.env.BACKEND_INTERNAL_URL || 'http://localhost:8000';
    return [
      {
        source: '/api/:path*',
        destination: `${target}/api/:path*`,
      },
    ];
  },
};

export default nextConfig;
