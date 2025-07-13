import { defineConfig } from "vite"
import vue from "@vitejs/plugin-vue"
import Icons from 'unplugin-icons/vite'
import Components from 'unplugin-vue-components/vite'
import IconsResolver from 'unplugin-icons/resolver'

export default defineConfig({
    plugins: [
        vue(),
        Components({
            resolvers: [IconsResolver({ prefix: "" })],
        }),
        Icons({
            compiler: "vue3",
        }),
    ],
    build: {
        outDir: "../healthcare/public/dcmviewer",
        sourcemap: true,
    },
    worker: {
        format: "es",
    },
    server: {
        port: 5173,
    },
})