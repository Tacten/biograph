<template>
	<div class="w-full h-full bg-red">
		<div ref="viewportRef" class="w-[512px] h-[512px] bg-red" tabindex="-1" data-viewport-uid="dicomViewport"
			data-rendering-engine-uid="dicomRenderingEngine"></div>
	</div>
</template>

<script setup>
import { ref, onMounted } from "vue"
import * as cornerstone from "@cornerstonejs/core"
import { RenderingEngine, Enums } from "@cornerstonejs/core"
// import { init as initDicomImageLoader } from "@cornerstonejs/dicom-image-loader"

// Initialize the image loader
// initDicomImageLoader()

const viewportRef = ref(null)
const renderingEngineId = "dicomRenderingEngine"
const viewportId = "dicomViewport"

onMounted(async () => {

	try {
		await cornerstone.init()
		const element = viewportRef.value
		if (!element) throw new Error("Viewport element not found")

		const renderingEngine = new RenderingEngine(renderingEngineId)
		renderingEngine.enableElement({
			viewportId,
			element,
			type: Enums.ViewportType.STACK,
		})

		const viewPort = renderingEngine.getViewport(viewportId)

		const studyUID = "1.2.826.0.1.3680043.10.43.1754538150"
		const seriesUID = "1.2.826.0.1.3680043.8.498.17825687713634590686490321075298115373"
		const objectUID = ["1.2.826.0.1.3680043.8.498.87870675210578450241247951451749611712", "1.2.826.0.1.3680043.8.498.98327856056778592685211212009986357439"]
		let imageIds = []

		objectUID.forEach(o =>{
			// const imageId = `wadori:http://localhost:8080/wado?requestType=WADO&studyUID=${studyUID}&seriesUID=${seriesUID}&objectUID=${o}`
			// const imageId = `wadors:http://localhost:8080/dicom-web/studies=${studyUID}&series=${seriesUID}&instances=${o}`
			// const imageId = `wadors://localhost:8080/dicom-web/studies/${studyUID}/series/${seriesUID}/instances/${o}/frames/1`
			const imageId = `wadors:http://localhost:8080/dicom-web/studies/${studyUID}/series/${seriesUID}/instances/${o}`
			// const imageId = `wadors://localhost:8080/${studyUID}/${seriesUID}/${o}`
			imageIds.push(imageId)
		})
		// const imageIds = [
		// 	"wadouri:https://raw.githubusercontent.com/cornerstonejs/cornerstone-wado-image-loader/main/examples/images/CTImage.dcm"
		// ]

		console.log("imageIds:", imageIds)

		if (!Array.isArray(imageIds) || imageIds.length === 0) {
			throw new Error("imageIds must be a non-empty array of strings")
		}
		await viewPort.setStack(imageIds)
		await viewPort.render()
		console.log("Rendered!")
	} catch (e) {
		console.error("Viewer load error:", e)
	}
})
</script>
