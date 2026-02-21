import { defineConfig, type Plugin } from 'vite'
import react from '@vitejs/plugin-react'
import fs from 'node:fs'
import path from 'node:path'

const NOTES_DIR = path.resolve(__dirname, '../.obnotes')

function notesPlugin(): Plugin {
  return {
    name: 'notes-api',
    configureServer(server) {
      server.middlewares.use((req, res, next) => {
        if (req.url === '/api/notes') {
          const realDir = fs.realpathSync(NOTES_DIR)
          const files = fs.readdirSync(realDir)
            .filter(f => f.endsWith('.md'))
            .sort()
            .map(f => f.replace(/\.md$/, ''))
          res.setHeader('Content-Type', 'application/json')
          res.end(JSON.stringify(files))
          return
        }

        const match = req.url?.match(/^\/api\/notes\/(.+)$/)
        if (match) {
          const name = decodeURIComponent(match[1])
          const realDir = fs.realpathSync(NOTES_DIR)
          const filePath = path.join(realDir, `${name}.md`)
          if (fs.existsSync(filePath)) {
            res.setHeader('Content-Type', 'text/plain; charset=utf-8')
            res.end(fs.readFileSync(filePath, 'utf-8'))
            return
          }
          res.statusCode = 404
          res.end('Not found')
          return
        }

        next()
      })
    },
  }
}

export default defineConfig({
  plugins: [react(), notesPlugin()],
  build: {
    lib: {
      entry: 'src/index.ts',
      name: 'artdig',
      fileName: () => 'artdig.js',
      formats: ['iife'],
    },
    cssCodeSplit: false,
    rollupOptions: {
      output: {
        extend: true,
        assetFileNames: '[name][extname]',
      },
    },
  },
})
