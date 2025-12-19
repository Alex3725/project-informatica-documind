import adapter from '@sveltejs/adapter-node';
import { vitePreprocess } from '@sveltejs/vite-plugin-svelte';

/** @type {import('@sveltejs/kit').Config} */
const config = {
  preprocess: vitePreprocess(),

  kit: {
    adapter: adapter({
      out: 'build',          // cartella di build
      precompress: false,
      env: {
        host: '0.0.0.0',     // necessario per Docker
        port: process.env.PORT || 5173
      }
    })
  }
};

export default config;
