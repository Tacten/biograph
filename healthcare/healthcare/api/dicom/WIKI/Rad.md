# End-to-end workflow: OHIF in RIS with Orthanc as PACS

### End-to-end workflow: OHIF in RIS with Orthanc as PACS

- What you set up first
    - Orthanc: enable DICOMweb and CORS for your RIS domain; secure behind HTTPS/SSO or reverse proxy.
    - OHIF: embed the viewer in your RIS; configure Orthanc as the DICOMweb data source (QIDO-RS, WADO-RS, STOW-RS).
- How the study gets to the radiologist
    - Order in RIS → MWL to modality → modality acquires and C-STOREs images to Orthanc.
    - RIS learns the StudyInstanceUID (via HL7, polling QIDO, or webhook) and shows it on the worklist.
- How RIS launches the viewer
    - RIS opens OHIF with the study context:
        - Pass `StudyInstanceUIDs` (preferred), or Accession Number and let OHIF (or your RIS) resolve to UIDs via QIDO.
    - Authentication: use your RIS session/cookie via reverse proxy, or bearer token headers to Orthanc.
- Radiologist actions inside OHIF
    - Measurements: length, angle, ellipse/rectangle ROIs, etc. (Measurement Tracking).
    - Segmentations: labelmap/brush for structures (SEG).
    - Annotations/keys: key images; display states.
    - Series navigation, hanging protocols, viewport presets, window/level, MPR (if enabled).
- How the data is saved
    - Quantitative measurements → DICOM SR (TID-1500) via dcmjs.
    - Pixel-level segmentations → DICOM SEG.
    - Key images → Key Object Selection (KOS).
    - Storage path: OHIF uses DICOMweb STOW-RS to send SR/SEG/KOS back to Orthanc; these live alongside the study.
    - Optional: keep a JSON copy in RIS for drafts/UX.
- How observations flow back to the RIS
    - Lightweight: RIS stores links to the SR/SEG/KOS instance UIDs and displays summaries from Orthanc on demand.
    - Structured: RIS (or middleware) parses DICOM SR and maps values into reporting templates/fields.
    - Reporting: radiologist finalizes the report in RIS; RIS distributes via HL7 ORU/FHIR; optionally archive a PDF in Orthanc as Encapsulated PDF.
- Versioning and status
    - Use OHIF “save” for interim (draft) objects; mark final on sign-off.
    - You can tag SR ContentStatus or SeriesDescription (e.g., “Preliminary” vs “Final”), or control visibility by policy.
    - Keep provenance (observer name, time) in SR content and RIS audit trails.
- Typical minimal configs (illustrative)

Orthanc (enable DICOMweb + CORS):

```json
{
  "DicomWeb": { "Enable": true, "Root": "/dicom-web/" },
  "HttpServer": { "EnableCors": true, "CorsAllowedOrigin": "<https://ris.example.com>" }
}

```

OHIF datasource pointing to Orthanc:

```json
{
  "servers": {
    "dicomWeb": [{
      "name": "Orthanc",
      "qidoRoot": "<https://orthanc.example.com/dicom-web>",
      "wadoRoot": "<https://orthanc.example.com/dicom-web>",
      "stowRoot": "<https://orthanc.example.com/dicom-web>"
    }]
  }
}

```

RIS viewer launch (example):

```
/ohif/viewer?StudyInstanceUIDs=1.2.840.113619.2.55.3.2831164357.783.1599766931.467

```

- Best practices
    - Use MWL to prevent demographic mismatches; store measurements/segmentations as DICOM SR/SEG in Orthanc.
    - Keep the RIS as the source of truth for the signed report; archive a PDF/SR copy in Orthanc.
    - Secure Orthanc behind your RIS (reverse proxy, SSO, token header injection); enable HTTPS and audit logs.
    - For faster loads, prefetch via QIDO and cache thumbnails at the proxy layer.

If you want, I can provide a ready-to-use OHIF config JSON tailored to your Orthanc endpoint and a sample RIS launch URL pattern.

## 1. Real-World Radiology Workflow: RIS ↔ Modality ↔ PACS Communication

### Patient Appointment Booking & Data Synchronization Flow:

**Step 1: Patient Appointment in RIS (Biograph)**

- Healthcare staff schedule patient appointments in the RIS
- RIS generates imaging orders containing patient demographics, study type, and clinical indications
- Patient information includes: Name, DOB, Patient ID, Study Description, Scheduled Time

**Step 2: Modality Worklist (MWL) Communication**

- RIS communicates with imaging modalities (CT, MRI, X-ray) using **DICOM Modality Worklist (MWL)** service
- The imaging modality queries the RIS to retrieve scheduled patient information
- This eliminates manual data entry at the modality and reduces errors
- Modality receives: Patient demographics, Study UID, Accession Number, Procedure details

**Step 3: Image Acquisition & Metadata Embedding**

- Technologist performs the scan on the modality
- Modality embeds patient metadata from MWL into the DICOM images
- DICOM images contain both image data and comprehensive metadata

**Step 4: Image Storage in PACS** 

- Modality automatically sends completed DICOM studies to the PACS (Orthanc)
- PACS stores images with Study Instance UID as the primary identifier
- PACS notifies RIS of study completion (typically via HL7 messages)
    
    [How a modality stores a study to PACS (Orthanc)](https://www.notion.so/How-a-modality-stores-a-study-to-PACS-Orthanc-255b1df228f880c39320c8060144967a?pvs=21)
    

### Orthanc-Specific Implementation:

**Orthanc Configuration:**

```json
{
  "DicomModalities": {
    "CT_SCANNER": ["CT_AET", "192.168.1.100", 4242],
    "MRI_UNIT": ["MRI_AET", "192.168.1.101", 4242]
  },
  "OrthancPeers": {
    "RIS_SYSTEM": {
      "Url": "<http://ris-server:8042>",
      "Username": "ris_user"
    }
  }
}

```

**Integration Challenges & Solutions:**

- Orthanc doesn't natively support HL7 (common RIS communication protocol)
- **Solution**: Use integration middleware like **Mirth Connect** to translate HL7 messages to REST API calls
- This bridges RIS ↔ Orthanc communication gap

## 2. PACS Study Access & Viewer Integration

### Accessing Study Data from PACS:

**Study Identification:**

- Each study in Orthanc has a unique **Study Instance UID**
- Access studies via Orthanc's REST API:
    
    ```
    GET /studies/{study-id}
    GET /studies/{study-id}/instances
    GET /studies/{study-id}/series
    
    ```
    

**Typical RIS-PACS Integration Pattern:**

1. RIS stores the Study Instance UID when study is completed
2. RIS generates viewer URLs containing the Study UID
3. Viewer fetches DICOM data using the UID

### Image Format in PACS:

**DICOM Format:**

- Images stored in native **DICOM format** (.dcm files)
- DICOM contains both image data and metadata (patient info, acquisition parameters)
- Orthanc can convert DICOM to web-friendly formats (JPEG, PNG) on-demand for viewers

**DICOM-WEB Services:**
Orthanc supports DICOM-WEB standards for web-based access:

- **WADO-RS** (Web Access to DICOM Objects): Retrieve images/metadata
- **QIDO-RS** (Query based on ID for DICOM Objects): Search studies
- **STOW-RS** (Store Over the Web): Upload studies

### Cornerstone.js Integration Best Practices:

**1. Architecture Pattern:**

```
RIS → Orthanc REST API → DICOM-WEB → Cornerstone.js Viewer

```

**2. Implementation Approach:**

- **RIS Integration**: Embed Cornerstone.js viewer in RIS web interface
- **Authentication**: Use Orthanc's built-in authentication or proxy through RIS
- **Study Loading**: Pass Study Instance UID from RIS to viewer
- **Image Retrieval**: Use Cornerstone WADO Image Loader to fetch DICOM data

[Process of radiologists capturing observations and how they flow](https://www.notion.so/Process-of-radiologists-capturing-observations-and-how-they-flow-256b1df228f8804b966dcb8eedcd147e?pvs=21)

**3. Sample Integration Code:**

```jsx
// In your RIS, launch viewer with study ID
function openStudyViewer(studyInstanceUID) {
  const viewerUrl = `/viewer?study=${studyInstanceUID}`;
  window.open(viewerUrl, '_blank');
}

// In Cornerstone.js viewer
cornerstoneWADOImageLoader.configure({
  beforeSend: function(xhr) {
    // Add authentication headers if needed
    xhr.setRequestHeader('Authorization', 'Bearer ' + token);
  }
});

// Load study
const wadoUrl = `${orthancUrl}/studies/${studyId}/series/${seriesId}/instances/${instanceId}/frames/1`;
cornerstone.loadImage(wadoUrl).then(image => {
  cornerstone.displayImage(element, image);
});

```

**4. Security Considerations:**

- Use HTTPS for all communications
- Implement proper authentication (OAuth2, JWT tokens)
- Ensure HIPAA compliance for patient data access
- Consider using Orthanc's built-in user management

### Typical Production Architecture:

```
┌─────────────┐     HL7/DICOM MWL     ┌──────────────┐
│     RIS     │◄──────────────────────►│   Modality   │
│             │                       │  (CT/MRI)    │
└─────┬───────┘                       └──────┬───────┘
      │                                      │
      │ HL7 (via Mirth)                     │ DICOM Store
      ▼                                      ▼
┌─────────────┐     REST API          ┌──────────────┐
│   Orthanc   │◄──────────────────────►│ Cornerstone  │
│    PACS     │    DICOM-WEB/WADO     │   Viewer     │
└─────────────┘                       └──────────────┘

```

This architecture ensures seamless patient data flow from appointment booking through image viewing, with Orthanc serving as the central PACS repository and Cornerstone.js providing the viewing capabilities within your RIS interface.