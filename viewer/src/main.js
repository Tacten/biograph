import { createApp } from 'vue'
import DICOMViewer from './components/DICOMViewer.vue'
import './index.css'
import { init as cornerstoneInit } from '@cornerstonejs/core'
import { init as initDicomImageLoader } from '@cornerstonejs/dicom-image-loader'

async function bootstrap() {
  await cornerstoneInit()
  await initDicomImageLoader()

  const app = createApp(DICOMViewer)
  app.mount('#app')

  console.log("Vue app is booting")
}

bootstrap()
