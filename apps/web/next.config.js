/** @type {import('next').NextConfig} */
const nextConfig = {
  // output: 'standalone', // disabled on Windows dev (symlink permission issue)
  transpilePackages: ['@farmacia/shared-types'],
};

module.exports = nextConfig;
