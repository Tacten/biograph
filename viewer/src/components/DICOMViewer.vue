<template>
  <div ref="viewport" class="w-[512px] h-[512px] bg-black"></div>
</template>

<script setup>
import { ref, onMounted } from "vue"

import * as cornerstone from "@cornerstonejs/core"
// import { ViewportType } from "@cornerstonejs/core"
import { wadouri } from "@cornerstonejs/dicom-image-loader"
import dicomParser from "dicom-parser"

const viewport = ref(null)

onMounted(async () => {

  cornerstone.init()

  wadouri.external = {
    cornerstone,
    dicomParser,
  }

  cornerstone.imageLoader.registerImageLoader("wadouri", wadouri.loadImage)

  const element = viewport.value
  console.log("element: ", element)
  if (!element) return

  const renderingEngineId = "basicRenderingEngine"
  const viewportId = "basicViewport"
  const renderingEngine = new cornerstone.RenderingEngine(renderingEngineId)

  renderingEngine.enableElement({
    viewportId,
    element,
    type: "stack",
  })

  const viewportObj = renderingEngine.getViewport(viewportId)

  const imageIds = [
    "wadouri:https://raw.githubusercontent.com/cornerstonejs/cornerstoneWADOImageLoader/master/testImages/CT0012.fragmented_no_bot_jpeg_baseline.51.dcm",
  ]

  await cornerstone.imageLoader.loadAndCacheImage(imageIds[0])

  viewportObj.setStack({
    imageIds,
    currentImageIdIndex: 0,
  })

  viewportObj.render()
})
</script>
