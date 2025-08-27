<template>
	<div class="w-full h-full bg-red">
    <!-- Loading State -->
    <div v-if="isLoading" class="p-4 text-white bg-blue-600">
      Loading DICOM viewer...
    </div>
    
    <!-- Error State -->
    <div v-else-if="error" class="p-4 text-white bg-red-600">
      Error: {{ error }}
    </div>
    
    <!-- Viewport is always rendered so the ref exists at mount -->
    <div class="flex flex-col items-center justify-center h-full">
      <div ref="viewportRef" class="w-[512px] h-[512px] bg-gray-800" tabindex="-1"
           data-viewport-uid="dicomViewport"
           data-rendering-engine-uid="dicomRenderingEngine">
      </div>
      <div v-if="!error" class="mt-4 text-sm text-white">
        Study: {{ studyUID }}
      </div>
    </div>
  </div>
</template>

<script setup>
import { ref, onMounted, defineProps } from "vue"
import * as cornerstone from "@cornerstonejs/core"
import { RenderingEngine, Enums } from "@cornerstonejs/core"
import { init as initDicomImageLoader } from "@cornerstonejs/dicom-image-loader"


const props = defineProps({
  pacsBaseUrl: {
    type: String,
    required: true
  },
  pacsUsername: {
    type: String,
    required: true
  },
  pacsPassword: {
    type: String,
    required: true
  },
  studyUID: {
    type: String,
    required: true,
    validator: value => {
      if (!value) {
        console.error('Error: studyUID is required');
        return false;
      }
      return true;
    }
  },
  seriesUID: {
    type: String,
    required: true,
    validator: value => {
      if (!value) {
        console.error('Error: seriesUID is required');
        return false;
      }
      return true;
    }
  },
  objectUID: {
    type: [String, Array],
    required: true,
    validator: value => {
      if (!value || (Array.isArray(value) && value.length === 0)) {
        console.error('Error: At least one objectUID is required');
        return false;
      }
      return true;
    }
  }
})

const viewportRef = ref(null)
const renderingEngineId = "dicomRenderingEngine"
const viewportId = "dicomViewport"

const error = ref(null);
const isLoading = ref(true);

onMounted(async () => {
  try {
    // Validate all required props
    if (!props.studyUID || !props.seriesUID || !props.objectUID || 
        !props.pacsBaseUrl || !props.pacsUsername || !props.pacsPassword) {
      throw new Error('Required DICOM or PACS parameters are missing');
    }

await cornerstone.init()

initDicomImageLoader({
  beforeSend: (xhr) => {
    const base64Credentials = btoa(`${props.pacsUsername}:${props.pacsPassword}`)
    xhr.setRequestHeader('Authorization', `Basic ${base64Credentials}`)
  }
})
		const element = viewportRef.value
		if (!element) throw new Error("Viewport element not found")

		const renderingEngine = new RenderingEngine(renderingEngineId)
		renderingEngine.enableElement({
			viewportId,
			element,
			type: Enums.ViewportType.STACK,
		})

		const viewPort = renderingEngine.getViewport(viewportId)

		const { studyUID, seriesUID } = props
		const objectUIDs = Array.isArray(props.objectUID) ? props.objectUID : [props.objectUID]
		let imageIds = []

		objectUIDs.forEach(o => {
			// const imageId = `wadori:http://localhost:8080/wado?requestType=WADO&studyUID=${studyUID}&seriesUID=${seriesUID}&objectUID=${o}`
			// const imageId = `wadors:http://localhost:8080/dicom-web/studies=${studyUID}&series=${seriesUID}&instances=${o}`
			// const imageId = `wadors://localhost:8080/dicom-web/studies/${studyUID}/series/${seriesUID}/instances/${o}/frames/1`
			// const imageId = `wadors:${props.pacsBaseUrl}/dicom-web/studies/${studyUID}/series/${seriesUID}/instances/${o}`
			// const imageId = `wadouri:${props.pacsBaseUrl}/instances/0664aace-03bbf140-61a682a1-2f777d8b-96a352ec/file`
			const imageId = `wadouri:${props.pacsBaseUrl}/wado?requestType=WADO&studyUID=${studyUID}&seriesUID=${seriesUID}&objectUID=${o}&contentType=application/dicom`;
			// const imageId = `wadouri:${props.pacsBaseUrl}/wado?requestType=WADO&studyUID=${studyUID}&seriesUID=${seriesUID}&objectUID=${o}`
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
  } catch (err) {
    const errorMsg = `Failed to load DICOM viewer: ${err.message}`;
    error.value = errorMsg;
    console.error('DICOMViewer error:', errorMsg, err);
  } finally {
    isLoading.value = false;
  }
})
</script>
