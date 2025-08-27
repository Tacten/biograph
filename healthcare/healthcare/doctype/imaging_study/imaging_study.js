frappe.ui.form.on("Imaging Study", {
	async refresh(frm) {
		if (!frm.doc.__islocal && frm.doc.preview_json) {
			const [pacs_base_url] = await Promise.all([
				frappe.db.get_single_value('Healthcare Settings', 'pacs_base_url'),
			]);
			let series_list = JSON.parse(frm.doc.preview_json || "[]");

			let html = `
				<div class="series-container" style="display:flex; flex-wrap:wrap; gap:16px; margin-bottom:1em;">
			`;

			series_list.forEach((series, index) => {
				html += `
					<div class="series-card" data-series-index="${index}"
						style="
							text-align:center;
							cursor:pointer;
							width:18%;
							border:1px solid #ccc;
							border-radius:7px;
							padding:7px;
							overflow:hidden;
							max-height:220px;
							display:flex;
							flex-direction:column;
							justify-content:space-between;
							box-shadow:0 2px 5px rgba(0,0,0,0.05);">
						<img src="${series.preview_url}" style="width:100%; height:auto; border-radius:5px;" />
						<div style="
							font-size: 0.85rem;
							margin-top: 6px;
							white-space: nowrap;
							overflow: hidden;
							text-overflow: ellipsis;" title="${series.SeriesDescription || series.SeriesInstanceUID}
						">
							${series.SeriesDescription || series.SeriesInstanceUID}
						</div>
						<div style="color: #888888;">${series.InstanceCount || "0"} ${series.Modality} images</div>
					</div>
				`;
			});

			html += `
				</div>
				<div id="instance-previews"
					style="margin-top:20px;
					display:none;
					flex-wrap:wrap;
					gap:10px;
					justify-content:left;">
				</div>
			`;

			frm.fields_dict.preview_html.$wrapper.html(html);

			setTimeout(() => {
				const cards = frm.fields_dict.preview_html.$wrapper.find(".series-card");

				cards.each(function () {
					const card = $(this);
					const index = card.data("series-index");
					const series = series_list[index];

					card.on("click", function () {
						cards.css("border", "1px solid #ccc");
						card.css("border", "3px solid #ccc");

						const site = `${pacs_base_url}/ohif/viewer?StudyInstanceUIDs=${frm.doc.study_instance_uid}`
						const url = new URL(site, window.location.origin);

						console.log(url.toString());

						const d = new frappe.ui.Dialog({
							title: `${series.SeriesInstanceUID}`,
							size: "extra-large",
							fields: [
								{
								fieldname: "viewer_html",
								fieldtype: "HTML",
								options: `
									<iframe
										src="${url.toString()}"
										frameborder="0"
										style="display: block; height: 85vh; width: 100%"
									></iframe>
								`
								}
							]
						});
						d.show();
					});
				});
			}, 50);
		}
	}
});
