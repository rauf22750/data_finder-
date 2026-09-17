import {defineConfig} from 'vite';
import react from '@vitejs/plugin-react';
import {resolve} from 'path';

export default defineConfig({
  plugins:[react()],
  build:{
    outDir:resolve(__dirname,'../static/frontend'), emptyOutDir:true,
    rollupOptions:{output:{entryFileNames:'app.js',chunkFileNames:'chunks/[name].js',assetFileNames:asset=>asset.name?.endsWith('.css')?'app.css':'assets/[name][extname]'}}
  }
});
