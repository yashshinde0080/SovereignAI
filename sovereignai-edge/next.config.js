/** @type {import('next').NextConfig} */
const nextConfig = {
  images: {
    unoptimized: true, // For static export if needed
  },
  // Optimize for production
  compiler: {
    removeConsole: process.env.NODE_ENV === 'production',
  },
}

module.exports = nextConfig