frappe.ui.form.on("Imaging Study", {
	refresh(frm) {
		if (!frm.doc.__islocal && frm.doc.series_json) {
			const series_list = JSON.parse(frm.doc.series_json || "[]");

			let html = `
				<div class="series-container" style="display:flex; flex-wrap:wrap; gap:12px;">
			`;

			series_list.forEach((series, index) => {
				html += `
					<div class="series-card" data-series-index="${index}"
						style="
							text-align:center;
							width:140px;
							cursor:pointer;
							border:1px solid #ccc;
							border-radius:7px;
							padding:8px;
							overflow:hidden;
							max-height:220px;
							display:flex;
							flex-direction:column;
							justify-content:space-between;
							box-shadow:0 2px 5px rgba(0,0,0,0.05);">
						<img src="${series.series_preview}" style="width:100%; height:auto; border-radius:5px;" />
						<!--<div style="font-size: 0.85rem; margin-top: 6px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;" title="${series.description || series.series_uid}">
							${series.description || series.series_uid}
						</div>-->
						<div style="color: #888;">${series.instance_previews?.length || "-"} images</div>
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
						const d = new frappe.ui.Dialog({
							title: `${series.series_uid}`,
							size: "large",
							fields: [
								{
								fieldname: "viewer_html",
								fieldtype: "HTML",
								options: `
									<iframe
									src="assets/index.html?seriesUID=${series.series_uid}&qidoRoot=http://localhost:8042/dicom-web&wadoRoot=http://localhost:8042/dicom-web"
									width="100%"
									height="600px"
									frameborder="0"
									></iframe>
								`
								}
							]
						});
						d.show();
					});
				});
			}, 50);

			/*setTimeout(() => {
				const cards = frm.fields_dict.preview_html.$wrapper.find(".series-card");
				const previewContainer = frm.fields_dict.preview_html.$wrapper.find("#instance-previews");

				cards.each(function () {
					const card = $(this);
					const index = card.data("series-index");
					const series = series_list[index];

					card.on("click", function () {
						cards.css("border", "1px solid #ccc");
						card.css("border", "3px solid #ccc");

						previewContainer.empty().hide();
						series.instance_previews.forEach(instance => {
							const img = $(`<img src="${instance.file_url}"
								style="
									width:120px;
									height:auto;
									border:1px solid #aaa;
									border-radius:7px;
									margin:3px;"
							/>`);
							previewContainer.append(img);
						});
						previewContainer.show();
					});
				});
			}, 50);*/
		}
	}
});
