import { createApp } from "vue"
import App from "./App.vue"
import "./index.css"
import DicomViewer from "./components/DICOMViewer.vue"

createApp(DicomViewer).mount("#app")
const app = createApp(App)
app.mount("#app")
