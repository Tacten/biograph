<template>
	<div ref="viewport" class="w-[512px] h-[512px] bg-black mx-auto mt-10"></div>
</template>

<script setup>
import { ref, onMounted } from "vue"
import * as cornerstone from "@cornerstonejs/core"
import * as dicomParser from "dicom-parser"
import { wadors } from "@cornerstonejs/dicom-image-loader"

const viewport = ref(null)

const ALLOWED_SOP_CLASSES = [
	"1.2.840.10008.5.1.4.1.1.2",   // CT
	"1.2.840.10008.5.1.4.1.1.4",   // MR
	"1.2.840.10008.5.1.4.1.1.128", // PET
	"1.2.840.10008.5.1.4.1.1.1",   // CR
	"1.2.840.10008.5.1.4.1.1.6.1", // US
	"1.2.840.10008.5.1.4.1.1.2.1"  // Enhanced CT
]

function getQueryParams() {
	const params = new URLSearchParams(window.location.search)
	return {
		seriesUID: params.get("seriesUID"),
		qidoRoot: params.get("qidoRoot"),
		wadoRoot: params.get("wadoRoot")
	}
}

async function fetchInstanceMetadata({ qidoRoot, seriesUID }) {
	const url = `${qidoRoot}/instances?SeriesInstanceUID=${encodeURIComponent(seriesUID)}`
	const res = await fetch(url, {
		headers: {
			Accept: "application/dicom+json",
			Authorization: "Basic " + btoa("orthanc:orthanc"), // replace if using token
		}
	})
	if (!res.ok) throw new Error(`QIDO-RS fetch failed: ${res.status}`)
	return await res.json()
}

function buildImageIds(instances, seriesUID, wadoRoot) {
	return instances.map(instance => {
		const studyUID = instance["0020000D"]?.Value?.[0]
		const sopUID = instance["00080018"]?.Value?.[0]
		const sopClassUID = instance["00080016"]?.Value?.[0]

		if (!studyUID || !seriesUID || !sopUID || !sopClassUID) return null
		if (!ALLOWED_SOP_CLASSES.includes(sopClassUID)) return null

		return `wadors:${wadoRoot}/studies/${studyUID}/series/${seriesUID}/instances/${sopUID}/frames/1`
	}).filter(Boolean)
}

onMounted(async () => {
	const el = viewport.value
	if (!el) return

	const { seriesUID, qidoRoot, wadoRoot } = getQueryParams()
	if (!seriesUID || !qidoRoot || !wadoRoot) {
		alert("Missing required query params: seriesUID, qidoRoot, wadoRoot")
		return
	}

	try {
		// Init cornerstone
		cornerstone.init()
		wadors.external = {
			cornerstone,
			dicomParser
		}

		// Register wadors loader
		cornerstone.imageLoader.registerImageLoader("wadors", wadors.loadImage)

		// Get image metadata
		const instances = await fetchInstanceMetadata({ qidoRoot, seriesUID })
		const imageIds = buildImageIds(instances, seriesUID, wadoRoot)

		if (!imageIds.length) {
			alert("No viewable DICOM images found in this series.")
			return
		}

		// Setup rendering engine
		const renderingEngineId = "cornerstone-renderer"
		const viewportId = "dicom-viewport"
		const renderingEngine = new cornerstone.RenderingEngine(renderingEngineId)

		renderingEngine.enableElement({
			viewportId,
			element: el,
			type: cornerstone.Enums.ViewportType.STACK
		})

		const vp = renderingEngine.getViewport(viewportId)
		await vp.setStack({ imageIds, currentImageIdIndex: 0 })
		vp.render()

		console.log(`Rendered ${imageIds.length} image(s) for series ${seriesUID}`)
	} catch (err) {
		console.error("Viewer load error:", err)
		alert(`Viewer error: ${err.message}`)
	}
})
</script>
