# End-to-End RIS, Emulator, and Bridge System Documentation

## Overview

This document explains the complete workflow of how the **Marley RIS Bridge**, **Marley Modality Simulator**, and **Healthcare RIS** work together to simulate a real-world radiology imaging workflow using DICOM protocols.

## System Architecture

```
┌─────────────────┐    DICOM MWL     ┌─────────────────┐    C-STORE     ┌─────────────────┐
│  Healthcare RIS │◄─────────────────►│ Marley Modality │───────────────►│   Orthanc PACS  │
│   (Frappe)      │                  │   Simulator     │                │                 │
└─────────┬───────┘                  └─────────────────┘                └─────────────────┘
          │                                    │
          │ UPS-RS/DICOMweb                   │ MPPS N-CREATE/N-SET
          │                                    │
          ▼                                    ▼
┌─────────────────┐    DICOM Services  ┌─────────────────┐
│ Marley RIS      │◄─────────────────►│ Marley Modality │
│    Bridge       │                   │   Simulator     │
└─────────────────┘                   └─────────────────┘
```

## Component Breakdown

### 1. Healthcare RIS (Frappe-based)
**Location**: `/home/hm/health-bench/apps/healthcare/healthcare/healthcare/api/dicom/`

**Purpose**: The main Radiology Information System that manages imaging appointments and workflows.

**Key Components**:
- **`actions.py`**: Core UPS (Unified Procedure Step) management
- **`mpps.py`**: MPPS (Modality Performed Procedure Step) handlers
- **`dcmweb_renderer.py`**: DICOMweb interface rendering

**Key Functions**:
- Manages `Imaging Appointment` documents
- Provides UPS-RS (Unified Procedure Step Retrieve Service) endpoints
- Handles MPPS N-CREATE and N-SET operations
- Converts between DICOM tags and Frappe field mappings

### 2. Marley RIS Bridge
**Location**: `/home/hm/marley_ris_bridge/`

**Purpose**: Acts as a DICOM SCP (Service Class Provider) that bridges between modality simulators and the Healthcare RIS.

**Key Components**:
- **`app.py`**: Main DICOM SCP server
- **`handlers/find.py`**: MWL (Modality Worklist) C-FIND handler
- **`handlers/mpps.py`**: MPPS N-CREATE/N-SET handlers
- **`handlers/assoc.py`**: Association management
- **`network/dicomweb.py`**: DICOMweb communication with RIS

**Supported DICOM Services**:
- **C-ECHO**: Verification service
- **C-FIND**: Modality Worklist queries
- **N-CREATE**: MPPS creation
- **N-SET**: MPPS completion
- **N-ACTION**: UPS actions

### 3. Marley Modality Simulator
**Location**: `/home/hm/marley_modality_simulator/`

**Purpose**: Simulates a real imaging modality (CT, MRI, etc.) that communicates with RIS and PACS.

**Key Components**:
- **`marley_modality/cli.py`**: Main CLI interface
- **Sample DICOM data**: `/DCM/` directory with test images

**Capabilities**:
- Queries MWL from RIS Bridge
- Sends MPPS N-CREATE (study start)
- Uploads DICOM images to PACS via C-STORE
- Sends MPPS N-SET (study completion)

## End-to-End Workflow

### Step 1: Appointment Setup in Healthcare RIS

1. **Create Patient Appointment**: Healthcare staff creates a patient appointment in the Frappe RIS
2. **Create Imaging Appointment**: An imaging appointment is created with:
   - Patient demographics
   - Observation template (imaging type)
   - Scheduled date/time
   - Modality (CT, MRI, etc.)
   - Station AE Title

### Step 2: Start the Bridge and Simulator

**Terminal 1 - Start RIS Bridge**:
```bash
cd /home/hm/marley_ris_bridge/
sudo /home/user/marley_ris_bridge/env/bin/python -m app MARLEY-SCP --host 0.0.0.0 -p 104
```

**Terminal 2 - Start Modality Simulator**:
```bash
cd /home/hm/marley_modality_simulator
source env/bin/activate
python -m marley_modality.cli -d
```

### Step 3: DICOM Communication Flow

#### 3.1 C-ECHO (Verification)
```python
# Modality Simulator → RIS Bridge
def run_echo(config):
    ae = AE(ae_title=config['ae_title'])
    ae.add_requested_context(Verification, ALL_TRANSFER_SYNTAXES)
    assoc = ae.associate(config['ris']['host'], config['ris']['port'])
    status = assoc.send_c_echo()
```

#### 3.2 C-FIND (Modality Worklist Query)
```python
# Modality Simulator queries for worklist
def run_mwl(config):
    ae = AE(ae_title=config['ae_title'])
    ae.add_requested_context(ModalityWorklistInformationFind)
    ds = Dataset()
    ds.QueryRetrieveLevel = "PATIENT"
    ds.PatientName = "*"
    responses = assoc.send_c_find(ds, ModalityWorklistInformationFind)
```

**RIS Bridge Process**:
1. Receives C-FIND request in `handlers/find.py`
2. Builds filters from DICOM dataset
3. Calls Healthcare RIS via UPS-RS: `send_ups_rs_query()`
4. Converts UPS response to MWL format
5. Returns worklist entries to modality

#### 3.3 MPPS N-CREATE (Study Start)
```python
# Modality signals study start
def run_mpps_create(config, mwl_record, study_uid):
    ds = Dataset()
    ds.AccessionNumber = mwl_record.AccessionNumber
    ds.StudyInstanceUID = study_uid
    ds.PerformedProcedureStepStatus = "IN PROGRESS"
    status, _ = assoc.send_n_create(ds, MPPS_SOP_CLASS, study_uid)
```

**RIS Bridge Process**:
1. Receives N-CREATE in `handlers/mpps.py`
2. Calls `send_n_action()` with action_type=1 (claim)
3. Healthcare RIS updates appointment status to "In Progress"

#### 3.4 C-STORE (Image Upload to PACS)
```python
# Modality uploads images to Orthanc PACS
def upload_c_store(**kwargs):
    dicom_series = build_dicom_series(kwargs['sample_dicom_path'])
    ae = AE()
    ae.add_requested_context(STORAGE_SOP_CLASS)
    assoc = ae.associate(kwargs['pacs_host'], kwargs['pacs_port'])
    
    for series in dicom_series:
        for file_path in series['files']:
            ds = dcmread(file_path)
            # Update metadata with patient info from MWL
            ds.PatientName = kwargs['patient_name']
            ds.StudyInstanceUID = study_uid
            status = assoc.send_c_store(ds)
```

#### 3.5 MPPS N-SET (Study Completion)
```python
# Modality signals study completion
def run_mpps_set(config, mwl_record, study_uid, performed_series):
    ds = Dataset()
    ds.AccessionNumber = mwl_record.AccessionNumber
    ds.StudyInstanceUID = study_uid
    ds.PerformedProcedureStepStatus = "COMPLETED"
    ds.PerformedSeriesSequence = Sequence(series_seq)
    status, _ = assoc.send_n_set(ds, MPPS_SOP_CLASS, study_uid)
```

**RIS Bridge Process**:
1. Receives N-SET in `handlers/mpps.py`
2. Calls `send_n_action()` with action_type=3 (workitemevent)
3. Healthcare RIS updates appointment status to "Completed"

### Step 4: Data Flow and Mappings

#### DICOM to Frappe Field Mapping
```python
DICOM_TO_FRAPPE_MAP = {
    "00100020": "patient",          # Patient ID
    "00100010": "patient_name",     # Patient Name
    "00100030": "date_of_birth",    # DOB
    "00100040": "gender",           # Gender
    "00400001": "scheduled_date",   # Scheduled Date
    "00080050": "name",             # Accession Number
    "00081030": "modality",         # Modality
    "0008005A": "station_ae",       # Scheduled Device
}
```

#### UPS-RS Response Format
```json
{
    "00080016": {"vr": "UI", "Value": ["1.2.840.10008.5.1.4.34.5"]},
    "00080018": {"vr": "UI", "Value": ["ups_instance_uid"]},
    "00080050": {"vr": "SH", "Value": ["accession_number"]},
    "00100020": {"vr": "LO", "Value": ["patient_id"]},
    "00100010": {"vr": "PN", "Value": ["patient_name"]},
    "00100040": {"vr": "CS", "Value": ["gender"]},
    "00404010": {
        "vr": "SQ",
        "Value": [{
            "00080100": {"vr": "SH", "Value": ["observation_template"]},
            "00081030": {"vr": "LO", "Value": ["modality"]}
        }]
    }
}
```

## Configuration Files

### Modality Simulator Config
```json
{
    "ae_title": "TEST_HARNESS",
    "ris": {
        "ae_title": "MARLEY-RIS",
        "host": "127.0.0.1",
        "port": 104
    },
    "pacs": {
        "host": "localhost",
        "port": 4242,
        "ae_title": "ORTHANC",
        "url": "http://localhost:8042/dicom-web/studies"
    },
    "sample_dicom": "./DCM/"
}
```

### RIS Bridge Config
```python
# config.py
def get_config():
    return {
        "host_name": "https://ris-server.com",
        "api_key": "your_api_key",
        "api_secret": "your_api_secret",
        "ae_title": "MARLEY-RIS"
    }
```

## Error Handling and Logging

### Bridge Logging
- All DICOM operations logged via `logzero`
- Association tracking in `handlers/assoc.py`
- Failed operations return appropriate DICOM status codes

### Simulator Logging
- Comprehensive logging of all DICOM operations
- Status codes logged for each C-STORE operation
- MWL query results displayed to user

## Security Considerations

1. **Authentication**: RIS Bridge uses token-based authentication
2. **Network Security**: DICOM communications typically on secure network
3. **Data Privacy**: Patient data handled according to HIPAA requirements
4. **Access Control**: AE Title validation for authorized modalities

## Troubleshooting

### Common Issues

1. **Association Failures**:
   - Check AE titles match configuration
   - Verify network connectivity and ports
   - Ensure RIS Bridge is running on correct port (104)

2. **MWL Query Returns Empty**:
   - Verify imaging appointment exists in RIS
   - Check appointment status is "Scheduled"
   - Validate patient name/ID filters

3. **MPPS Failures**:
   - Ensure study UID is unique
   - Check RIS API authentication
   - Verify appointment hasn't been claimed already

4. **C-STORE Failures**:
   - Verify Orthanc PACS is running
   - Check DICOM file validity
   - Ensure proper SOP Class configuration

## Integration with OHIF Viewer

The system integrates with OHIF viewer for image display:

1. **Study Access**: RIS provides Study Instance UID to OHIF
2. **DICOMweb**: OHIF uses WADO-RS to retrieve images from Orthanc
3. **Authentication**: Viewer inherits RIS session authentication

```javascript
// N-CREATE OHIF viewer launch
function openStudyViewer(studyInstanceUID) {
    const viewerUrl = `/ohif/viewer?StudyInstanceUIDs=${studyInstanceUID}`;
    window.open(viewerUrl, '_blank');
}
```

This comprehensive system provides a complete simulation of real-world radiology workflows while maintaining DICOM compliance and proper data flow between all components.


```json
{
 "AccessionNumber (0008,0050)": [
  "8592bf88074d4327"
 ],
 "Modality (0008,0060)": [],
 "StudyInstanceUID (0020,000D)": [
  "1.2.826.0.1.3680043.10.43.1755963266"
 ],
 "PerformedStationAETitle (0040,0241)": [
  "MARLEY-RIS"
 ],
 "PerformedProcedureStepStartDate (0040,0244)": [
  "20250823"
 ],
 "PerformedProcedureStepStartTime (0040,0245)": [
  "153432"
 ],
 "PerformedProcedureStepStatus (0040,0252)": [
  "IN PROGRESS"
 ]
}```


```N-SET
{
 "AccessionNumber (0008,0050)": [
  "8592bf88074d4327"
 ],
 "StudyInstanceUID (0020,000D)": [
  "1.2.826.0.1.3680043.10.43.1755963266"
 ],
 "PerformedProcedureStepStatus (0040,0252)": [
  "COMPLETED"
 ],
 "PerformedSeriesSequence (0040,0340)": [
  {
   "Modality (0008,0060)": [
    "MR"
   ],
   "SeriesDescription (0008,103E)": [
    "Siemens-MRI-Magnetom-Vida-3T_C-Spine_1800000004364899"
   ],
   "ReferencedImageSequence (0008,1140)": [
    {
     "ReferencedSOPClassUID (0008,1150)": [
      "1.2.840.10008.5.1.4.1.1.2"
     ],
     "ReferencedSOPInstanceUID (0008,1155)": [
      "1.2.826.0.1.3680043.8.498.23096790871148362753813102595995613427"
     ]
    },
    {
     "ReferencedSOPClassUID (0008,1150)": [
      "1.2.840.10008.5.1.4.1.1.2"
     ],
     "ReferencedSOPInstanceUID (0008,1155)": [
      "1.2.826.0.1.3680043.8.498.895986006627225382227023347189796810"
     ]
    },
    {
     "ReferencedSOPClassUID (0008,1150)": [
      "1.2.840.10008.5.1.4.1.1.2"
     ],
     "ReferencedSOPInstanceUID (0008,1155)": [
      "1.2.826.0.1.3680043.8.498.73055235726511968655399248231545259483"
     ]
    }
   ],
   "SeriesInstanceUID (0020,000E)": [
    "1.2.826.0.1.3680043.8.498.41026793056110168579878030807798627312"
   ]
  },
  {
   "Modality (0008,0060)": [
    "MR"
   ],
   "SeriesDescription (0008,103E)": [
    "T2spc_darkfluid_sag_iso_p2"
   ],
   "ReferencedImageSequence (0008,1140)": [
    {
     "ReferencedSOPClassUID (0008,1150)": [
      "1.2.840.10008.5.1.4.1.1.2"
     ],
     "ReferencedSOPInstanceUID (0008,1155)": [
      "1.2.826.0.1.3680043.8.498.25281274753941909729387105430395815661"
     ]
    },
    {
     "ReferencedSOPClassUID (0008,1150)": [
      "1.2.840.10008.5.1.4.1.1.2"
     ],
     "ReferencedSOPInstanceUID (0008,1155)": [
      "1.2.826.0.1.3680043.8.498.54913583739652082991060688100636619103"
     ]
    }
   ],
   "SeriesInstanceUID (0020,000E)": [
    "1.2.826.0.1.3680043.8.498.54117068537224083792261381262404219946"
   ]
  },
  {
   "Modality (0008,0060)": [
    "MR"
   ],
   "SeriesDescription (0008,103E)": [
    "Vida_Head.MR"
   ],
   "ReferencedImageSequence (0008,1140)": [
    {
     "ReferencedSOPClassUID (0008,1150)": [
      "1.2.840.10008.5.1.4.1.1.2"
     ],
     "ReferencedSOPInstanceUID (0008,1155)": [
      "1.2.826.0.1.3680043.8.498.69088719370360554051249304051962464188"
     ]
    }
   ],
   "SeriesInstanceUID (0020,000E)": [
    "1.2.826.0.1.3680043.8.498.90268536937871656556694714846756859796"
   ]
  }
 ]
}```



```json
# DATASET
{
 "00080050": {
  "vr": "SH",
  "Value": [
   "8592bf88074d4327"
  ]
 },
 "0020000D": {
  "vr": "UI",
  "Value": [
   "1.2.826.0.1.3680043.10.43.1755963266"
  ]
 },
 "00400252": {
  "vr": "CS",
  "Value": [
   "COMPLETED"
  ]
 },
 "00400340": {
  "vr": "SQ",
  "Value": [
   {
    "00080060": {
     "vr": "CS",
     "Value": [
      "MR"
     ]
    },
    "0008103E": {
     "vr": "LO",
     "Value": [
      "Siemens-MRI-Magnetom-Vida-3T_C-Spine_1800000004364899"
     ]
    },
    "00081140": {
     "vr": "SQ",
     "Value": [
      {
       "00081150": {
        "vr": "UI",
        "Value": [
         "1.2.840.10008.5.1.4.1.1.2"
        ]
       },
       "00081155": {
        "vr": "UI",
        "Value": [
         "1.2.826.0.1.3680043.8.498.23096790871148362753813102595995613427"
        ]
       }
      },
      {
       "00081150": {
        "vr": "UI",
        "Value": [
         "1.2.840.10008.5.1.4.1.1.2"
        ]
       },
       "00081155": {
        "vr": "UI",
        "Value": [
         "1.2.826.0.1.3680043.8.498.895986006627225382227023347189796810"
        ]
       }
      },
      {
       "00081150": {
        "vr": "UI",
        "Value": [
         "1.2.840.10008.5.1.4.1.1.2"
        ]
       },
       "00081155": {
        "vr": "UI",
        "Value": [
         "1.2.826.0.1.3680043.8.498.73055235726511968655399248231545259483"
        ]
       }
      }
     ]
    },
    "0020000E": {
     "vr": "UI",
     "Value": [
      "1.2.826.0.1.3680043.8.498.41026793056110168579878030807798627312"
     ]
    }
   },
   {
    "00080060": {
     "vr": "CS",
     "Value": [
      "MR"
     ]
    },
    "0008103E": {
     "vr": "LO",
     "Value": [
      "T2spc_darkfluid_sag_iso_p2"
     ]
    },
    "00081140": {
     "vr": "SQ",
     "Value": [
      {
       "00081150": {
        "vr": "UI",
        "Value": [
         "1.2.840.10008.5.1.4.1.1.2"
        ]
       },
       "00081155": {
        "vr": "UI",
        "Value": [
         "1.2.826.0.1.3680043.8.498.25281274753941909729387105430395815661"
        ]
       }
      },
      {
       "00081150": {
        "vr": "UI",
        "Value": [
         "1.2.840.10008.5.1.4.1.1.2"
        ]
       },
       "00081155": {
        "vr": "UI",
        "Value": [
         "1.2.826.0.1.3680043.8.498.54913583739652082991060688100636619103"
        ]
       }
      }
     ]
    },
    "0020000E": {
     "vr": "UI",
     "Value": [
      "1.2.826.0.1.3680043.8.498.54117068537224083792261381262404219946"
     ]
    }
   },
   {
    "00080060": {
     "vr": "CS",
     "Value": [
      "MR"
     ]
    },
    "0008103E": {
     "vr": "LO",
     "Value": [
      "Vida_Head.MR"
     ]
    },
    "00081140": {
     "vr": "SQ",
     "Value": [
      {
       "00081150": {
        "vr": "UI",
        "Value": [
         "1.2.840.10008.5.1.4.1.1.2"
        ]
       },
       "00081155": {
        "vr": "UI",
        "Value": [
         "1.2.826.0.1.3680043.8.498.69088719370360554051249304051962464188"
        ]
       }
      }
     ]
    },
    "0020000E": {
     "vr": "UI",
     "Value": [
      "1.2.826.0.1.3680043.8.498.90268536937871656556694714846756859796"
     ]
    }
   }
  ]
 }
}```