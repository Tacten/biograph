import { defineConfig } from "vite"
import vue from "@vitejs/plugin-vue"
import Icons from 'unplugin-icons/vite'
import Components from 'unplugin-vue-components/vite'
import IconsResolver from 'unplugin-icons/resolver'

export default defineConfig({
	base: "/assets/healthcare/dcmviewer/",
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
		outDir: "../public/dcmviewer",
		sourcemap: true,
		assetsDir: ".",
	},
	worker: {
		format: "es",
	},
})