import base64

from pydicom.datadict import keyword_for_tag


def dicom_to_named_dict(ds):
	result = {}
	for elem in ds:
		tag = elem.tag
		vr = elem.VR
		keyword = keyword_for_tag(tag)

		if not keyword:  # fallback to tag number string
			keyword = f"Tag_{tag.group:04X}_{tag.element:04X}"

		if vr == "SQ":  # Sequence
			result[keyword] = [dicom_to_named_dict(item) for item in elem.value]
		elif vr in ("OB", "OW", "UN"):  # Binary data
			try:
				result[keyword] = base64.b64encode(elem.value).decode("utf-8")
			except Exception:
				result[keyword] = None  # fallback if not base64-compatible
		elif isinstance(elem.value, bytes):
			try:
				result[keyword] = elem.value.decode("utf-8")
			except UnicodeDecodeError:
				result[keyword] = base64.b64encode(elem.value).decode("utf-8")
		elif isinstance(elem.value, (list, tuple)):
			result[keyword] = list(elem.value)
		else:
			result[keyword] = elem.value
	return result
