/**
 * ABDM ABHA — all dialogs inline (no bundle dependency).
 * Changes take effect after `bench restart` only (no bench build needed).
 *
 * Dialogs defined here:
 *   healthcare.regional.india.abdm.AbhaVerifyDialog      — Verify / re-verify ABHA (ABDM → Verify ABHA)
 *   healthcare.regional.india.abdm.AbhaCreationDialog    — Create ABHA via Aadhaar or Mobile
 *   healthcare.regional.india.abdm.AbhaDlDialog          — Create ABHA via Driving Licence
 *   healthcare.regional.india.abdm.QRScannerDialog       — Show ABHA QR + Download Card
 *
 * Security constraints (preserved throughout):
 *   - IDOR guard via _assert_patient_permission on all backend calls
 *   - No PII in any log
 *   - Tokens stored as Password fields server-side
 *   - RSA encryption on all sensitive fields
 *   - Per-user rate limiting on OTP send/verify
 */

frappe.provide("healthcare.regional.india.abdm");

// ---------------------------------------------------------------------------
// M1-T86: client-side Verhoeff checksum — rejects a malformed/mistyped
// Aadhaar number before it ever leaves the browser. Mirrors the server-side
// check in healthcare.regional.india.abdm.api.enrol._verhoeff_validate
// (defence in depth, not a replacement for it).
// ---------------------------------------------------------------------------
const ABDM_VERHOEFF_D = [
	[0,1,2,3,4,5,6,7,8,9], [1,2,3,4,0,6,7,8,9,5], [2,3,4,0,1,7,8,9,5,6],
	[3,4,0,1,2,8,9,5,6,7], [4,0,1,2,3,9,5,6,7,8], [5,9,8,7,6,0,4,3,2,1],
	[6,5,9,8,7,1,0,4,3,2], [7,6,5,9,8,2,1,0,4,3], [8,7,6,5,9,3,2,1,0,4],
	[9,8,7,6,5,4,3,2,1,0],
];
const ABDM_VERHOEFF_P = [
	[0,1,2,3,4,5,6,7,8,9], [1,5,7,6,2,8,3,0,9,4], [5,8,0,3,7,9,6,1,4,2],
	[8,9,1,6,0,4,3,5,2,7], [9,4,5,3,1,2,6,8,7,0], [4,2,8,6,5,7,3,9,0,1],
	[2,7,9,3,8,0,6,4,1,5], [7,0,4,6,9,1,3,2,5,8],
];

function abdm_verhoeff_validate(number) {
	let c = 0;
	const digits = number.split("").reverse();
	for (let i = 0; i < digits.length; i++) {
		c = ABDM_VERHOEFF_D[c][ABDM_VERHOEFF_P[i % 8][parseInt(digits[i], 10)]];
	}
	return c === 0;
}

function abdm_validate_aadhaar_format(value) {
	// True only if it's 12 digits AND passes the Verhoeff checksum.
	return /^\d{12}$/.test(value) && abdm_verhoeff_validate(value);
}

// ===========================================================================
// AbhaVerifyDialog — Verify / Re-verify ABHA (Path 1: mobile/Aadhaar, Path 2: ABHA address)
// ===========================================================================
healthcare.regional.india.abdm.AbhaVerifyDialog = class AbhaVerifyDialog {
	constructor(frm) {
		this.frm     = frm;
		this.patient = frm.doc.name;
		this.mode    = "verify";

		this._method    = null;
		this._otpSystem = "abdm";
		this._txnId     = null;

		this.dialog = new frappe.ui.Dialog({
			title: __("ABHA — Verify"),
			size:  "regular",
		});
		this.$body = this.dialog.$body;
	}

	show() {
		this.dialog.show();
		this._renderTabs();
	}

	// ── Tab chrome ──────────────────────────────────────────────────────────

	_renderTabs() {
		this.$body.empty();
		this.$body.append(`
			<div class="abdm-tabs" style="display:flex;border-bottom:2px solid #e9ecef;margin-bottom:16px;">
				<button class="abdm-tab" data-mode="verify"
					style="flex:1;padding:8px;border:none;background:none;cursor:pointer;
					font-weight:${this.mode === "verify" ? "600" : "400"};
					color:${this.mode === "verify" ? "#2490ef" : "#6c757d"};
					border-bottom:${this.mode === "verify" ? "2px solid #2490ef" : "none"};">
					<i class="fa fa-shield"></i> ${__("Verify ABHA")}
				</button>
				<button class="abdm-tab" data-mode="profile"
					style="flex:1;padding:8px;border:none;background:none;cursor:pointer;
					font-weight:${this.mode === "profile" ? "600" : "400"};
					color:${this.mode === "profile" ? "#2490ef" : "#6c757d"};
					border-bottom:${this.mode === "profile" ? "2px solid #2490ef" : "none"};">
					<i class="fa fa-user"></i> ${__("ABHA Profile")}
				</button>
			</div>
			<div id="abdm-verify-content"></div>
		`);

		const self = this;
		this.$body.find(".abdm-tab").on("click", function () {
			const newMode = $(this).data("mode");
			if (newMode === self.mode) return;
			self.mode   = newMode;
			self._txnId = null;
			self._method = null;
			self._renderTabs();
		});

		if (this.mode === "verify") {
			this._renderMethodStep();
		} else {
			this._renderProfile();
		}
	}

	_content() { return this.$body.find("#abdm-verify-content"); }

	// ── Step 1: Method selection ─────────────────────────────────────────────

	_renderMethodStep() {
		this.dialog.set_title(__("Verify ABHA — Choose Method"));
		this._content().html(`
			<div class="abdm-step">
				<p class="text-muted" style="margin-bottom:16px;">
					${__("How would you like to verify this ABHA?")}
				</p>
				<div style="display:flex;flex-direction:column;gap:10px;margin-bottom:20px;">
					<label style="display:flex;align-items:flex-start;gap:10px;
						padding:12px;border:1px solid #e9ecef;border-radius:6px;cursor:pointer;">
						<input type="radio" name="abdm-method" value="mobile" checked style="margin-top:3px;">
						<div>
							<strong>${__("Mobile OTP")}</strong>
							<div class="text-muted" style="font-size:12px;">
								${__("OTP sent to the mobile number linked with this ABHA")}
							</div>
						</div>
					</label>
					<label style="display:flex;align-items:flex-start;gap:10px;
						padding:12px;border:1px solid #e9ecef;border-radius:6px;cursor:pointer;">
						<input type="radio" name="abdm-method" value="aadhaar" style="margin-top:3px;">
						<div>
							<strong>${__("Aadhaar OTP")}</strong>
							<div class="text-muted" style="font-size:12px;">
								${__("OTP from UIDAI sent to Aadhaar-linked mobile")}
							</div>
						</div>
					</label>
					<label style="display:flex;align-items:flex-start;gap:10px;
						padding:12px;border:1px solid #e9ecef;border-radius:6px;cursor:pointer;">
						<input type="radio" name="abdm-method" value="abha-number" style="margin-top:3px;">
						<div>
							<strong>${__("ABHA Number")}</strong>
							<div class="text-muted" style="font-size:12px;">
								${__("Enter the 14-digit ABHA number; OTP sent to the linked mobile")}
							</div>
						</div>
					</label>
					<label style="display:flex;align-items:flex-start;gap:10px;
						padding:12px;border:1px solid #e9ecef;border-radius:6px;cursor:pointer;">
						<input type="radio" name="abdm-method" value="abha_address" style="margin-top:3px;">
						<div>
							<strong>${__("ABHA Address")}</strong>
							<div class="text-muted" style="font-size:12px;">
								${__("Enter ABHA address (e.g. name@sbx or name@abdm)")}
							</div>
						</div>
					</label>
				</div>
				<div id="abdm-credential-wrap"></div>
				<div id="abdm-method-error" class="text-danger" style="display:none;margin-top:8px;"></div>
			</div>
		`);
		this._renderCredentialInput("mobile");
		this._content().on("change", "input[name=abdm-method]", (e) => {
			this._renderCredentialInput($(e.target).val());
		});
		this.dialog.set_primary_action(__("Send OTP"), () => this._submitMethodStep());
	}

	_renderCredentialInput(method) {
		const $wrap = this._content().find("#abdm-credential-wrap");
		if (method === "mobile") {
			$wrap.html(`
				<div class="form-group">
					<label>${__("Mobile Number")} <span class="req-star">*</span></label>
					<input id="abdm-credential" type="tel" class="form-control"
						placeholder="${__("10-digit mobile number")}"
						maxlength="10" inputmode="numeric" autocomplete="tel">
				</div>
			`);
		} else if (method === "aadhaar") {
			$wrap.html(`
				<div class="form-group">
					<label>${__("Aadhaar Number")} <span class="req-star">*</span></label>
					<input id="abdm-credential" type="tel" class="form-control"
						placeholder="${__("12-digit Aadhaar number")}"
						maxlength="12" inputmode="numeric" autocomplete="off">
				</div>
			`);
		} else if (method === "abha-number") {
			$wrap.html(`
				<div class="form-group">
					<label>${__("ABHA Number")} <span class="req-star">*</span></label>
					<input id="abdm-credential" type="text" class="form-control"
						placeholder="${__("14-digit ABHA number")}"
						maxlength="17" inputmode="numeric" autocomplete="off">
				</div>
			`);
		} else {
			$wrap.html(`
				<div class="form-group">
					<label>${__("ABHA Address")} <span class="req-star">*</span></label>
					<input id="abdm-credential" type="text" class="form-control"
						placeholder="name@sbx" autocomplete="off" autocapitalize="none">
				</div>
				<div class="form-group" style="margin-top:10px;">
					<label style="font-size:12px;font-weight:600;color:#6c757d;">${__("Deliver OTP via")}</label>
					<div style="display:flex;gap:20px;margin-top:6px;">
						<label style="display:flex;align-items:center;gap:6px;cursor:pointer;font-weight:normal;">
							<input type="radio" name="abdm-otp-system" value="abdm" checked>
							<span>${__("Mobile OTP")}</span>
						</label>
						<label style="display:flex;align-items:center;gap:6px;cursor:pointer;font-weight:normal;">
							<input type="radio" name="abdm-otp-system" value="aadhaar">
							<span>${__("Aadhaar OTP")}</span>
						</label>
					</div>
				</div>
			`);
		}
		setTimeout(() => this._content().find("#abdm-credential").focus(), 50);
	}

	_submitMethodStep() {
		const method     = this._content().find("input[name=abdm-method]:checked").val() || "mobile";
		const credential = (this._content().find("#abdm-credential").val() || "").trim();
		this._method     = method;

		if (method === "mobile" && !/^\d{10}$/.test(credential)) {
			this._content().find("#abdm-method-error").text(__("Enter a valid 10-digit mobile number.")).show();
			return;
		}
		if (method === "aadhaar" && !/^\d{12}$/.test(credential)) {
			this._content().find("#abdm-method-error").text(__("Enter a valid 12-digit Aadhaar number.")).show();
			return;
		}
		if (method === "aadhaar" && !abdm_verhoeff_validate(credential)) {
			this._content().find("#abdm-method-error").text(__("Invalid Aadhaar number. Please check and re-enter.")).show();
			return;
		}
		if (method === "abha-number" && !/^\d{14}$/.test(credential.replace(/-/g, ""))) {
			this._content().find("#abdm-method-error").text(__("Enter a valid 14-digit ABHA number.")).show();
			return;
		}
		if (method === "abha_address" && !credential.includes("@")) {
			this._content().find("#abdm-method-error").text(__("Enter a valid ABHA address (e.g. name@sbx).")).show();
			return;
		}

		this._setLoading(true, __("Sending OTP…"));

		if (method === "mobile" || method === "aadhaar" || method === "abha-number") {
			frappe.call({
				method:   "healthcare.regional.india.abdm.api.profile.request_abha_login_otp",
				args:     { patient: this.patient, login_id: credential, login_hint: method },
				callback: (r) => {
					this._setLoading(false);
					if (r.exc) { this._showApiError("#abdm-method-error", r); return; }
					if (!r.message) { this._content().find("#abdm-method-error").text(__("Failed to send OTP. Please try again.")).show(); return; }
					this._txnId = r.message.txnId;
					this._renderOtpStep();
				},
				error: (r) => { this._setLoading(false); this._showApiError("#abdm-method-error", r); },
			});
		} else {
			this._otpSystem = this._content().find("input[name=abdm-otp-system]:checked").val() || "abdm";
			frappe.call({
				method:   "healthcare.regional.india.abdm.api.profile.request_abha_address_otp",
				args:     { patient: this.patient, abha_address: credential, otp_system: this._otpSystem },
				callback: (r) => {
					this._setLoading(false);
					if (r.exc) { this._showApiError("#abdm-method-error", r); return; }
					if (!r.message) { this._content().find("#abdm-method-error").text(__("Failed to send OTP. Please try again.")).show(); return; }
					this._txnId = r.message.txnId;
					this._renderOtpStep();
				},
				error: (r) => { this._setLoading(false); this._showApiError("#abdm-method-error", r); },
			});
		}
	}

	// ── Step 2: OTP entry ────────────────────────────────────────────────────

	_renderOtpStep() {
		this.dialog.set_title(__("Verify ABHA — Enter OTP"));
		const otpDesc = this._method === "aadhaar"
			? __("Enter the 6-digit OTP sent to your Aadhaar-linked mobile by UIDAI.")
			: __("Enter the 6-digit OTP sent to your registered mobile.");

		this._content().html(`
			<div class="abdm-step">
				<p class="text-muted">${otpDesc}</p>
				<div class="form-group">
					<label>${__("OTP")} <span class="req-star">*</span></label>
					<input id="abdm-otp" type="text" class="form-control"
						placeholder="6-digit OTP" maxlength="6"
						inputmode="numeric" pattern="[0-9]*" autocomplete="one-time-code">
				</div>
				<a href="#" id="abdm-otp-back" style="font-size:12px;">← ${__("Change method")}</a>
				<div id="abdm-otp-error" class="text-danger" style="display:none;margin-top:8px;"></div>
			</div>
		`);
		this._content().find("#abdm-otp-back").on("click", (e) => {
			e.preventDefault();
			this._txnId  = null;
			this._method = null;
			this._renderMethodStep();
		});
		setTimeout(() => this._content().find("#abdm-otp").focus(), 50);
		this.dialog.set_primary_action(__("Verify & Fetch Profile"), () => this._submitOtpStep());
	}

	_submitOtpStep() {
		const otp = (this._content().find("#abdm-otp").val() || "").trim();
		if (!otp || otp.length !== 6 || !/^\d+$/.test(otp)) {
			this._content().find("#abdm-otp-error").text(__("Enter the 6-digit OTP.")).show();
			return;
		}
		this._setLoading(true, __("Verifying…"));

		if (this._method === "mobile" || this._method === "aadhaar" || this._method === "abha-number") {
			frappe.call({
				method:   "healthcare.regional.india.abdm.api.profile.verify_abha_login_otp",
				args:     { patient: this.patient, txn_id: this._txnId, otp, login_hint: this._method },
				callback: (r) => {
					this._setLoading(false);
					if (r.exc) { this._showApiError("#abdm-otp-error", r); return; }
					if (!r.message) { this._content().find("#abdm-otp-error").text(__("Verification failed. Please try again.")).show(); return; }
					this._onAbhaVerified(r.message);
				},
				error: (r) => { this._setLoading(false); this._showApiError("#abdm-otp-error", r); },
			});
		} else {
			frappe.call({
				method:   "healthcare.regional.india.abdm.api.profile.verify_abha_address_otp",
				args:     { patient: this.patient, txn_id: this._txnId, otp, otp_system: this._otpSystem || "abdm" },
				callback: (r) => {
					this._setLoading(false);
					if (r.exc) { this._showApiError("#abdm-otp-error", r); return; }
					if (!r.message) { this._content().find("#abdm-otp-error").text(__("Verification failed. Please try again.")).show(); return; }
					this._onAbhaVerified(r.message);
				},
				error: (r) => { this._setLoading(false); this._showApiError("#abdm-otp-error", r); },
			});
		}
	}

	// ── Profile tab ──────────────────────────────────────────────────────────

	_renderProfile() {
		this.dialog.set_title(__("ABHA Profile"));
		this.dialog.set_primary_action(__("Refresh from ABDM"), () => this._fetchAndShowProfile());
		this._content().html(`
			<div class="text-center" style="padding:20px;">
				<i class="fa fa-spinner fa-spin fa-2x text-muted"></i>
				<p class="text-muted" style="margin-top:8px;">${__("Loading profile…")}</p>
			</div>
		`);
		this._fetchAndShowProfile();
	}

	_fetchAndShowProfile() {
		this._content().html(`
			<div class="text-center" style="padding:20px;">
				<i class="fa fa-spinner fa-spin fa-2x text-muted"></i>
				<p class="text-muted" style="margin-top:8px;">${__("Loading…")}</p>
			</div>
		`);
		frappe.call({
			method:   "healthcare.regional.india.abdm.api.profile.get_abha_profile",
			args:     { patient: this.patient },
			callback: (r) => {
				if (r.exc || !r.message) {
					const msg = (r && _parse_server_msg(r)) || __("Could not load profile.");
					this._content().html(`<div class="text-danger" style="padding:16px;">${frappe.utils.escape_html(msg)}</div><p class="text-muted" style="font-size:12px;">${__("Use the <b>Verify ABHA</b> tab to authenticate first.")}</p>`);
					return;
				}
				const p = r.message;
				this._content().html(`
					<div style="display:flex;flex-direction:column;gap:12px;padding:8px 0;">
						${this._profileRow(__("ABHA Number"), p.abha_number)}
						${this._profileRow(__("ABHA Address"), p.abha_address)}
						${this._profileRow(__("Name"), p.name)}
						${this._profileRow(__("Gender"), p.gender)}
						${this._profileRow(__("Date of Birth"), p.dob)}
						${this._profileRow(__("Mobile"), p.mobile)}
						${this._profileRow(__("Status"), p.status)}
					</div>
					<hr>
					<button id="abdm-download-card" class="btn btn-default btn-sm">
						<i class="fa fa-download"></i> ${__("Download ABHA Card")}
					</button>
				`);
				this._content().find("#abdm-download-card").on("click", () => this._downloadCard());
			},
			error: (r) => {
				const msg = _parse_server_msg(r) || __("Could not load profile.");
				this._content().html(`
					<div class="text-danger" style="padding:16px;">
						${frappe.utils.escape_html(msg)}
					</div>
					<p class="text-muted" style="font-size:12px;">
						${__("Use the <b>Verify ABHA</b> tab to authenticate first.")}
					</p>
				`);
			},
		});
	}

	_profileRow(label, value) {
		if (!value) return "";
		return `
			<div style="display:flex;gap:8px;">
				<span class="text-muted" style="min-width:120px;font-size:12px;">${frappe.utils.escape_html(label)}</span>
				<strong>${frappe.utils.escape_html(String(value))}</strong>
			</div>
		`;
	}

	_downloadCard() {
		const btn = this._content().find("#abdm-download-card");
		btn.prop("disabled", true).html(`<i class="fa fa-spinner fa-spin"></i> ${__("Downloading…")}`);
		frappe.call({
			method:   "healthcare.regional.india.abdm.api.profile.download_abha_card",
			args:     { patient: this.patient },
			callback: (r) => {
				btn.prop("disabled", false).html(`<i class="fa fa-download"></i> ${__("Download ABHA Card")}`);
				if (r.exc || !r.message) return;
				const link = document.createElement("a");
				link.href     = `data:image/png;base64,${r.message.card_b64}`;
				link.download = `ABHA_Card_${this.patient}.png`;
				document.body.appendChild(link);
				link.click();
				document.body.removeChild(link);
				frappe.show_alert({ message: __("ABHA Card downloaded"), indicator: "green" });
			},
			error: () => {
				btn.prop("disabled", false).html(`<i class="fa fa-download"></i> ${__("Download ABHA Card")}`);
				frappe.show_alert({ message: __("Download failed. Try again."), indicator: "red" });
			},
		});
	}

	// ── Conclusion ────────────────────────────────────────────────────────────

	_onAbhaVerified(profile) {
		// The backend already wrote abha_number/abha_address/name/sex/dob/mobile
		// directly to this Patient record (frappe.db.set_value, inside the verify
		// call, before this callback runs) — see _sync_abha_fields_to_patient /
		// _sync_abha_profile_to_patient. Re-applying the same fields here via
		// frm.set_value()+frm.save() is redundant AND races against that backend
		// write: the form's in-memory `modified` timestamp is now stale relative
		// to the DB, so frm.save() reliably throws "has been modified after you
		// opened it". Reload instead — no save, no race, and it picks up exactly
		// what the backend already persisted.
		const frm = this.frm;
		this.dialog.hide();
		frappe.show_alert({ message: __("ABHA verified. Patient record updated from ABDM."), indicator: "green" }, 6);
		if (frm && !frm.is_new()) frm.reload_doc();
	}

	// ── Helpers ───────────────────────────────────────────────────────────────

	_showApiError(selector, r) {
		let msg;
		try { msg = JSON.parse(r._server_messages || "[]")[0]?.message; } catch (_) {}
		this._content().find(selector).text(msg || __("An error occurred. Please try again.")).show();
	}

	_setLoading(on, text) {
		const btn = this.dialog.get_primary_btn();
		if (on) btn.prop("disabled", true).html(`<i class="fa fa-spinner fa-spin"></i> ${text || __("Please wait…")}`);
		else    btn.prop("disabled", false);
	}
};


// ===========================================================================
// AbhaCreationDialog — Create ABHA via Aadhaar or Mobile (SOP §3)
// ===========================================================================
healthcare.regional.india.abdm.AbhaCreationDialog = class AbhaCreationDialog {
	constructor(patient) {
		this.patient         = patient;
		this.txnId           = null;
		this.abhaNumber      = null;
		this.abhaAddress     = null;
		this.mode            = "aadhaar";
		this._abhaAddrSuffix = "@abdm";  // updated from ABDM suggestion list; @sbx on sandbox

		this._stepMeta = {
			aadhaar: { total: 6, labels: ["Aadhaar", "OTP", "Mobile OTP", "Email", "Address", "Done"] },
			mobile:  { total: 4, labels: ["Mobile", "OTP", "Address", "Done"] },
		};

		this.dialog = new frappe.ui.Dialog({
			title: __("Create ABHA (Ayushman Bharat Health Account)"),
			size:  "large",
		});
		this._renderModeSelector();
	}

	_renderModeSelector() {
		const $b = this.dialog.$body;
		$b.empty();
		$b.append(`
			<div class="abdm-tabs" style="display:flex;border-bottom:2px solid #e9ecef;margin-bottom:16px;">
				<button class="abdm-tab" data-mode="aadhaar"
					style="flex:1;padding:8px;border:none;background:none;cursor:pointer;
					font-weight:${this.mode === "aadhaar" ? "600" : "400"};
					color:${this.mode === "aadhaar" ? "#2490ef" : "#6c757d"};
					border-bottom:${this.mode === "aadhaar" ? "2px solid #2490ef" : "none"};">
					<i class="fa fa-id-card"></i> ${__("Aadhaar")}
				</button>
				<button class="abdm-tab" data-mode="mobile"
					style="flex:1;padding:8px;border:none;background:none;cursor:pointer;
					font-weight:${this.mode === "mobile" ? "600" : "400"};
					color:${this.mode === "mobile" ? "#2490ef" : "#6c757d"};
					border-bottom:${this.mode === "mobile" ? "2px solid #2490ef" : "none"};">
					<i class="fa fa-mobile"></i> ${__("Mobile")}
				</button>
			</div>
			<div id="abdm-create-content"></div>
		`);
		const self = this;
		$b.find(".abdm-tab").on("click", function () {
			const newMode = $(this).data("mode");
			if (newMode === self.mode) return;
			self.mode = newMode; self.txnId = null;
			self._renderModeSelector();
		});
		this._renderStep(1);
		this.dialog.show();
	}

	_content() { return this.dialog.$body.find("#abdm-create-content"); }

	_renderStep(step) {
		this.currentStep = step;
		const meta = this._stepMeta[this.mode];
		this._content().empty();
		this._renderProgressBar(step, meta.total, meta.labels[step - 1]);
		this.dialog.get_primary_btn().prop("disabled", false);
		const route = this.mode === "aadhaar"
			? [null, "_A1", "_A2", "_A3", "_A4", "_A5", "_A6"]
			: [null, "_M1", "_M2", "_M3", "_M4"];
		if (route[step]) this[route[step]]();
	}

	_renderProgressBar(step, total, label) {
		const pct = Math.round(step / total * 100);
		this._content().prepend(`
			<div style="margin-bottom:12px;">
				<div style="display:flex;justify-content:space-between;font-size:11px;color:#8d99ae;margin-bottom:4px;">
					<span>${__("Step")} ${step} ${__("of")} ${total}: <strong>${__(label)}</strong></span>
					<span>${pct}%</span>
				</div>
				<div style="background:#e9ecef;border-radius:4px;height:6px;">
					<div style="background:#2490ef;border-radius:4px;height:6px;width:${pct}%;transition:width .3s;"></div>
				</div>
			</div>
		`);
	}

	_appendStep(html) { this._content().append(html); }

	// ── Aadhaar flow ─────────────────────────────────────────────────────────

	_A1() {
		this._appendStep(`
			<div class="form-group">
				<label>${__("Aadhaar Number")} <span class="req-star">*</span></label>
				<input id="abdm-aadhaar" type="password" class="form-control"
					placeholder="${__("12-digit Aadhaar")}" maxlength="12"
					autocomplete="off" inputmode="numeric">
				<small class="text-muted">${__("Encrypted before transmission.")}</small>
			</div>
			<div id="abdm-a1-error" class="text-danger" style="display:none;margin-top:8px;"></div>
		`);
		this.dialog.set_primary_action(__("Send OTP"), () => {
			const v = $("#abdm-aadhaar").val().trim();
			if (!v || v.length !== 12 || !/^\d+$/.test(v)) {
				$("#abdm-a1-error").text(__("Enter a valid 12-digit Aadhaar.")).show(); return;
			}
			if (!abdm_verhoeff_validate(v)) {
				$("#abdm-a1-error").text(__("Invalid Aadhaar number. Please check and re-enter.")).show(); return;
			}
			this._setLoading(true, __("Sending OTP…"));
			// Safety net: unblock UI if ABDM takes >25s (e.g. UIDAI slow or sandbox down)
			const _a1Timeout = setTimeout(() => {
				this._setLoading(false);
				this._err("abdm-a1-error", null,
					__("ABDM is taking too long to respond. Please try again in a moment."));
			}, 25000);
			frappe.call({
				method: "healthcare.regional.india.abdm.api.enrol.generate_aadhaar_otp",
				args: { patient: this.patient, aadhaar: v },
				callback: (r) => {
					clearTimeout(_a1Timeout);
					$("#abdm-aadhaar").val("");
					this._setLoading(false);
					if (r.exc) { this._err("abdm-a1-error", r); return; }
					if (!r.message) {
						this._err("abdm-a1-error", null, __("OTP could not be sent. Check ABDM V3 Settings and try again."));
						return;
					}
					this.txnId = r.message.txnId;
					frappe.show_alert({ message: __("OTP sent to your Aadhaar-linked mobile."), indicator: "green" }, 4);
					this._renderStep(2);
				},
				error: (r) => { clearTimeout(_a1Timeout); $("#abdm-aadhaar").val(""); this._setLoading(false); this._err("abdm-a1-error", r); },
			});
		});
	}

	_A2() {
		// V3 SOP §3 Step 4: user must supply their mobile alongside the OTP.
		// ABDM uses it to auto-link if it matches the Aadhaar-linked mobile,
		// or triggers a separate mobile OTP (step A3) if it differs.
		this._appendStep(`
			<p class="text-muted">${__("Enter the OTP sent to your Aadhaar-linked mobile and your mobile number.")}</p>
			<div class="form-group">
				<label>${__("OTP")} <span class="req-star">*</span></label>
				<input id="abdm-otp" type="text" class="form-control"
					placeholder="6-digit OTP" maxlength="6" inputmode="numeric" autocomplete="one-time-code">
			</div>
			<div class="form-group" style="margin-top:10px;">
				<label>${__("Your Mobile Number")} <span class="req-star">*</span></label>
				<div class="input-group">
					<div class="input-group-prepend"><span class="input-group-text">+91</span></div>
					<input id="abdm-enrol-mobile" type="tel" class="form-control"
						placeholder="10-digit mobile" maxlength="10" inputmode="numeric" autocomplete="tel">
				</div>
				<small class="text-muted">${__("Must match the mobile linked to your Aadhaar for auto-link, or enter a different number to link via OTP.")}</small>
			</div>
			<a href="#" id="abdm-resend">${__("Resend OTP")}</a>
			<div id="abdm-a2-error" class="text-danger" style="display:none;margin-top:8px;"></div>
		`);
		setTimeout(() => this._content().find("#abdm-otp").focus(), 50);
		$("#abdm-resend").on("click", (e) => {
			e.preventDefault();
			frappe.call({ method: "healthcare.regional.india.abdm.api.enrol.resend_aadhaar_otp",
				args: { patient: this.patient, txn_id: this.txnId },
				callback: () => frappe.show_alert({ message: __("OTP resent"), indicator: "green" }) });
		});
		this.dialog.set_primary_action(__("Verify & Enrol"), () => {
			const otp    = $("#abdm-otp").val().trim();
			const mobile = $("#abdm-enrol-mobile").val().trim();
			if (!otp || otp.length !== 6 || !/^\d+$/.test(otp)) {
				$("#abdm-a2-error").text(__("Enter the 6-digit OTP.")).show(); return;
			}
			if (!mobile || mobile.length !== 10 || !/^\d+$/.test(mobile)) {
				$("#abdm-a2-error").text(__("Enter a valid 10-digit mobile number.")).show(); return;
			}
			this._enrollMobile = mobile;  // store for step A3
			this._setLoading(true, __("Creating ABHA…"));
			frappe.call({
				method: "healthcare.regional.india.abdm.api.enrol.enrol_by_aadhaar",
				args: { patient: this.patient, txn_id: this.txnId, otp, mobile },
				callback: (r) => {
					this._setLoading(false);
					if (r.exc) { this._err("abdm-a2-error", r); return; }
					if (!r.message) { this._err("abdm-a2-error", null, __("Enrolment failed. Please try again.")); return; }
					this.abhaNumber = r.message.abha_number;
					if (cur_frm && cur_frm.doctype === "Patient" && cur_frm.doc.name === this.patient) {
						if (r.message.abha_number) cur_frm.set_value("abha_number", r.message.abha_number);
					}
					// Skip mobile OTP step if ABDM already auto-linked the mobile
					if (r.message.mobile_linked) {
						this._renderStep(4);   // jump to email step
					} else {
						this._renderStep(3);   // mobile OTP needed
					}
				},
				error: (r) => { this._setLoading(false); this._err("abdm-a2-error", r); },
			});
		});
	}

	_A3() {
		this._mobileVerifyTxnId = null; // reset sub-txnId tracker each time step renders
		this._appendStep(`
			<p class="text-muted" id="abdm-a3-desc">${__("Sending OTP to your Aadhaar-linked mobile…")}</p>
			<div class="form-group">
				<label>${__("Mobile OTP")} <span class="req-star">*</span></label>
				<input id="abdm-motp" type="text" class="form-control"
					placeholder="6-digit OTP" maxlength="6" inputmode="numeric" autocomplete="one-time-code">
			</div>
			<div id="abdm-a3-error" class="text-danger" style="display:none;margin-top:8px;"></div>
		`);
		this.dialog.set_primary_action(__("Verify Mobile"), () => {
			const otp = $("#abdm-motp").val().trim();
			if (!otp || otp.length !== 6 || !/^\d+$/.test(otp)) {
				$("#abdm-a3-error").text(__("Enter the 6-digit OTP.")).show(); return;
			}
			this._setLoading(true, __("Verifying…"));
			frappe.call({
				method: "healthcare.regional.india.abdm.api.enrol.verify_mobile_otp",
				args: { patient: this.patient, txn_id: this._mobileVerifyTxnId || this.txnId, otp },
				callback: (r) => {
					this._setLoading(false);
					if (r.exc) { this._err("abdm-a3-error", r); return; }
					this._renderStep(4);
				},
				error: (r) => { this._setLoading(false); this._err("abdm-a3-error", r); },
			});
		});
		// Auto-send mobile OTP; disable Verify until the sub-txnId it depends on
		// arrives — submitting before this resolves would silently fall back to
		// the wrong txnId (enrollment txnId instead of the mobile-verify one),
		// which is exactly what causes ABDM's HV000028 error.
		this._setLoading(true, __("Sending OTP…"));
		frappe.call({
			method: "healthcare.regional.india.abdm.api.enrol.send_mobile_otp",
			args:   { patient: this.patient, txn_id: this.txnId, mobile: this._enrollMobile || "" },
			callback: (r) => {
				this._setLoading(false);
				if (r.exc) {
					const msg = _parse_server_msg(r) || __("Could not send mobile OTP.");
					$("#abdm-a3-desc").text(__("Mobile OTP could not be sent. If your mobile is already linked to an ABHA, you may skip this step."));
					$("#abdm-a3-error").text(msg).show();
					// Add skip button if not already present
					if (!$("#abdm-a3-skip").length) {
						$("#abdm-a3-error").after(
							`<button id="abdm-a3-skip" class="btn btn-sm btn-default" style="margin-top:8px;">
								${__("Skip Mobile Verification →")}
							</button>`
						);
						$("#abdm-a3-skip").on("click", () => this._renderStep(4));
					}
				} else {
					// Capture the mobile-verify sub-txnId — this is what auth/byAbdm needs.
					// Using the enrollment txnId here causes ABDM to return no JWT → HV000028.
					if (r.message && r.message.txnId) this._mobileVerifyTxnId = r.message.txnId;
					$("#abdm-a3-desc").text(__("Enter the OTP sent to your Aadhaar-linked mobile."));
				}
			},
			error: () => {
				this._setLoading(false);
				$("#abdm-a3-desc").text(__("Mobile OTP could not be sent. You may skip this step and continue."));
				if (!$("#abdm-a3-skip").length) {
					$("#abdm-a3-error").after(
						`<button id="abdm-a3-skip" class="btn btn-sm btn-default" style="margin-top:8px;">
							${__("Skip Mobile Verification →")}
						</button>`
					);
					$("#abdm-a3-skip").on("click", () => this._renderStep(4));
				}
			},
		});
	}

	_A4() {
		this._appendStep(`
			<p class="text-muted">${__("Link an email to your ABHA. This step is optional.")}</p>
			<div class="form-group">
				<label>${__("Email Address")}</label>
				<input id="abdm-email" type="email" class="form-control" placeholder="${__("optional")}">
			</div>
		`);
		this.dialog.set_primary_action(__("Skip →"), () => {
			frappe.call({ method: "healthcare.regional.india.abdm.api.enrol.skip_email_verification",
				args: { patient: this.patient, txn_id: this.txnId || "" } });
			this._renderStep(5);
		});
	}

	_A5() {
		this._appendStep(this._addressHTML("abdm-a5-error"));
		this.dialog.set_primary_action(__("Confirm Address"), () => this._submitAddress(5, 6));
		this._loadSuggestions();
	}

	_A6() { this._renderSuccess(); }

	// ── Mobile flow ───────────────────────────────────────────────────────────

	_M1() {
		this._appendStep(`
			<p class="text-muted">${__("Enter the mobile number to create ABHA without Aadhaar.")}</p>
			<div class="form-group">
				<label>${__("Mobile Number")} <span class="req-star">*</span></label>
				<div class="input-group">
					<div class="input-group-prepend"><span class="input-group-text">+91</span></div>
					<input id="abdm-mobile" type="tel" class="form-control"
						placeholder="10-digit mobile" maxlength="10" inputmode="numeric" autocomplete="tel">
				</div>
			</div>
			<div id="abdm-m1-error" class="text-danger" style="display:none;margin-top:8px;"></div>
		`);
		this.dialog.set_primary_action(__("Send OTP"), () => {
			const v = $("#abdm-mobile").val().trim();
			if (!v || v.length !== 10 || !/^\d+$/.test(v)) {
				$("#abdm-m1-error").text(__("Enter a valid 10-digit mobile number.")).show(); return;
			}
			this._setLoading(true, __("Sending OTP…"));
			const _m1Timeout = setTimeout(() => {
				this._setLoading(false);
				this._err("abdm-m1-error", null,
					__("ABDM is taking too long to respond. Please try again in a moment."));
			}, 25000);
			frappe.call({
				method: "healthcare.regional.india.abdm.api.enrol.generate_mobile_otp",
				args: { patient: this.patient, mobile: v },
				callback: (r) => {
					clearTimeout(_m1Timeout);
					this._setLoading(false);
					if (r.exc) { this._err("abdm-m1-error", r); return; }
					if (!r.message) {
						this._err("abdm-m1-error", null, __("OTP could not be sent. Check ABDM V3 Settings and try again."));
						return;
					}
					this.txnId = r.message.txnId;
					frappe.show_alert({ message: __("OTP sent to your mobile number."), indicator: "green" }, 4);
					this._renderStep(2);
				},
				error: (r) => { clearTimeout(_m1Timeout); this._setLoading(false); this._err("abdm-m1-error", r); },
			});
		});
	}

	_M2() {
		this._appendStep(`
			<p class="text-muted">${__("Enter the OTP sent to your mobile number.")}</p>
			<div class="form-group">
				<label>${__("OTP")} <span class="req-star">*</span></label>
				<input id="abdm-m-otp" type="text" class="form-control"
					placeholder="6-digit OTP" maxlength="6" inputmode="numeric" autocomplete="one-time-code">
			</div>
			<div id="abdm-m2-error" class="text-danger" style="display:none;margin-top:8px;"></div>
		`);
		setTimeout(() => this._content().find("#abdm-m-otp").focus(), 50);
		this.dialog.set_primary_action(__("Verify & Continue"), () => {
			const otp = $("#abdm-m-otp").val().trim();
			if (!otp || otp.length !== 6 || !/^\d+$/.test(otp)) {
				$("#abdm-m2-error").text(__("Enter the 6-digit OTP.")).show(); return;
			}
			this._setLoading(true, __("Verifying…"));
			frappe.call({
				method: "healthcare.regional.india.abdm.api.enrol.verify_mobile_otp_enrol",
				args: { patient: this.patient, txn_id: this.txnId, otp },
				callback: (r) => {
					this._setLoading(false);
					if (r.exc) { this._err("abdm-m2-error", r); return; }
					if (!r.message) { this._err("abdm-m2-error", null, __("Verification failed. Please try again.")); return; }
					if (r.message.txnId) this.txnId = r.message.txnId;
					this._renderStep(3);
				},
				error: (r) => { this._setLoading(false); this._err("abdm-m2-error", r); },
			});
		});
	}

	_M3() {
		this._appendStep(this._addressHTML("abdm-m3-error"));
		this.dialog.set_primary_action(__("Confirm Address"), () => this._submitAddress(3, 4));
		this._loadSuggestions();
	}

	_M4() { this._renderSuccess(); }

	// ── Shared: address step ─────────────────────────────────────────────────

	_addressHTML(errorId) {
		return `
			<p class="text-muted">${__("Your ABHA address is how others share records with you.")}</p>
			<div id="abdm-suggestions-wrap">
				<p class="text-muted"><i class="fa fa-spinner fa-spin"></i> ${__("Loading suggestions…")}</p>
			</div>
			<div class="form-group" style="margin-top:12px;">
				<label>${__("Or enter a custom address")}</label>
				<div class="input-group">
					<input id="abdm-custom-addr" type="text" class="form-control"
						placeholder="yourname" autocomplete="off">
					<div class="input-group-append">
						<span class="input-group-text" id="abdm-addr-suffix">${this._abhaAddrSuffix}</span>
					</div>
				</div>
			</div>
			<div id="${errorId}" class="text-danger" style="display:none;margin-top:8px;"></div>
		`;
	}

	_loadSuggestions() {
		frappe.call({
			method: "healthcare.regional.india.abdm.api.enrol.get_abha_suggestions",
			args: { patient: this.patient },
			callback: (r) => {
				const wrap = $("#abdm-suggestions-wrap");
				const sugs = (r.message && r.message.suggestions) || [];
				if (sugs.length) {
					// Detect environment suffix from what ABDM returned (@sbx on sandbox, @abdm on prod)
					const firstSuf = (sugs[0].match(/@(sbx|abdm)$/) || [])[0];
					if (firstSuf) {
						this._abhaAddrSuffix = firstSuf;
						$("#abdm-addr-suffix").text(firstSuf);
					}
				}
				if (!sugs.length) { wrap.html(`<p class="text-muted">${__("No suggestions. Enter a custom address.")}</p>`); return; }
				wrap.html(`<label>${__("Suggestions")}</label><div>${
					sugs.map(s => `<button class="btn btn-sm btn-default abdm-suggest-btn"
						style="margin:3px;border-radius:20px;" data-addr="${frappe.utils.escape_html(s)}">
						${frappe.utils.escape_html(s)}</button>`).join("")
				}</div>`);
				// When a suggestion is clicked, populate the custom input with just the local part
				const self = this;
				$(".abdm-suggest-btn").on("click", function () {
					const full = $(this).data("addr");
					// Extract suffix (@sbx/@abdm) and local part
					const match = full.match(/^(.+?)(@(?:sbx|abdm))$/);
					const local = match ? match[1] : full;
					const suffix = match ? match[2] : self._abhaAddrSuffix;
					self._abhaAddrSuffix = suffix;
					$("#abdm-addr-suffix").text(suffix);
					$("#abdm-custom-addr").val(local);
					$(".abdm-suggest-btn").removeClass("btn-primary").addClass("btn-default");
					$(this).removeClass("btn-default").addClass("btn-primary");
				});
			},
		});
	}

	_submitAddress(currentStep, nextStep) {
		let addr = $("#abdm-custom-addr").val().trim();
		if (!addr) {
			const sel = $(".abdm-suggest-btn.btn-primary").data("addr");
			if (sel) {
				// Strip existing suffix — will re-attach with the correct one below
				addr = sel.replace(/@(abdm|sbx)$/, "");
			}
		}
		const errorId = currentStep === 5 ? "abdm-a5-error" : "abdm-m3-error";
		if (!addr) { $(`#${errorId}`).text(__("Select or enter an ABHA address.")).show(); return; }
		// Use the detected suffix (e.g. @sbx on sandbox), not a hardcoded @abdm
		const fullAddr = addr.includes("@") ? addr : `${addr}${this._abhaAddrSuffix}`;
		this._setLoading(true, __("Setting address…"));
		frappe.call({
			method: "healthcare.regional.india.abdm.api.enrol.set_abha_address",
			args: { patient: this.patient, abha_address: fullAddr },
			callback: (r) => {
				this._setLoading(false);
				if (r.exc) { this._err(errorId, r); return; }
				if (!r.message) { this._err(errorId, null, __("Could not set ABHA address. Please try again.")); return; }
				this.abhaAddress = fullAddr;
				this._renderStep(nextStep);
			},
			error: (r) => { this._setLoading(false); this._err(errorId, r); },
		});
	}

	// ── Success ───────────────────────────────────────────────────────────────

	_renderSuccess() {
		this._appendStep(`
			<div class="text-center" style="padding:24px 0;">
				<div style="font-size:48px;color:#28a745;">✓</div>
				<h4 style="margin:12px 0 4px;">${__("ABHA Created!")}</h4>
				<p class="text-muted">${__("Your Ayushman Bharat Health Account is now active.")}</p>
				<div style="background:#f8f9fa;border-radius:8px;padding:16px;margin:16px 0;text-align:left;">
					${this.abhaNumber ? `<div style="margin-bottom:8px;">
						<span class="text-muted" style="font-size:11px;">${__("ABHA Number")}</span><br>
						<strong>${frappe.utils.escape_html(this.abhaNumber)}</strong></div>` : ""}
					<div>
						<span class="text-muted" style="font-size:11px;">${__("ABHA Address")}</span><br>
						<strong style="color:#2490ef;">${frappe.utils.escape_html(this.abhaAddress || "—")}</strong>
					</div>
				</div>
			</div>
		`);
		this.dialog.set_primary_action(__("Done"), () => {
			this.dialog.hide();
			if (cur_frm && cur_frm.doctype === "Patient" && cur_frm.doc.name === this.patient) {
				// Set known fields immediately so the badge/fields update before reload
				if (this.abhaNumber) cur_frm.set_value("abha_number", this.abhaNumber);
				if (this.abhaAddress) cur_frm.set_value("abha_address", this.abhaAddress);
				cur_frm.reload_doc();
			}
		});
	}

	// ── Helpers ───────────────────────────────────────────────────────────────

	_err(domId, r, fallback) {
		const msg = (r && _parse_server_msg(r)) || fallback || __("An error occurred. Please try again.");
		$(`#${domId}`).text(msg).show();
	}

	_setLoading(on, text) {
		const btn = this.dialog.get_primary_btn();
		if (on) {
			this._savedBtnLabel = btn.text().trim() || null;
			btn.prop("disabled", true).html(`<i class="fa fa-spinner fa-spin"></i> ${text || __("Please wait…")}`);
		} else {
			btn.prop("disabled", false);
			if (this._savedBtnLabel) { btn.text(this._savedBtnLabel); this._savedBtnLabel = null; }
		}
	}
};

healthcare.regional.india.abdm.show_abha_creation_dialog = function (patient) {
	return new healthcare.regional.india.abdm.AbhaCreationDialog(patient);
};


// ===========================================================================
// AbhaDlDialog — Create ABHA via Driving Licence (SOP §4)
// ===========================================================================
healthcare.regional.india.abdm.AbhaDlDialog = class AbhaDlDialog {
	constructor(patient) {
		this.patient     = patient;
		this.txnId       = null;
		this.abhaNumber  = null;
		this.abhaAddress = null;
		this.totalSteps  = 4;

		this.dialog = new frappe.ui.Dialog({
			title: __("Create ABHA via Driving Licence"),
			size:  "large",
		});
		this._renderStep(1);
	}

	_renderStep(step) {
		this.currentStep = step;
		const $b = this.dialog.$body;
		$b.empty();
		this.dialog.get_primary_btn().prop("disabled", false);
		const pct    = Math.round(step / this.totalSteps * 100);
		const labels = ["Mobile OTP", "Verify OTP", "DL Details", "Done"];
		$b.append(`
			<div style="margin-bottom:16px;">
				<div style="display:flex;justify-content:space-between;font-size:11px;color:#8d99ae;margin-bottom:4px;">
					<span>${__("Step")} ${step} ${__("of")} ${this.totalSteps}: <strong>${__(labels[step-1])}</strong></span>
					<span>${pct}%</span>
				</div>
				<div style="background:#e9ecef;border-radius:4px;height:6px;">
					<div style="background:#e67e22;border-radius:4px;height:6px;width:${pct}%;transition:width .3s;"></div>
				</div>
			</div>
		`);
		({ 1: () => this._step1(), 2: () => this._step2(), 3: () => this._step3(), 4: () => this._step4() }[step] || (() => {}))();
		this.dialog.show();
	}

	_step1() {
		this.dialog.$body.append(`
			<p class="text-muted">${__("To create ABHA via Driving Licence, first verify your mobile number.")}</p>
			<div class="form-group">
				<label>${__("Mobile Number")} <span class="req-star">*</span></label>
				<div class="input-group">
					<div class="input-group-prepend"><span class="input-group-text">+91</span></div>
					<input id="dl-mobile" type="tel" class="form-control" placeholder="10-digit mobile"
						maxlength="10" inputmode="numeric" autocomplete="tel">
				</div>
			</div>
			<div id="dl-s1-error" class="text-danger" style="display:none;margin-top:8px;"></div>
		`);
		this.dialog.set_primary_action(__("Send OTP"), () => {
			const v = $("#dl-mobile").val().trim();
			if (!v || v.length !== 10 || !/^\d+$/.test(v)) {
				$("#dl-s1-error").text(__("Enter a valid 10-digit mobile number.")).show(); return;
			}
			this._setLoading(true, __("Sending OTP…"));
			frappe.call({
				method: "healthcare.regional.india.abdm.api.enrol.generate_dl_otp",
				args: { patient: this.patient, mobile: v },
				callback: (r) => {
					this._setLoading(false);
					if (r.exc) { this._err("dl-s1-error", r); return; }
					if (!r.message) { this._err("dl-s1-error", null, __("OTP could not be sent. Please try again.")); return; }
					this.txnId = r.message.txnId;
					this._renderStep(2);
				},
				error: (r) => { this._setLoading(false); this._err("dl-s1-error", r); },
			});
		});
	}

	_step2() {
		this.dialog.$body.append(`
			<p class="text-muted">${__("Enter the OTP sent to your mobile number.")}</p>
			<div class="form-group">
				<label>${__("OTP")} <span class="req-star">*</span></label>
				<input id="dl-otp" type="text" class="form-control"
					placeholder="6-digit OTP" maxlength="6" inputmode="numeric" autocomplete="one-time-code">
			</div>
			<div id="dl-s2-error" class="text-danger" style="display:none;margin-top:8px;"></div>
		`);
		this.dialog.set_primary_action(__("Verify OTP"), () => {
			const otp = $("#dl-otp").val().trim();
			if (!otp || otp.length !== 6 || !/^\d+$/.test(otp)) {
				$("#dl-s2-error").text(__("Enter the 6-digit OTP.")).show(); return;
			}
			this._setLoading(true, __("Verifying…"));
			frappe.call({
				method: "healthcare.regional.india.abdm.api.enrol.verify_dl_otp",
				args: { patient: this.patient, txn_id: this.txnId, otp },
				callback: (r) => {
					this._setLoading(false);
					if (r.exc) { this._err("dl-s2-error", r); return; }
					if (!r.message) { this._err("dl-s2-error", null, __("Verification failed. Please try again.")); return; }
					if (r.message.txnId) this.txnId = r.message.txnId;
					this._renderStep(3);
				},
				error: (r) => { this._setLoading(false); this._err("dl-s2-error", r); },
			});
		});
	}

	_step3() {
		this.dialog.$body.append(`
			<p class="text-muted">${__("Enter your Driving Licence details exactly as they appear on your card.")}</p>
			<div class="row">
				<div class="col-sm-6">
					<div class="form-group">
						<label>${__("DL Number")} <span class="req-star">*</span></label>
						<input id="dl-number" type="text" class="form-control" placeholder="e.g. MH0120210001234" maxlength="20">
					</div>
				</div>
				<div class="col-sm-6">
					<div class="form-group">
						<label>${__("Date of Birth")} <span class="req-star">*</span></label>
						<input id="dl-dob" type="date" class="form-control">
					</div>
				</div>
			</div>
			<div class="row">
				<div class="col-sm-4">
					<div class="form-group"><label>${__("First Name")} <span class="req-star">*</span></label>
						<input id="dl-fname" type="text" class="form-control"></div>
				</div>
				<div class="col-sm-4">
					<div class="form-group"><label>${__("Middle Name")}</label>
						<input id="dl-mname" type="text" class="form-control"></div>
				</div>
				<div class="col-sm-4">
					<div class="form-group"><label>${__("Last Name")}</label>
						<input id="dl-lname" type="text" class="form-control"></div>
				</div>
			</div>
			<div class="row">
				<div class="col-sm-6">
					<div class="form-group"><label>${__("Gender")} <span class="req-star">*</span></label>
						<select id="dl-gender" class="form-control">
							<option value="">${__("Select")}</option>
							<option value="M">${__("Male")}</option>
							<option value="F">${__("Female")}</option>
							<option value="O">${__("Other")}</option>
						</select></div>
				</div>
				<div class="col-sm-6">
					<div class="form-group"><label>${__("Pin Code")}</label>
						<input id="dl-pincode" type="text" class="form-control" maxlength="6" inputmode="numeric"></div>
				</div>
			</div>
			<div class="form-group"><label>${__("Address")}</label>
				<input id="dl-address" type="text" class="form-control"></div>
			<div class="row">
				<div class="col-sm-6">
					<div class="form-group"><label>${__("State")}</label>
						<input id="dl-state" type="text" class="form-control"></div>
				</div>
				<div class="col-sm-6">
					<div class="form-group"><label>${__("District")}</label>
						<input id="dl-district" type="text" class="form-control"></div>
				</div>
			</div>
			<div class="row" style="margin-top:8px;">
				<div class="col-sm-6">
					<div class="form-group"><label>${__("Front photo (optional)")}</label>
						<input id="dl-front-photo" type="file" class="form-control-file" accept="image/jpeg,image/png">
						<small class="text-muted">${__("Max 150 KB.")}</small></div>
				</div>
				<div class="col-sm-6">
					<div class="form-group"><label>${__("Back photo (optional)")}</label>
						<input id="dl-back-photo" type="file" class="form-control-file" accept="image/jpeg,image/png"></div>
				</div>
			</div>
			<div id="dl-s3-error" class="text-danger" style="display:none;margin-top:8px;"></div>
		`);
		this.dialog.set_primary_action(__("Submit"), () => this._submitDL());
	}

	async _submitDL() {
		const dlNum  = $("#dl-number").val().trim();
		const dob    = $("#dl-dob").val().trim();
		const fname  = $("#dl-fname").val().trim();
		const gender = $("#dl-gender").val();
		if (!dlNum)  { this._err("dl-s3-error", null, __("DL Number is required.")); return; }
		if (!dob)    { this._err("dl-s3-error", null, __("Date of Birth is required.")); return; }
		if (!fname)  { this._err("dl-s3-error", null, __("First Name is required.")); return; }
		if (!gender) { this._err("dl-s3-error", null, __("Gender is required.")); return; }
		this._setLoading(true, __("Uploading…"));
		const frontPhoto = await this._readFileAsBase64(document.getElementById("dl-front-photo"));
		const backPhoto  = await this._readFileAsBase64(document.getElementById("dl-back-photo"));
		frappe.call({
			method: "healthcare.regional.india.abdm.api.enrol.enrol_by_dl",
			args: { patient: this.patient, txn_id: this.txnId, dl_data: JSON.stringify({
				documentId: dlNum, firstName: fname, middleName: $("#dl-mname").val().trim(),
				lastName: $("#dl-lname").val().trim(), dob, gender,
				address: $("#dl-address").val().trim(), state: $("#dl-state").val().trim(),
				district: $("#dl-district").val().trim(), pinCode: $("#dl-pincode").val().trim(),
				frontSidePhoto: frontPhoto || "", backSidePhoto: backPhoto || "",
			}) },
			callback: (r) => {
				this._setLoading(false);
				if (r.exc) { this._err("dl-s3-error", r); return; }
				if (!r.message) { this._err("dl-s3-error", null, __("ABHA creation failed. Please try again.")); return; }
				this.abhaNumber  = r.message.abha_number;
				this.abhaAddress = r.message.abha_address;
				this._renderStep(4);
			},
			error: (r) => { this._setLoading(false); this._err("dl-s3-error", r); },
		});
	}

	_readFileAsBase64(inputEl) {
		return new Promise((resolve) => {
			if (!inputEl || !inputEl.files || !inputEl.files[0]) { resolve(null); return; }
			const file = inputEl.files[0];
			// ABDM's real limit is 150KB (confirmed via sandbox rejection) — matching
			// it client-side avoids a failed round-trip for an oversized-but-under-2MB photo.
			if (file.size > 150 * 1024) {
				frappe.show_alert({ message: __("Photo must be under 150 KB"), indicator: "orange" });
				resolve(null); return;
			}
			const reader = new FileReader();
			reader.onload  = (e) => resolve(e.target.result.split(",")[1]);
			reader.onerror = () => resolve(null);
			reader.readAsDataURL(file);
		});
	}

	_step4() {
		this.dialog.$body.append(`
			<div class="text-center" style="padding:24px 0;">
				<div style="font-size:48px;color:#28a745;">✓</div>
				<h4 style="margin:12px 0 4px;">${__("ABHA Created!")}</h4>
				<p class="text-muted">${__("Your ABHA was created using your Driving Licence.")}</p>
				<div style="background:#f8f9fa;border-radius:8px;padding:16px;margin:16px 0;text-align:left;">
					${this.abhaNumber  ? `<div style="margin-bottom:8px;">
						<span class="text-muted" style="font-size:11px;">${__("ABHA Number")}</span><br>
						<strong>${frappe.utils.escape_html(this.abhaNumber)}</strong></div>` : ""}
					${this.abhaAddress ? `<div>
						<span class="text-muted" style="font-size:11px;">${__("ABHA Address")}</span><br>
						<strong style="color:#2490ef;">${frappe.utils.escape_html(this.abhaAddress)}</strong></div>` : ""}
				</div>
			</div>
		`);
		this.dialog.set_primary_action(__("Done"), () => {
			this.dialog.hide();
			if (cur_frm && cur_frm.doctype === "Patient") cur_frm.reload_doc();
		});
	}

	_err(domId, r, message) {
		let msg = message;
		if (!msg && r) { try { msg = JSON.parse(r._server_messages || "[]")[0]?.message; } catch (_) {} }
		$(`#${domId}`).text(msg || __("An error occurred. Please try again.")).show();
	}

	_setLoading(on, text) {
		const btn = this.dialog.get_primary_btn();
		if (on) btn.prop("disabled", true).html(`<i class="fa fa-spinner fa-spin"></i> ${text || __("Please wait…")}`);
		else    btn.prop("disabled", false);
	}
};

healthcare.regional.india.abdm.show_abha_dl_dialog = function (patient) {
	return new healthcare.regional.india.abdm.AbhaDlDialog(patient);
};


// ===========================================================================
// QRScannerDialog — Show ABHA QR + Download Card (S4)
// ===========================================================================
healthcare.regional.india.abdm.QRScannerDialog = class QRScannerDialog {
	constructor(frm) {
		this.frm     = frm;
		this.patient = frm.doc.name;

		this.dialog = new frappe.ui.Dialog({
			title: __("ABHA QR Code"),
			size:  "small",
		});
	}

	show() {
		const $b = this.dialog.$body;
		$b.empty();
		$b.append(`
			<div class="abdm-qr-wrap text-center" style="padding:16px;">
				<p class="text-muted">
					<i class="fa fa-spinner fa-spin fa-2x"></i><br>${__("Loading QR Code…")}
				</p>
			</div>
		`);
		this.dialog.set_primary_action(__("Download ABHA Card"), () => this._downloadCard());
		this.dialog.set_secondary_action_label(__("Refresh"));
		this.dialog.set_secondary_action(() => this._loadQR());
		this.dialog.show();
		this._loadQR();
	}

	_loadQR() {
		const wrap = this.dialog.$body.find(".abdm-qr-wrap");
		wrap.html(`<p class="text-muted"><i class="fa fa-spinner fa-spin fa-2x"></i><br>${__("Loading…")}</p>`);
		frappe.call({
			method: "healthcare.regional.india.abdm.api.profile.get_abha_qr_code",
			args:   { patient: this.patient },
			callback: (r) => {
				if (r.exc || !r.message) {
					this._showError(wrap, __("Could not load QR code.")); return;
				}
				const qr  = r.message.qr_code;
				const src = qr.startsWith("data:") ? qr : `data:image/png;base64,${qr}`;
				wrap.html(`
					<div style="background:#fff;padding:16px;border-radius:8px;display:inline-block;
						margin-bottom:12px;box-shadow:0 1px 6px rgba(0,0,0,.12);">
						<img src="${src}" alt="ABHA QR Code" style="width:220px;height:220px;display:block;">
					</div>
					<p class="text-muted" style="font-size:12px;margin-top:4px;">
						${__("Scan this QR code to share health records.")}
					</p>
				`);
			},
			error: (r) => {
				const msg = _parse_server_msg(r) ||
					__("No active ABHA session. Please use ABDM → Verify ABHA first.");
				this._showError(wrap, msg);
			},
		});
	}

	_downloadCard() {
		const btn = this.dialog.get_primary_btn();
		btn.prop("disabled", true).html(`<i class="fa fa-spinner fa-spin"></i> ${__("Downloading…")}`);
		frappe.call({
			method: "healthcare.regional.india.abdm.api.profile.download_abha_card",
			args:   { patient: this.patient },
			callback: (r) => {
				btn.prop("disabled", false).text(__("Download ABHA Card"));
				if (r.exc || !r.message) {
					frappe.show_alert({ message: __("Could not download ABHA card."), indicator: "red" }); return;
				}
				const link = document.createElement("a");
				link.href     = `data:image/png;base64,${r.message.card_b64}`;
				link.download = `ABHA_Card_${frappe.utils.escape_html(this.patient)}.png`;
				document.body.appendChild(link);
				link.click();
				document.body.removeChild(link);
				frappe.show_alert({ message: __("ABHA Card downloaded"), indicator: "green" });
			},
			error: () => {
				btn.prop("disabled", false).text(__("Download ABHA Card"));
				frappe.show_alert({ message: __("Download failed. Please try again."), indicator: "red" });
			},
		});
	}

	_showError(wrap, msg) {
		wrap.html(`
			<div class="text-danger" style="padding:16px;">
				<i class="fa fa-exclamation-triangle fa-2x" style="display:block;margin-bottom:8px;"></i>
				${frappe.utils.escape_html(msg)}
			</div>
			<p class="text-muted" style="font-size:12px;">
				${__("If you have not yet verified your ABHA, use <b>ABDM → Verify ABHA</b> first.")}
			</p>
		`);
	}
};


// ===========================================================================
// AbhaLifecycleDialog — Deactivate / Delete / Reactivate ABHA (SOP §7 / T72)
// ===========================================================================
healthcare.regional.india.abdm.AbhaLifecycleDialog = class AbhaLifecycleDialog {
	/**
	 * action: "deactivate" | "delete" | "reactivate"
	 */
	constructor(frm, action) {
		this.frm      = frm;
		this.patient  = frm.doc.name;
		this.action   = action;
		this.txnId    = null;
		this.otpMode  = "mobile";   // "mobile" | "aadhaar" — set in _renderOtpRequest

		const _META = {
			deactivate: {
				title:   __("Deactivate ABHA"),
				icon:    "fa-pause-circle",
				colour:  "#e67e22",
				warning: __("Deactivating your ABHA will temporarily prevent health records from being shared. You can reactivate it later."),
				confirm: __("Deactivate ABHA"),
				success: __("ABHA deactivated successfully."),
			},
			delete: {
				title:   __("Delete ABHA"),
				icon:    "fa-trash",
				colour:  "#e74c3c",
				warning: __("⚠️ This action is PERMANENT. Deleting your ABHA will erase all linked health records from ABDM. This cannot be undone."),
				confirm: __("Permanently Delete ABHA"),
				success: __("ABHA deleted. The record has been removed from ABDM."),
			},
			reactivate: {
				title:   __("Reactivate ABHA"),
				icon:    "fa-play-circle",
				colour:  "#27ae60",
				warning: __("Reactivating your ABHA will restore health record sharing capabilities."),
				confirm: __("Reactivate ABHA"),
				success: __("ABHA reactivated successfully."),
			},
		};

		this._meta = _META[action] || _META.deactivate;

		this.dialog = new frappe.ui.Dialog({
			title: this._meta.title,
			size:  "regular",
		});
	}

	show() {
		this._renderOtpRequest();
		this.dialog.show();
	}

	// ── Step 1: OTP method selection + send ──────────────────────────────────

	_renderOtpRequest() {
		const $b = this.dialog.$body;
		$b.empty();
		$b.append(`
			<div class="alert" style="border-left:4px solid ${frappe.utils.escape_html(this._meta.colour)};
				background:#fff9f0;padding:12px 16px;border-radius:4px;margin-bottom:16px;">
				<i class="fa ${frappe.utils.escape_html(this._meta.icon)}"
					style="color:${frappe.utils.escape_html(this._meta.colour)};margin-right:8px;"></i>
				${this._meta.warning}
			</div>
			<div style="margin-bottom:14px;">
				<label style="font-weight:600;margin-bottom:6px;display:block;">${__("Verify via")}</label>
				<div class="abdm-otp-method-group" style="display:flex;gap:12px;">
					<label class="abdm-method-option" style="display:flex;align-items:center;gap:6px;cursor:pointer;
						border:1px solid #4f46e5;border-radius:6px;padding:8px 14px;flex:1;
						background:#eef2ff;transition:border-color .15s,background .15s;">
						<input type="radio" name="abdm-otp-method" value="mobile" checked style="accent-color:#4f46e5;">
						<span style="font-size:13px;">${__("Mobile OTP")}</span>
					</label>
					<label class="abdm-method-option" style="display:flex;align-items:center;gap:6px;cursor:pointer;
						border:1px solid #d1d5db;border-radius:6px;padding:8px 14px;flex:1;
						background:#fff;transition:border-color .15s,background .15s;">
						<input type="radio" name="abdm-otp-method" value="aadhaar" style="accent-color:#4f46e5;">
						<span style="font-size:13px;">${__("Aadhaar OTP")}</span>
					</label>
				</div>
			</div>
			<p class="text-muted" style="font-size:13px;" id="abdm-otp-hint">
				${__("An OTP will be sent to your ABHA-linked mobile number.")}
			</p>
			<div id="abdm-lc-req-error" class="text-danger" style="display:none;margin-top:8px;"></div>
		`);
		// Aadhaar number input — shown only when Aadhaar OTP is selected
		$b.append(`
			<div id="abdm-aadhaar-input-wrap" style="display:none;margin-top:10px;">
				<label style="font-weight:600;margin-bottom:4px;display:block;">${__("Aadhaar Number")}</label>
				<input type="text" id="abdm-aadhaar-number" maxlength="14" inputmode="numeric"
					placeholder="XXXX XXXX XXXX"
					style="width:100%;padding:8px 10px;border:1px solid #d1d5db;border-radius:4px;font-size:14px;">
				<p class="text-muted" style="font-size:12px;margin-top:4px;">${__("Enter your 12-digit Aadhaar number to receive OTP via Aadhaar.")}</p>
			</div>
		`);

		$b.find('input[name="abdm-otp-method"]').on("change", (e) => {
			this.otpMode = e.target.value;
			$b.find(".abdm-method-option").css({ "border-color": "#d1d5db", "background": "#fff" });
			$(e.target).closest(".abdm-method-option").css({ "border-color": "#4f46e5", "background": "#eef2ff" });
			const isAadhaar = this.otpMode === "aadhaar";
			$b.find("#abdm-otp-hint").text(
				isAadhaar
					? __("An OTP will be sent to your Aadhaar-registered mobile number.")
					: __("An OTP will be sent to your ABHA-linked mobile number.")
			);
			$b.find("#abdm-aadhaar-input-wrap").toggle(isAadhaar);
		});
		this.dialog.set_primary_action(__("Send OTP"), () => this._sendOtp());
	}

	_sendOtp() {
		// Validate aadhaar input if aadhaar OTP mode selected
		let aadhaarNumber = "";
		if (this.otpMode === "aadhaar") {
			aadhaarNumber = (this.dialog.$body.find("#abdm-aadhaar-number").val() || "").replace(/\s+/g, "");
			if (!/^\d{12}$/.test(aadhaarNumber)) {
				this._err("abdm-lc-req-error", null, __("Please enter a valid 12-digit Aadhaar number."));
				return;
			}
		}
		this._setLoading(true, __("Sending OTP…"));
		frappe.call({
			method: "healthcare.regional.india.abdm.api.profile.request_lifecycle_otp",
			args:   {
				patient:        this.patient,
				action:         this.action,
				otp_mode:       this.otpMode,
				aadhaar_number: aadhaarNumber,
			},
			callback: (r) => {
				this._setLoading(false);
				if (r.exc) { this._err("abdm-lc-req-error", r); return; }
				if (!r.message) {
					this._err("abdm-lc-req-error", null, __("Could not send OTP. Ensure the patient has a linked ABHA."));
					return;
				}
				this.txnId = r.message.txnId;
				frappe.show_alert({
					message: this.otpMode === "aadhaar"
						? __("OTP sent to your Aadhaar-registered mobile.")
						: __("OTP sent to your ABHA-linked mobile."),
					indicator: "green",
				}, 4);
				this._renderOtpConfirm();
			},
			error: (r) => { this._setLoading(false); this._err("abdm-lc-req-error", r); },
		});
	}

	_renderOtpConfirm() {
		const $b = this.dialog.$body;
		$b.empty();
		$b.append(`
			<p class="text-muted">${
				this.otpMode === "aadhaar"
					? __("Enter the 6-digit OTP sent to your Aadhaar-registered mobile.")
					: __("Enter the 6-digit OTP sent to your ABHA-linked mobile.")
			}</p>
			<div class="form-group">
				<label>${__("OTP")} <span class="req-star">*</span></label>
				<input id="abdm-lc-otp" type="text" class="form-control"
					placeholder="6-digit OTP" maxlength="6" inputmode="numeric" autocomplete="one-time-code">
			</div>
			<div id="abdm-lc-otp-error" class="text-danger" style="display:none;margin-top:8px;"></div>
		`);
		setTimeout(() => this.dialog.$body.find("#abdm-lc-otp").focus(), 50);
		this.dialog.set_primary_action(this._meta.confirm, () => this._confirmWithOtp());
	}

	_confirmWithOtp() {
		const otp = (this.dialog.$body.find("#abdm-lc-otp").val() || "").trim();
		if (!otp || otp.length !== 6 || !/^\d+$/.test(otp)) {
			this.dialog.$body.find("#abdm-lc-otp-error").text(__("Enter the 6-digit OTP.")).show();
			return;
		}
		this._setLoading(true, __("Confirming…"));
		frappe.call({
			method: "healthcare.regional.india.abdm.api.profile.confirm_lifecycle_action",
			args:   { patient: this.patient, action: this.action, txn_id: this.txnId, otp, otp_mode: this.otpMode },
			callback: (r) => {
				this._setLoading(false);
				if (r.exc) { this._err("abdm-lc-otp-error", r); return; }
				this.dialog.hide();
				frappe.show_alert({ message: this._meta.success, indicator: "green" }, 6);
				if (this.frm && this.frm.doctype === "Patient") this.frm.reload_doc();
			},
			error: (r) => { this._setLoading(false); this._err("abdm-lc-otp-error", r); },
		});
	}

	// ── Helpers ───────────────────────────────────────────────────────────────

	_err(domId, r, fallback) {
		const msg = (r && _parse_server_msg(r)) || fallback || __("An error occurred. Please try again.");
		this.dialog.$body.find(`#${domId}`).text(msg).show();
	}

	_setLoading(on, text) {
		const btn = this.dialog.get_primary_btn();
		if (on) btn.prop("disabled", true).html(`<i class="fa fa-spinner fa-spin"></i> ${text || __("Please wait…")}`);
		else    btn.prop("disabled", false);
	}
};


// ===========================================================================
// AbhaProfileUpdateDialog — edit ABHA profile fields (name, email)
// ===========================================================================

healthcare.regional.india.abdm.AbhaProfileUpdateDialog = class AbhaProfileUpdateDialog {
	constructor(frm) {
		this.frm     = frm;
		this.patient = frm.doc.name;

		this.dialog = new frappe.ui.Dialog({
			title: __("Update ABHA Profile"),
			size:  "regular",
		});
	}

	show() {
		this._fetchAndRender();
		this.dialog.show();
	}

	_fetchAndRender() {
		// Pre-fill from the Frappe Patient record (no ABDM API call needed for local update)
		frappe.db.get_value("Patient", this.patient,
			["patient_name", "first_name", "middle_name", "last_name", "email", "abha_number", "abha_address"],
			(values) => {
				this._renderForm(values || {});
			}
		);
	}

	_renderForm(p) {
		const firstName  = p.first_name  || "";
		const middleName = p.middle_name || "";
		const lastName   = p.last_name   || "";
		const email      = p.email       || "";

		this.dialog.$body.html(`
			<div style="background:#f0f4ff;border-radius:6px;padding:12px 16px;margin-bottom:18px;font-size:13px;">
				<strong>${__("ABHA Number")}:</strong> ${frappe.utils.escape_html(p.abha_number || "—")}
				&nbsp;|&nbsp;
				<strong>${__("ABHA Address")}:</strong> ${frappe.utils.escape_html(p.abha_address || "—")}
			</div>
			<p class="text-muted" style="font-size:12px;margin-bottom:14px;">
				<i class="fa fa-info-circle"></i>
				${__("Changes are saved to this patient record. ABDM-side sync (SOP §7.1/7.2) will be available in the next release.")}
			</p>

			<div class="form-group">
				<label style="font-weight:600;">${__("First Name")}</label>
				<input id="abdm-prof-first" type="text" class="form-control"
					placeholder="${__("First name")}" value="${frappe.utils.escape_html(firstName)}">
			</div>
			<div class="form-group">
				<label style="font-weight:600;">${__("Middle Name")}</label>
				<input id="abdm-prof-middle" type="text" class="form-control"
					placeholder="${__("Middle name (optional)")}" value="${frappe.utils.escape_html(middleName)}">
			</div>
			<div class="form-group">
				<label style="font-weight:600;">${__("Last Name")}</label>
				<input id="abdm-prof-last" type="text" class="form-control"
					placeholder="${__("Last name")}" value="${frappe.utils.escape_html(lastName)}">
			</div>
			<div class="form-group">
				<label style="font-weight:600;">${__("Email")}</label>
				<input id="abdm-prof-email" type="email" class="form-control"
					placeholder="${__("Email address")}" value="${frappe.utils.escape_html(email)}">
			</div>

			<div id="abdm-prof-error" class="text-danger" style="display:none;margin-top:8px;"></div>
		`);

		this.dialog.set_primary_action(__("Save Changes"), () => this._save());
		this.dialog.get_primary_btn().prop("disabled", false);
	}

	// ── Submit ───────────────────────────────────────────────────────────────

	_save() {
		const $b          = this.dialog.$body;
		const firstName   = ($b.find("#abdm-prof-first").val()  || "").trim();
		const middleName  = ($b.find("#abdm-prof-middle").val() || "").trim();
		const lastName    = ($b.find("#abdm-prof-last").val()   || "").trim();
		const email       = ($b.find("#abdm-prof-email").val()  || "").trim();

		if (!firstName && !lastName && !email) {
			$b.find("#abdm-prof-error").text(__("Update at least one field.")).show();
			return;
		}
		if (email && !/^[^\s@]+@[^\s@]+\.[^\s@]+$/.test(email)) {
			$b.find("#abdm-prof-error").text(__("Enter a valid email address.")).show();
			return;
		}

		$b.find("#abdm-prof-error").hide();
		this._setLoading(true, __("Saving…"));

		frappe.call({
			method: "healthcare.regional.india.abdm.api.profile.update_abha_profile",
			args:   {
				patient:     this.patient,
				first_name:  firstName,
				middle_name: middleName,
				last_name:   lastName,
				email:       email,
			},
			callback: (r) => {
				this._setLoading(false);
				if (r.exc) {
					$b.find("#abdm-prof-error").text(_parse_server_msg(r) || __("Update failed. Please try again.")).show();
					return;
				}
				this.dialog.hide();
				frappe.show_alert({ message: __("ABHA profile updated successfully."), indicator: "green" }, 5);
				if (this.frm && this.frm.doctype === "Patient") this.frm.reload_doc();
			},
			error: (r) => {
				this._setLoading(false);
				$b.find("#abdm-prof-error").text(_parse_server_msg(r) || __("An error occurred.")).show();
			},
		});
	}

	// ── Helpers ───────────────────────────────────────────────────────────────

	_setLoading(on, text) {
		const btn = this.dialog.get_primary_btn();
		if (on) btn.prop("disabled", true).html(`<i class="fa fa-spinner fa-spin"></i> ${text || __("Please wait…")}`);
		else    btn.prop("disabled", false).html(__("Save Changes"));
	}
};


// ===========================================================================
// Shared helpers
// ===========================================================================

/**
 * Extract a human-readable message from a Frappe error response.
 * _server_messages is a JSON array where each item may be a plain string
 * or an object with a .message property.
 */
function _parse_server_msg(r) {
	try {
		const items = JSON.parse(r._server_messages || "[]");
		const first = items[0];
		if (!first) return null;
		// Some Frappe versions double-encode; try inner parse too
		if (typeof first === "string") {
			try { return JSON.parse(first).message || first; } catch (_) { return first; }
		}
		return first.message || null;
	} catch (_) { return null; }
}

// ===========================================================================
// Patient form hooks
// ===========================================================================

frappe.ui.form.on("Patient", {
	refresh(frm) {
		if (frm.doc.__islocal) return;
		// ABDM/ABHA is India's national health ID system — only show these
		// actions for India deployments (matches the pre-existing behaviour
		// of the native regional/india/abdm module this replaces).
		if (frappe.boot.sysdefaults.country !== "India") return;

		const hasAbha = !!(frm.doc.abha_number || frm.doc.abha_address);

		if (!hasAbha) {
			frm.add_custom_button(__("Create ABHA"), () => {
				new healthcare.regional.india.abdm.AbhaCreationDialog(frm.doc.name);
			}, __("ABDM"));

			frm.add_custom_button(__("Create ABHA via DL"), () => {
				new healthcare.regional.india.abdm.AbhaDlDialog(frm.doc.name);
			}, __("ABDM"));
		}

		frm.add_custom_button(__("Show ABHA QR"), () => {
			new healthcare.regional.india.abdm.QRScannerDialog(frm).show();
		}, __("ABDM"));

		const verifyLabel = hasAbha ? __("Re-verify ABHA") : __("Verify ABHA");
		frm.add_custom_button(verifyLabel, () => {
			new healthcare.regional.india.abdm.AbhaVerifyDialog(frm).show();
		}, __("ABDM"));

		if (hasAbha) {
			frm.add_custom_button(__("Update ABHA Profile"), () => {
				new healthcare.regional.india.abdm.AbhaProfileUpdateDialog(frm).show();
			}, __("ABDM"));
		}

		_render_abha_token_badge(frm);
	},
});

function _render_abha_token_badge(frm) {
	frappe.call({
		method: "healthcare.regional.india.abdm.api.profile.get_token_status",
		args: { patient: frm.doc.name },
		callback(r) {
			if (!r.message) return;
			const { status } = r.message;
			const color = { ACTIVE: "green", EXPIRING: "orange", EXPIRED: "red" }[status] || "grey";
			const label = { ACTIVE: "ABHA Active", EXPIRING: "ABHA Expiring Soon", EXPIRED: "ABHA Expired" }[status] || "No ABHA";
			frm.dashboard.add_indicator(__(label), color);
		},
	});
}
