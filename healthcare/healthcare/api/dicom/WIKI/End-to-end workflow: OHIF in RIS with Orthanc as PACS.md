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