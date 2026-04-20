import tailwindcss from '@tailwindcss/vite';
import react from '@vitejs/plugin-react';
import path from 'path';
import {defineConfig, loadEnv} from 'vite';

export default defineConfig(({mode}) => {
  const env = loadEnv(mode, '.', '');
  return {
    plugins: [react(), tailwindcss()],
    define: {
      // OpenAI key — 팀원용 (VITE_ 미접두 변수는 직접 define 필요)
      'process.env.OPENAI_API_KEY': JSON.stringify(env.OPENAI_API_KEY || ''),
      // VITE_GOOGLE_API_KEY / VITE_BACKEND_URL 은 VITE_ 접두 덕분에 자동 노출
    },
    resolve: {
      alias: {
        '@': path.resolve(__dirname, './src'),
      },
    },
    server: {
      // HMR is disabled in AI Studio via DISABLE_HMR env var.
      // Do not modifyâfile watching is disabled to prevent flickering during agent edits.
      hmr: process.env.DISABLE_HMR !== 'true',
    },
  };
});
