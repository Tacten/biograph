# FHIR Terminology Service Parity — Implementation Plan

## Context

Biograph's terminology model (`Code System`, `Code Value`, `Code Value Set`, `Codification Table`) provides a solid foundation for medical coding but falls short of FHIR terminology service standards in four areas: hierarchy support, dynamic value sets, concept designations, and concept mapping. **PR #252** (merged) added `code_value_set` to the Codification Table and introduced shared codification client utilities, establishing the groundwork for value-set-level codification. This plan extends that work toward full FHIR parity while preserving backward compatibility across the **16 doctypes** that consume the `Codification Table` child table.

**Goal:** Bring Biograph to parity with standard FHIR terminology services (CodeSystem hierarchy, dynamic ValueSet compose/include, terminology operations) without regressing any existing codification workflows.

---

## What PR #252 Already Delivered

PR #252 has been merged and provides the foundation this plan builds upon:

### Schema
- Added `code_value_set` (Link → Code Value Set) to `codification_table.json`, positioned immediately after `code_system` for UX clarity

### Shared Client Utilities (`public/js/utils.js`)
- **`set_codification_table_query(frm)`** — Cascading filters: `code_system → code_value_set → code_value`. When both `code_system` and `code_value_set` are set, `code_value` is filtered by both; when only `code_system` is set, the original single-filter behavior is preserved
- **`before_save_check(frm)`** — Before-save consistency validation that calls `get_codification_row_code_data()` to verify `code_value_set` matches the server-side `value_set` on the linked Code Value
- **`auto_table_code_val_set(frm, cdt, cdn)`** — Auto-populates `code_value_set` from the selected `code_value`'s `value_set` field when no value set is manually chosen

### Backend (`healthcare/utils.py`)
- **`get_codification_row_code_data(code_value, code_system)`** — Whitelisted method returning `value_set` and `code_system` for a given Code Value; used by `before_save_check`
- **`get_medical_codes()`** — Now includes `code_value_set` in its return fields, so template copy flows propagate the value set

### Consumer DocType Integration
All 15 consumer JS files (Patient Encounter, Diagnosis, Lab Test, Clinical Procedure, Observation, Medication, Service Request, Therapy Session, etc.) updated with `Codification Table` event handlers that delegate to the shared utilities for `code_value_set`, `code_system`, and `code_value` field changes.

---

## Regression Scope — 16 Consumer DocTypes

Any schema change to `Code Value`, `Code Value Set`, or `Codification Table` must be validated against these consumers:

| Category | DocTypes |
|----------|----------|
| **Core Clinical** | Patient Encounter, Observation, Lab Test, Clinical Procedure |
| **Masters** | Diagnosis, Complaint, Medication, Appointment Type |
| **Requests** | Medication Request, Service Request, Therapy Session |
| **Templates** | Observation Template, Lab Test Template, Clinical Procedure Template, Therapy Type |

**Critical auto-population flows that must not break:**
1. `Patient Encounter.set_codification_table_from_diagnosis()` — copies codes from Diagnosis via `get_medical_codes()` (now includes `code_value_set`)
2. `Service Request.validate()` — copies template's codification_table rows (`service_request.py:24-30`)
3. Shared client utility `set_codification_table_query()` in `public/js/utils.js` — provides cascading filters (`code_system → code_value_set → code_value`) for all 15 consumer doctypes
4. `before_save_check()` — validates `code_value_set` consistency against server-side Code Value data
5. `auto_table_code_val_set()` — auto-populates `code_value_set` from selected `code_value`

**Safety principle:** All new fields are optional with backward-compatible defaults. Existing records and workflows continue to work unchanged.

---

## Phase 1: Hierarchy Support in Code Systems

### Schema Changes

#### [MODIFY] `healthcare/doctype/code_value/code_value.json`
Add field `parent_code`:
```json
{
  "fieldname": "parent_code",
  "fieldtype": "Link",
  "label": "Parent Code",
  "options": "Code Value",
  "search_index": 1,
  "description": "Parent concept in the hierarchy (must be from same Code System)"
}
```

#### [MODIFY] `healthcare/doctype/code_system/code_system.json`
Add field `hierarchy_meaning`:
```json
{
  "fieldname": "hierarchy_meaning",
  "fieldtype": "Select",
  "label": "Hierarchy Meaning",
  "options": "\nis-a\npart-of\nclassified-with\ngrouped-by",
  "description": "Structural meaning of parent-child relationships in this code system"
}
```

### Logic Changes

#### [MODIFY] `healthcare/doctype/code_value/code_value.py`
- **`validate()`**: Enforce `parent_code.code_system == self.code_system` (same code system only)
- **`validate()`**: Circular dependency check — walk up `parent_code` chain with depth limit of 50; raise `ValidationError` if cycle detected
- **`validate()`**: Auto-compute `level` from `parent_code` depth (root = 0, child of root = 1, etc.) — maintains backward compatibility with existing `level` field consumers
- **`get_descendants()`** (`@frappe.whitelist()`): Returns flat list of descendant Code Value names using iterative BFS query
- **`get_ancestors()`** (`@frappe.whitelist()`): Returns ordered list of ancestor Code Value names walking up `parent_code`

#### [MODIFY] `healthcare/doctype/code_value/code_value.js`
- Add `set_query` on `parent_code` to filter by `code_system: frm.doc.code_system`

#### [NEW] `healthcare/patches/v15_0/add_parent_code_to_code_value.py`
- No-op migration — sets `parent_code = NULL` on all existing records (documents schema change)

### Regression Risk: LOW
- `parent_code` is optional (NULL default) — all existing Code Values remain valid flat codes
- `level` field is auto-computed on save but never overwritten for existing records until they're re-saved
- Codification Table, `get_medical_codes()`, and cascading filters are completely unaffected — they never reference hierarchy
- Code Value autoname (`{code_value}{-version}-{code_system}`) is unchanged

---

## Phase 2: Dynamic Value Sets

### New DocType

#### [NEW] `healthcare/doctype/value_set_include_rule/`
Child table for defining compose/include rules on Code Value Set:
```
Fields:
- code_system     (Link → Code System, required)
- filter_property (Select: "concept", "is-a", "descendent-of", "is-not-a", "in", "not-in", "exists")
- filter_value    (Data — code value string for filter matching)
- filter_code     (Link → Code Value — when filter references a specific concept)
```

### Schema Changes

#### [MODIFY] `healthcare/doctype/code_value_set/code_value_set.json`
Add fields:
```json
{
  "fieldname": "is_dynamic",
  "fieldtype": "Check",
  "label": "Is Dynamic",
  "default": 0,
  "description": "When enabled, codes are determined by include rules instead of static links"
},
{
  "fieldname": "include_rules",
  "fieldtype": "Table",
  "label": "Include Rules",
  "options": "Value Set Include Rule",
  "depends_on": "eval:doc.is_dynamic"
}
```

### Logic Changes

#### [MODIFY] `healthcare/doctype/code_value_set/code_value_set.py`
- **`get_expanded_codes()`** (`@frappe.whitelist()`):
  - If `is_dynamic == 0`: `frappe.get_all("Code Value", filters={"value_set": self.name}, pluck="name")`
  - If `is_dynamic == 1`: Evaluate each `include_rule`:
    - `"concept"`: Direct code match
    - `"is-a"` / `"descendent-of"`: Call `CodeValue.get_descendants()` from Phase 1
    - `"is-not-a"`: All codes in system minus descendants
    - `"in"`: Comma-separated code list
  - Return union of all rule results
- **Caching**: Use `frappe.cache().set_value()` with key `vs_expand:{name}`, TTL 3600s. Invalidate via `on_update` hook on Code Value Set and a `doc_events` hook on Code Value save (if its `code_system` matches any rule's `code_system`).

#### [MODIFY] `healthcare/utils.py`
- Add a new whitelisted method `get_value_set_codes(value_set_name)` that calls `get_expanded_codes()` — used by client-side cascading filters to populate `code_value` dropdown when a dynamic `code_value_set` is selected.

### Regression Risk: LOW-MEDIUM
- `is_dynamic` defaults to `0` — all existing Code Value Sets continue as static groupings
- The static path (`value_set` link on Code Value) is preserved as the default behavior
- Existing cascading filters (`code_system → code_value`) are unaffected
- **Performance concern**: Dynamic expansion on large code systems (SNOMED 300k+ concepts) could be slow. Mitigations:
  1. Redis cache with 1-hour TTL avoids repeated computation
  2. `is_dynamic` flag ensures static value sets (majority) have zero overhead
  3. If performance is measured as a problem after SNOMED import, add a `materialized_path` column to Code Value for O(1) descendant queries (deferred optimization, not in initial scope)

---

## Phase 3: Cascading Filter Integration

### Logic Changes

#### [MODIFY] `public/js/utils.js` — `set_codification_table_query()`
The shared utility (already delivered by PR #252) currently filters `code_value` by `{code_system, value_set}` using a static link match. Update the `code_value` query to support dynamic value sets:

```javascript
// Current (PR #252): filters code_value by { code_system, value_set: row.code_value_set }
// Updated: When code_value_set is selected, check if it's dynamic via server call
// If dynamic: call get_value_set_codes() to get expanded code list, filter by name IN [...]
// If static (or no value set): keep existing filter behavior unchanged
```

This is the **single integration point** — all 15 consumer doctype JS files already delegate to this shared utility via their `Codification Table` event handlers. No individual doctype JS changes needed.

#### [MODIFY] `public/js/utils.js` — `before_save_check()`
Update to handle dynamic value sets: when a `code_value_set` is dynamic, skip the strict `code_value_set !== server_value_set` mismatch check since the code may belong to the value set via a rule rather than a direct `value_set` link on Code Value.

### Regression Risk: LOW
- The shared utility adds a conditional path: if `code_value_set` is dynamic, use expanded codes. Otherwise, fall through to existing filter. Existing behavior is the default path.
- `get_medical_codes()` already includes `code_value_set` in its return fields (PR #252), so template copy flows already propagate the value set reference.

---

## What to DEFER

### ConceptMap (Gap 4) — Defer to separate future phase
- Current `canonical_mapping` on Code Value has no programmatic consumers (no Python code references it)
- Full ConceptMap requires a new doctype with source/target pairs, equivalence levels, bidirectional traversal — significant scope with no immediate workflow need
- Can be added independently later without affecting Phases 1-3

### Designations / Properties (Gap 3) — Defer
- No current UI or workflow uses synonyms or translations
- Can be added as child tables to Code Value later (purely additive, zero breaking change)
- Worth revisiting when multi-language support or synonym search becomes a requirement

### FHIR Operations ($validate-code, $expand, $lookup) — Defer
- These are API-level operations typically needed for FHIR interop endpoints
- The internal methods (`get_expanded_codes`, `get_descendants`) provide the underlying logic
- Wrapping them in FHIR-compliant operation endpoints can be done when a FHIR API layer is built

---

## Files Summary

### Phase 1
| Action | File |
|--------|------|
| MODIFY | `healthcare/doctype/code_value/code_value.json` — add `parent_code` field |
| MODIFY | `healthcare/doctype/code_value/code_value.py` — hierarchy validation, `get_descendants()`, `get_ancestors()`, auto-compute `level` |
| MODIFY | `healthcare/doctype/code_value/code_value.js` — `parent_code` filter by `code_system` |
| MODIFY | `healthcare/doctype/code_system/code_system.json` — add `hierarchy_meaning` field |
| NEW | `healthcare/patches/v15_0/add_parent_code_to_code_value.py` |
| MODIFY | `healthcare/patches.txt` — register patch |

### Phase 2
| Action | File |
|--------|------|
| NEW | `healthcare/doctype/value_set_include_rule/` — child table doctype (JSON, PY, __init__) |
| MODIFY | `healthcare/doctype/code_value_set/code_value_set.json` — add `is_dynamic`, `include_rules` |
| MODIFY | `healthcare/doctype/code_value_set/code_value_set.py` — `get_expanded_codes()` with caching |
| MODIFY | `healthcare/utils.py` — add `get_value_set_codes()` |

### Phase 3
| Action | File |
|--------|------|
| MODIFY | `public/js/utils.js` — update `set_codification_table_query()` for dynamic value set resolution |
| MODIFY | `public/js/utils.js` — update `before_save_check()` to handle dynamic value sets |

---

## Verification Plan

### Phase 1 Tests
1. **Unit**: Create Code System with `hierarchy_meaning = "is-a"`, create 3-level hierarchy (Analgesics → NSAIDs → Ibuprofen), verify `get_descendants("Analgesics")` returns `[NSAIDs, Ibuprofen]`
2. **Unit**: Verify circular dependency (A → B → C → A) raises `ValidationError`
3. **Unit**: Verify `level` auto-computed correctly (root=0, child=1, grandchild=2)
4. **Regression**: Create a Diagnosis with codification rows, create Patient Encounter referencing it — verify `set_codification_table_from_diagnosis()` still works
5. **Regression**: Open each of 4 representative doctypes (Patient Encounter, Lab Test, Diagnosis, Service Request) — verify codification table renders and cascading filter works

### Phase 2 Tests
1. **Unit**: Static value set — `get_expanded_codes()` returns codes with matching `value_set` link
2. **Unit**: Dynamic value set with `is-a` rule — returns correct descendants
3. **Unit**: Cache invalidation — add new Code Value under hierarchy, call `get_expanded_codes()` again, verify it includes the new code
4. **Regression**: Existing Code Value Sets (static) continue to work unchanged in Codification Table dropdowns

### Phase 3 Tests
1. **Integration**: In Codification Table, select a dynamic `code_value_set` — verify `code_value` dropdown shows only expanded codes
2. **Integration**: In Codification Table, select a static `code_value_set` or none — verify existing filter behavior unchanged (same as PR #252 behavior)
3. **Integration**: Verify `before_save_check()` passes for a code that belongs to a dynamic value set via rule (not direct `value_set` link)
4. **Integration**: Template copy flow (Lab Test Template → Lab Test) propagates `code_value_set` (already works via PR #252's `get_medical_codes()`)
5. **Integration**: Run through Patient Encounter → Diagnosis → auto-populate codification flow end-to-end, verify `code_value_set` is populated via `auto_table_code_val_set()`
