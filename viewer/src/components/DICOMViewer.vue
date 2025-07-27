<template>
	<div ref="viewport" class="w-[512px] h-[512px] bg-black"></div>
</template>

<script setup>
import { ref, onMounted } from "vue"
import * as cornerstone from "@cornerstonejs/core"
import * as dicomParser from "dicom-parser"
import { wadouri } from "@cornerstonejs/dicom-image-loader"

const viewport = ref(null)

function getQueryParams() {
	const params = new URLSearchParams(window.location.search)
	return {
		studyUID: params.get("studyUID"),
		seriesUID: params.get("seriesUID"),
		sopUID: params.get("sopUID"),
		qidoRoot: params.get("qidoRoot"),
		wadoRoot: params.get("wadoRoot"),
	}
}

async function fetchInstanceMetadata({ qidoRoot, seriesUID }) {
	// const url = `${qidoRoot}/instances?SeriesInstanceUID=${seriesUID}`
	const url = `/dicom-proxy/instances?SeriesInstanceUID=${seriesUID}`
	const res = await fetch(url, {
		headers: {
			Accept: "application/dicom+json",
			// Authorization: "Basic " + btoa("orthanc:orthanc"),
		},
	})
	if (!res.ok) throw new Error("QIDO-RS fetch failed")
	return await res.json()
}

function buildImageIds(instances, wadoRoot) {
	const allowedSOPs = [
		"1.2.840.10008.5.1.4.1.1.2",     // CT Image Storage
		"1.2.840.10008.5.1.4.1.1.4",     // MR Image Storage
		"1.2.840.10008.5.1.4.1.1.128",   // PET Image Storage
		"1.2.840.10008.5.1.4.1.1.1",     // CR Image Storage
		"1.2.840.10008.5.1.4.1.1.6.1",   // Ultrasound Image Storage
		"1.2.840.10008.5.1.4.1.1.2.1",     // Enhanced CT Image Storage
	]
	console.log("instances: ", instances)
	instances.forEach((instance, i) => {
		const sopClassUID = instance["00080016"]?.Value?.[0]
		console.log(`Instance #${i}: SOP Class UID =`, sopClassUID)
	})


	return instances
		.map((instance, i) => {
			const studyUID = instance["0020000D"]?.Value?.[0];
			const seriesUID = instance["0020000E"]?.Value?.[0];
			const sopUID = instance["00080018"]?.Value?.[0];
			const sopClassUID = instance["00080016"]?.Value?.[0];

			if (!studyUID || !seriesUID || !sopUID || !sopClassUID) return null;

			if (!allowedSOPs.includes(sopClassUID)) {
				console.warn(`Skipping unsupported SOP instance ${i}:`, sopClassUID);
				return null;
			}

			return `wadouri:${wadoRoot}/wado?requestType=WADO&studyUID=${studyUID}&seriesUID=${seriesUID}&objectUID=${sopUID}&contentType=application/dicom`
			// return `wadouri:/dicom-proxy/wado?requestType=WADO&studyUID=${studyUID}&seriesUID=${seriesUID}&objectUID=${sopUID}&contentType=application/dicom`;
		})
		.filter(Boolean);
}


onMounted(async () => {
	const element = viewport.value
	if (!element) return

	const { seriesUID, qidoRoot, wadoRoot } = getQueryParams()
	if (!seriesUID || !qidoRoot || !wadoRoot) {
		console.error("Missing query params")
		return
	}

	cornerstone.init()

	wadouri.external = {
		cornerstone,
		dicomParser,
	}
	cornerstone.imageLoader.registerImageLoader("wadouri", wadouri.loadImage)

	const instances = await fetchInstanceMetadata({ qidoRoot, seriesUID })
	const imageIds = buildImageIds(instances, wadoRoot)
	console.log("Image IDs:", imageIds)

	if (imageIds.length === 0) {
		console.warn("No valid images in stack.")
		return
	}


	const renderingEngineId = "basicRenderingEngine"
	const viewportId = "basicViewport"
	const renderingEngine = new cornerstone.RenderingEngine(renderingEngineId)

	renderingEngine.enableElement({
		viewportId,
		element,
		type: "stack",
	})

	const viewportObj = renderingEngine.getViewport(viewportId)
	for (const imageId of imageIds) {
		try {
			await cornerstone.imageLoader.loadAndCacheImage(imageId)
			console.log("✅ Loaded first image:", imageIds[0])

			viewport.setStack({ imageIds, currentImageIdIndex: 0 })
			viewport.render()
			break
		} catch (err) {
			console.warn("Skipping invalid image:", imageId, err)
		}
	}



})
</script>
