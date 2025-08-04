import { defineConfig } from "vite"
import vue from "@vitejs/plugin-vue"
import Icons from 'unplugin-icons/vite'
import frappeui from "frappe-ui/vite"
import Components from 'unplugin-vue-components/vite'
import IconsResolver from 'unplugin-icons/resolver'

export default defineConfig({
	plugins: [
		vue(),
		Components({
			resolvers: [IconsResolver({ prefix: "" })],
		}),
		frappeui({
			frappeProxy: true,
			jinjaBootData: true,
			lucideIcons: true,
			buildConfig: {
				indexHtmlPath: "../healthcare/www/viewer.html",
				emptyOutDir: true,
				sourcemap: true,
			},
		}),
		Icons({
			compiler: "vue3",
		}),
	],
	build: {
		chunkSizeWarningLimit: 1500,
		outDir: "../healthcare/public/viewer",
		emptyOutDir: true,
		target: "es2015",
		sourcemap: true,
	},
	worker: {
		format: "es",
	},
})