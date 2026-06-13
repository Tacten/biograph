# Insurance Module Parity Report

## Scope

Comparison and reconciliation of insurance features against **earthians/marley** (`marley-develop`) for:

| Branch | Path | Status |
|--------|------|--------|
| **biograph-fh** | `biograph-fh/biograph-fh` | Parity implemented (Jun 2026) |
| **biograph-insurance-v15** | `biograph-fh/biograph-insurance-v15` | Parity implemented (Jun 2026) |
| **Source reference** | `biograph-fh/marley-develop` | Upstream target |

Analysis methods: direct file diff, GitNexus knowledge-graph queries (`query`, `context`, `impact`), and targeted cherry-picks preserving Biograph-specific validation improvements.

---

## Executive Summary

Both **biograph-fh** and **biograph-insurance-v15** are now **functionally in parity** with Marley for insurance billing, claims, dashboard, tests, and MCP-indexed code flows. They are **not byte-identical** to Marley by design — Biograph branches retain stronger validation logic in several modules.

### What was ported from Marley (both branches)

| Area | Change |
|------|--------|
| **`healthcare/utils.py`** | Insurance-aware invoicing for appointments, encounters, lab tests, procedures, inpatient, therapy, service requests; `update_insurance_coverage()`; `post_transfer_journal_entry_and_update_coverage()`; `manage_fee_validity()` integration |
| **`insurance_claim/insurance_claim.py`** | `get_coverages()` refactored to QueryBuilder (pypika) |
| **`item_insurance_eligibility.js`** | `frm.set_df_property("template_dt", "only_select", true)` |
| **`insurance_claim_status.py`** | Company filter on dashboard chart query |
| **`patient_insurance_coverage.py`** | `currency` passed to `get_item_price_list_rate()` |
| **Test infrastructure** | `healthcare/tests/utils.py` with `HealthcareTestSuite` + `BootStrapTestData` |
| **Insurance tests (×6)** | Migrated to `HealthcareTestSuite` pattern |

### GitNexus verification

Both repos re-indexed after changes. Queries for `update_insurance_coverage` and `post_transfer_journal_entry_and_update_coverage` now resolve to `healthcare/healthcare/utils.py` (previously absent in Biograph indexes).

---

## Implementation Status by File

| File | biograph-fh | biograph-insurance-v15 | Notes |
|------|:-----------:|:----------------------:|-------|
| `healthcare/utils.py` — insurance billing | ✅ | ✅ | v15 uses simpler `manage_invoice` (no credit-note flip); fh retains `get_package_subscriptions_to_invoice()` |
| `insurance_claim/insurance_claim.py` — QueryBuilder | ✅ | ✅ | Biograph keeps `status` in `update_insurance_coverage_status()` |
| `item_insurance_eligibility.js` — `only_select` | ✅ | ✅ | Matches Marley |
| `insurance_claim_status.py` — company filter | ✅ | ✅ | Matches Marley |
| `patient_insurance_coverage.py` — currency | ✅ | ✅ | Other Biograph null-safety retained |
| `healthcare/tests/utils.py` | ✅ | ✅ | New in v15 (was missing) |
| `test_insurance_claim.py` | ✅ | ✅ | |
| `test_insurance_payor.py` | ✅ | ✅ | |
| `test_insurance_payor_contract.py` | ✅ | ✅ | |
| `test_item_insurance_eligibility.py` | ✅ | ✅ | New in v15 |
| `test_patient_insurance_coverage.py` | ✅ | ✅ | New in v15 |
| `test_patient_insurance_policy.py` | ✅ | ✅ | New in v15 |

---

## Intentional Remaining Differences vs Marley

These are **deliberate** — do not blind-merge from Marley.

### 1. `item_insurance_eligibility/item_insurance_eligibility.py`

| Check | Biograph (fh + v15) | Marley |
|-------|---------------------|--------|
| Percentage validation | `(flt(self.coverage) + flt(self.discount)) > 100` ✅ | `(flt(self.discount) + flt(self.discount)) > 100` ❌ typo |
| Overlap validation | Comprehensive (open-ended date ranges) | Simplified |
| `get_insurance_eligibility` null `item_code` | `(item_code or "")` safe | Bare `item_code` |

### 2. `patient_insurance_coverage/patient_insurance_coverage.py`

Biograph retains:

- `set_title()` with `template_dn or item_code` fallback
- Dynamic meta field checks in `set_and_validate_template_details()`
- `item_code` fallback from eligibility record
- Guard when `item_code` missing before price-list fetch
- `elif not price_list_rate and not self.price_list_rate` (preserves existing rate)
- `coverage.submit(ignore_permissions=True)`
- Field names `item_code` / `valid_from` (schema-aligned)

Marley-only items **not** ported: `item` / `start_date` renames in eligibility helper (schema drift).

### 3. `patient_insurance_policy/patient_insurance_policy.py`

| Check | Biograph | Marley |
|-------|----------|--------|
| `is_insurance_policy_valid()` | Requires `docstatus == 1` + expiry | Expiry only |
| Policy overlap filter | `policy_expiry_date >= today()` | `policy_expiry_date <= self.policy_expiry_date` |

### 4. `insurance_claim/insurance_claim.py`

| Behavior | Biograph | Marley |
|----------|----------|--------|
| `update_insurance_coverage_status()` | Sets `approved_amount`, `paid_amount`, **`status`** | Sets amounts only; omits `status` sync |

**Product decision pending:** whether claim child row status should overwrite Patient Insurance Coverage status.

### 5. `healthcare/utils.py` — branch-specific

| Feature | biograph-fh | biograph-insurance-v15 | Marley |
|---------|:-----------:|:----------------------:|:------:|
| `get_package_subscriptions_to_invoice()` | ✅ | ❌ | ❌ |
| Credit note / `is_return` invoice flip | ✅ | ❌ | ❌ |
| `update_therapy_plan()` in invoice hook | ✅ | ❌ | ❌ |
| Insurance billing + JE posting | ✅ | ✅ | ✅ |

---

## Original Gap Analysis (pre-implementation)

The following gaps existed before reconciliation and are **now addressed** in both Biograph branches:

1. ~~Raw SQL in `insurance_claim.get_coverages()`~~ → QueryBuilder
2. ~~Missing company filter on insurance claim chart~~ → Added
3. ~~No `HealthcareTestSuite` / bootstrap test data~~ → Ported
4. ~~No insurance branches in invoicing helpers~~ → Full Marley billing flow ported
5. ~~No `update_insurance_coverage` / JE transfer on SI submit~~ → Added
6. ~~Missing `only_select` on eligibility form~~ → Added
7. ~~Missing `currency` in price lookup~~ → Added

---

## Detailed Reference: Marley Insurance Billing Flow

Ported helpers in `healthcare/utils.py`:

```python
get_valid_insurance_coverage_details(insurance_coverage, company)
get_insurance_invoice_line(reference_type, reference_name, ...)
update_insurance_coverage(sales_invoice)                          # on SI cancel
post_transfer_journal_entry_and_update_coverage(sales_invoice)    # on SI submit
```

Insurance invoice lines are emitted when coverage is **Approved** or **Partly Invoiced**, validity end date is not passed, and company matches. Fields include: `insurance_coverage`, `insurance_payor`, `patient_insurance_policy`, `coverage_percentage`, `discount_percentage`, `coverage_rate`, `coverage_qty`.

Functions updated: `get_appointments_to_invoice`, `get_encounters_to_invoice`, `get_lab_tests_to_invoice`, `get_clinical_procedures_to_invoice`, `get_inpatient_services_to_invoice`, `get_therapy_sessions_to_invoice`, `get_service_requests_to_invoice`.

---

## Test Plan

Run on a Frappe bench with Healthcare + ERPNext test fixtures:

```bash
# Core insurance flows
bench --site <site> run-tests --module healthcare.healthcare.doctype.patient_insurance_coverage.test_patient_insurance_coverage
bench --site <site> run-tests --module healthcare.healthcare.doctype.insurance_claim.test_insurance_claim
bench --site <site> run-tests --module healthcare.healthcare.doctype.item_insurance_eligibility.test_item_insurance_eligibility
bench --site <site> run-tests --module healthcare.healthcare.doctype.patient_insurance_policy.test_patient_insurance_policy
bench --site <site> run-tests --module healthcare.healthcare.doctype.insurance_payor.test_insurance_payor
bench --site <site> run-tests --module healthcare.healthcare.doctype.insurance_payor_contract.test_insurance_payor_contract
```

### Manual E2E checklist

- [ ] Create insurance payor, contract, eligibility plan, and patient policy
- [ ] Book appointment with insurance policy → coverage auto-created
- [ ] Invoice appointment → SI line shows coverage %, discount %, insurance amount
- [ ] Submit SI → Journal Entry posted; Patient Insurance Coverage qty/amount updated
- [ ] Cancel SI → coverage amounts reversed
- [ ] Create and submit Insurance Claim from invoiced coverages
- [ ] Insurance Claim Status dashboard respects company filter

### Re-index after future insurance changes

```bash
cd biograph-fh/biograph-fh && gitnexus analyze
cd biograph-insurance-v15 && gitnexus analyze
```

---

## Recommendations Going Forward

1. **Do not merge Marley wholesale** into Biograph insurance validation modules — cherry-pick only.
2. **Consider upstreaming** Biograph fixes to Marley: eligibility percentage typo, policy `docstatus` check, null-safe eligibility lookup.
3. **Resolve product decision** on `update_insurance_coverage_status()` status sync before contributing claim changes back to Marley.
4. **Keep branches aligned**: when porting new Marley insurance fixes, apply to both `biograph-fh` and `biograph-insurance-v15` unless v15-specific divergence is intentional.
5. **Run insurance test suite in CI** on both branches after insurance-related PRs.

---

## GitNexus Re-Verification (Jun 2026)

After reconnecting GitNexus MCP, parity was re-validated directly with `list_repos`, `query`, `context`, and `impact` for:

- `biograph-fh/biograph-fh` vs `biograph-fh/marley-develop`
- `biograph-fh/biograph-insurance-v15` vs `biograph-fh/marley-develop`

### Indexed commit evidence

From `list_repos`:

- **biograph-fh**: `4e0363d2d19931f2d4f548ffe25bf24ad651387d`
- **biograph-insurance-v15**: `2171818e4ee32501a64d8cfffa62cbedba3c8e8b`
- **marley-develop**: `3428b277ed97a4a4f78ef9ce6dac337ba6ae8fbe`

### Flow parity evidence (`query` + `context`)

In both Biograph branches and Marley, GitNexus resolves the same core insurance billing and claims symbols:

- `healthcare/healthcare/utils.py`
  - `update_insurance_coverage`
  - `post_transfer_journal_entry_and_update_coverage`
- `healthcare/healthcare/doctype/insurance_claim/insurance_claim.py`
  - `InsuranceClaim.get_coverages`
- `healthcare/healthcare/dashboard_chart_source/insurance_claim_status/insurance_claim_status.py`
  - `get`

`context` also confirms matching wiring:

- `update_insurance_coverage` is called by `manage_invoice_submit_cancel`
- `post_transfer_journal_entry_and_update_coverage` is called by `manage_invoice_submit_cancel` and calls `get_insurance_payor_details`

for both Biograph branches and Marley.

### Blast radius parity evidence (`impact`)

For both `biograph-fh` and `biograph-insurance-v15` compared with Marley:

- `update_insurance_coverage`: `impactedCount=1`, `risk=LOW`
- `post_transfer_journal_entry_and_update_coverage`: `impactedCount=1`, `risk=LOW`
- `insurance_claim_status.get`: `impactedCount=0`, `risk=LOW`
- `update_insurance_coverage_status`: `impactedCount=3`, `risk=LOW`

### Confirmed conclusion

Both Biograph branches are **functionally in parity** with Marley for insurance workflows, with intentional non-parity in selected validation/hardening behavior.

Known intentional divergence (still present):

- `update_insurance_coverage_status()` in Biograph updates `status` alongside amounts; Marley updates amounts only.

---

## Revision History

| Date | Change |
|------|--------|
| Initial | Gap analysis: biograph-fh vs marley-develop (not in parity) |
| Jun 2026 | Implemented Marley parity on **biograph-fh**; preserved Biograph validation improvements |
| Jun 2026 | Same parity exercise applied to **biograph-insurance-v15**; added missing test modules |
| Jun 2026 | Report updated to reflect post-implementation state for both branches |
| Jun 2026 | GitNexus MCP re-verification added for **biograph-fh** and **biograph-insurance-v15** with `query/context/impact` evidence |
