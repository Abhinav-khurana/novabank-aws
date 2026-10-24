export default {
  build: {
    rollupOptions: {
      output: {
        entryFileNames: 'assets/app.js',
        chunkFileNames: 'assets/chunk-[name]-[hash].js',
        assetFileNames: asset => asset.names?.some(name => name.endsWith('.css'))
          ? 'assets/style.css'
          : 'assets/[name]-[hash][extname]'
      }
    }
  }
};
